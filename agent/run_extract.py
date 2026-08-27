# run_extract.py -- run one arm over a set of documents and cache every result.
#
# Caching is not a convenience here, it is what makes the experiment repeatable.
# One result file per (arm, model, prompt, effort, document) means:
#   * re-running an evaluation costs nothing and cannot drift,
#   * adding a model to the ablation only pays for the new cells,
#   * a crashed run resumes instead of restarting.
#
# READ-ONLY on the rest of the repo. Writes only under agent/out/.
#
# HOW TO RUN (from the project root)
#   python -X utf8 -m agent.run_extract --arm agent --model claude-opus-5
#   python -X utf8 -m agent.run_extract --arm single_call --model claude-haiku-4-5 --limit 5
#   python -X utf8 -m agent.run_extract --arm regex            # free, no API calls

import argparse
import concurrent.futures
import json
import os
import re
import time

from agent.baselines import run_regex
from agent.corpus import Document, list_documents
from agent.eval.gold import load_gold
from agent.extractor import run_agent, run_retrieval_single, run_single_call
from agent.schema import ExtractionResult

SIGNALS_DIR = "agent/out/signals"
RUNS_DIR = "agent/out/runs"

ARMS = {
    "agent": run_agent,
    "single_call": run_single_call,
    "retrieval_single": run_retrieval_single,
    "regex": run_regex,
}


def cache_key(arm: str, model: str, prompt_version: str, effort: str, doc_path: str) -> str:
    """Filesystem-safe identity of one experiment cell for one document."""
    stem = os.path.basename(doc_path)[:-4]
    raw = f"{arm}__{model}__{prompt_version}__{effort or 'na'}__{stem}"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", raw)


def cache_path(key: str) -> str:
    return os.path.join(SIGNALS_DIR, key + ".json")


def load_cached(key: str):
    path = cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return ExtractionResult.model_validate(json.load(handle))
    except Exception:                    # noqa: BLE001 - a corrupt cache file just re-runs
        return None


def save_cached(key: str, result: ExtractionResult) -> None:
    os.makedirs(SIGNALS_DIR, exist_ok=True)
    with open(cache_path(key), "w", encoding="utf-8") as handle:
        handle.write(result.model_dump_json(indent=2))


def _document_from_row(row) -> Document:
    """Gold rows carry a resolved path; rebuild a light Document around it."""
    return Document(path=row["doc_path"], company_token=row.get("company", ""),
                    quarter=0, year=0, suffix="")


def extract_one(row, arm: str, model: str, effort: str,
                prompt_version: str, force: bool) -> ExtractionResult:
    key = cache_key(arm, model, prompt_version, effort, row["doc_path"])
    if not force:
        cached = load_cached(key)
        if cached is not None:
            return cached
    result = ARMS[arm](_document_from_row(row), row["source_label"],
                       model=model, effort=effort, prompt_version=prompt_version)
    save_cached(key, result)
    return result


def run(arm: str, model: str, effort: str, prompt_version: str,
        rows, workers: int, force: bool):
    started = time.time()
    results = [None] * len(rows)

    def work(index):
        return index, extract_one(rows[index], arm, model, effort, prompt_version, force)

    if workers <= 1 or arm == "regex":
        for index in range(len(rows)):
            _, results[index] = work(index)
            _progress(index + 1, len(rows), results[index])
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(work, i) for i in range(len(rows))]
            done = 0
            for future in concurrent.futures.as_completed(futures):
                index, result = future.result()
                results[index] = result
                done += 1
                _progress(done, len(rows), result)

    elapsed = round(time.time() - started, 1)
    summary = {
        "arm": arm, "model": model, "effort": effort,
        "prompt_version": prompt_version,
        "n_documents": len(rows),
        "wall_clock_s": elapsed,
        "errors": sum(1 for r in results if r.error),
        "total_cost_usd": round(sum(r.cost_usd for r in results), 4),
        "total_input_tokens": sum(r.input_tokens for r in results),
        "total_output_tokens": sum(r.output_tokens for r in results),
        "total_cache_read_tokens": sum(r.cache_read_tokens for r in results),
    }
    os.makedirs(RUNS_DIR, exist_ok=True)
    run_name = cache_key(arm, model, prompt_version, effort, "run.txt")
    with open(os.path.join(RUNS_DIR, run_name + ".json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("\n" + json.dumps(summary, indent=2))
    return results, summary


def _progress(done, total, result):
    status = "ERR" if result.error else "ok "
    ground = "" if result.grounding_rate is None else f" ground={result.grounding_rate:.0%}"
    print(f"  [{done:>3}/{total}] {status} {os.path.basename(result.doc_path):<38}"
          f" {result.latency_s:>6}s ${result.cost_usd:.4f}{ground}"
          f"{'' if result.attempts == 1 else f' repaired'}"
          f"{'  ' + result.error if result.error else ''}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Run one extraction arm over documents.")
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument("--effort", default="medium",
                        help="low | medium | high | xhigh | max (model arms only)")
    parser.add_argument("--prompt", default="v1", help="prompt version from agent/prompts.py")
    parser.add_argument("--limit", type=int, default=0, help="only the first N documents")
    parser.add_argument("--workers", type=int, default=6, help="parallel requests")
    parser.add_argument("--force", action="store_true", help="ignore the cache and re-run")
    parser.add_argument("--all-docs", action="store_true",
                        help="run the whole corpus instead of the labelled gold set")
    args = parser.parse_args()

    # The regex arm has no model, effort or prompt. Pin them so its cache files and
    # run summary are not mislabelled with whatever the CLI defaults happened to be.
    if args.arm == "regex":
        args.model, args.effort, args.prompt = "regex", "", "keywords_v1"

    if args.all_docs:
        rows = [{"company": d.company_token, "doc_path": d.path,
                 "source_label": d.stem, "gold_flag": None}
                for d in list_documents() if d.is_full_transcript]
    else:
        rows = load_gold()
    if args.limit:
        rows = rows[:args.limit]

    print(f"arm={args.arm} model={args.model} effort={args.effort} "
          f"prompt={args.prompt} documents={len(rows)} workers={args.workers}")
    run(args.arm, args.model, args.effort, args.prompt, rows, args.workers, args.force)


if __name__ == "__main__":
    main()
