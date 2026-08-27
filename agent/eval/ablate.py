# ablate.py -- run the experiment matrix, then score it.
#
# Every cell is (arm, model, prompt_version, effort). Because run_extract caches per
# cell per document, re-running this is cheap: finished cells are read from disk and
# only new ones cost anything. That is what makes it safe to add a model and re-run
# the whole matrix.
#
# Cells are run SEQUENTIALLY, and local cells single-threaded on purpose: an Ollama
# model saturates the CPU with one request, so running two at once just splits the
# same cores and reports misleading per-document latencies.
#
# HOW TO RUN (from the project root)
#   python -X utf8 -m agent.eval.ablate            # everything defined below
#   python -X utf8 -m agent.eval.ablate --only local
#   python -X utf8 -m agent.eval.ablate --dry-run

import argparse

from agent.eval.evaluate import main as evaluate_main
from agent.eval.gold import load_gold
from agent.local_provider import installed_models, server_available
from agent.run_extract import run

# (group, arm, model, prompt_version, effort, workers)
MATRIX = [
    ("free",  "regex",            "regex",            "keywords_v1", "",       1),

    # Frontier: the three context regimes on the same model.
    ("api",   "single_call",      "claude-opus-5",    "v1",          "medium", 6),
    ("api",   "retrieval_single", "claude-opus-5",    "v1",          "medium", 6),
    ("api",   "agent",            "claude-opus-5",    "v1",          "medium", 6),

    # Cheaper frontier models, same three regimes -- the cost/quality axis.
    ("api",   "retrieval_single", "claude-haiku-4-5", "v1",          "medium", 6),
    ("api",   "single_call",      "claude-haiku-4-5", "v1",          "medium", 6),
    ("api",   "retrieval_single", "claude-sonnet-5",  "v1",          "medium", 6),

    # Local. Only the retrieval regime fits on a CPU, and only with the scratchpad
    # variant (the plain schema returns empty cards -- see agent/schema.py).
    ("local", "retrieval_single", "qwen3:4b",         "v1_scratch",  "",       1),
    ("local", "retrieval_single", "qwen3:8b",         "v1_scratch",  "",       1),
    # The plain-schema cell is kept deliberately: it is the evidence that constrained
    # decoding fails silently rather than loudly. Cheap, because it returns empty cards fast.
    ("local", "retrieval_single", "qwen3:4b",         "v1",          "",       1),
]


def main():
    parser = argparse.ArgumentParser(description="Run the ablation matrix and score it.")
    parser.add_argument("--only", choices=["free", "api", "local"],
                        help="run just one group")
    parser.add_argument("--model", action="append", default=None,
                        help="restrict to these model ids (repeatable)")
    parser.add_argument("--limit", type=int, default=0, help="first N documents per cell")
    parser.add_argument("--dry-run", action="store_true", help="list cells and exit")
    args = parser.parse_args()

    cells = [c for c in MATRIX if not args.only or c[0] == args.only]
    if args.model:
        cells = [c for c in cells if c[2] in set(args.model)]
    rows = load_gold()
    if args.limit:
        rows = rows[:args.limit]

    local_ok = server_available()
    local_models = set(installed_models())

    print(f"{len(cells)} cell(s), {len(rows)} documents each\n")
    for group, arm, model, prompt, effort, workers in cells:
        label = f"{arm} / {model} / {prompt}" + (f" / {effort}" if effort else "")
        if group == "local":
            if not local_ok:
                print(f"SKIP {label}: no Ollama server on localhost:11434")
                continue
            if model not in local_models:
                print(f"SKIP {label}: model not pulled (`ollama pull {model}`)")
                continue
        if args.dry_run:
            print(f"WOULD RUN {label}  workers={workers}")
            continue

        print(f"\n{'=' * 78}\nCELL {label}\n{'=' * 78}")
        try:
            run(arm, model, effort, prompt, rows, workers, force=False)
        except Exception as exc:                    # noqa: BLE001
            # One dead cell (no credit, model unloaded) must not lose the others.
            print(f"CELL FAILED: {type(exc).__name__}: {exc}")

    if not args.dry_run:
        print(f"\n{'=' * 78}\nSCORING\n{'=' * 78}")
        evaluate_main()


if __name__ == "__main__":
    main()
