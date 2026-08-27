# evaluate.py -- score every cached run against the human gold set.
#
# WHAT IS BEING MEASURED, and why each number is here:
#
#   precision / recall / F1   -- the agent's capacity_status == "sold_out" against the
#                                owner's flag=1. The task metric.
#   F1 95% CI (bootstrap)     -- with 70 rows and 17 positives, a bare point estimate
#                                is misleading. Two arms whose intervals overlap have
#                                not been shown to differ.
#   Cohen's kappa             -- agreement corrected for chance. Accuracy looks great
#                                on a 17/53 split simply by predicting "no".
#   grounding rate            -- share of required quotes that really occur in the
#                                document. This is the hallucination metric and it is
#                                independent of whether the LABEL was right.
#   empty / degenerate rate   -- share of documents where the model asserted NOTHING
#                                (every field "not_stated"). Such a card is valid JSON
#                                and carries no quotes, so it cannot show up in the
#                                grounding column; without this metric a model that
#                                says nothing at all looks clean. Local models under
#                                constrained decoding fail exactly this way.
#                                Note the regex arm scores non-zero here for a
#                                different reason: by design it only ever attempts
#                                capacity_status, so it is silent whenever no keyword
#                                matches. Compare it across model arms, not to regex.
#   fields asserted / doc     -- the same signal as a rate out of 5.
#   repair rate               -- how often the model's first answer had bad evidence
#                                (in the JSON report; dropped from the printed table).
#   cost / latency            -- an arm that is 2 points better and 6x the price is a
#                                decision, not a win.
#
# READ-ONLY: reads agent/out/signals/ and agent/eval/gold_set.json; writes only
# agent/out/eval_report.json.
#
# HOW TO RUN (from the project root)
#   python -X utf8 -m agent.eval.evaluate

import glob
import json
import os
import random
import statistics

from agent.eval.gold import load_gold, POSITIVE_VALUE
from agent.schema import ExtractionResult, SIGNAL_FIELDS

SIGNALS_GLOB = "agent/out/signals/*.json"
OUT_FILE = "agent/out/eval_report.json"

BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 20260820          # fixed so the report is reproducible


# --------------------------------------------------------------------------------
# Metric helpers -- written out rather than imported, so each one can be read.
# --------------------------------------------------------------------------------

def confusion(pairs):
    """pairs = [(gold_flag, predicted_flag), ...] -> tp, fp, fn, tn."""
    tp = sum(1 for g, p in pairs if g == 1 and p == 1)
    fp = sum(1 for g, p in pairs if g == 0 and p == 1)
    fn = sum(1 for g, p in pairs if g == 1 and p == 0)
    tn = sum(1 for g, p in pairs if g == 0 and p == 0)
    return tp, fp, fn, tn


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def cohens_kappa(tp, fp, fn, tn):
    """Agreement above what two random raters with the same marginals would hit."""
    n = tp + fp + fn + tn
    if n == 0:
        return 0.0
    observed = (tp + tn) / n
    # expected agreement from the marginal rates of each rater
    expected = (((tp + fp) * (tp + fn)) + ((fn + tn) * (fp + tn))) / (n * n)
    if expected == 1.0:
        return 0.0
    return (observed - expected) / (1 - expected)


def bootstrap_f1_ci(pairs, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED):
    """Percentile bootstrap 95% CI for F1: resample the 70 calls with replacement."""
    if not pairs:
        return None, None
    rng = random.Random(seed)
    n = len(pairs)
    scores = []
    for _ in range(samples):
        resampled = [pairs[rng.randrange(n)] for _ in range(n)]
        tp, fp, fn, _ = confusion(resampled)
        scores.append(prf(tp, fp, fn)[2])
    scores.sort()
    return scores[int(0.025 * samples)], scores[int(0.975 * samples)]


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(q * len(ordered)), len(ordered) - 1)
    return ordered[index]


# --------------------------------------------------------------------------------
# Load cached runs and group them into experiment cells.
# --------------------------------------------------------------------------------

def load_results():
    results = []
    for path in sorted(glob.glob(SIGNALS_GLOB)):
        try:
            with open(path, encoding="utf-8") as handle:
                results.append(ExtractionResult.model_validate(json.load(handle)))
        except Exception as exc:                    # noqa: BLE001
            print(f"  skipping unreadable cache file {path}: {exc}")
    return results


def cell_name(result):
    parts = [result.arm, result.model, result.prompt_version]
    if result.effort:
        parts.append(result.effort)
    return " / ".join(parts)


def evaluate_cell(name, results, gold_by_path):
    pairs, disagreements = [], []
    grounding_rates, costs, latencies = [], [], []
    repaired = errors = degenerate = 0
    quotes_total = quotes_verified = 0
    fields_asserted = 0

    for result in results:
        gold = gold_by_path.get(result.doc_path)
        if gold is None:
            continue                      # a document outside the labelled set
        if result.error or result.card is None:
            errors += 1
            continue

        predicted = 1 if result.card.capacity_status == POSITIVE_VALUE else 0
        pairs.append((gold["gold_flag"], predicted))
        if gold["gold_flag"] != predicted:
            disagreements.append({
                "company": gold["company"],
                "source_label": gold["source_label"],
                "gold_flag": gold["gold_flag"],
                "predicted": predicted,
                "agent_value": result.card.capacity_status,
                "agent_quote": result.card.quote_of("capacity_status")[:300],
                "agent_quote_check": result.quote_checks.get("capacity_status", "-"),
                "owner_evidence": gold["gold_evidence"][:300],
                "owner_ruling": gold["gold_ruling"],
            })

        # A card where every field is "not_stated" is structurally valid and
        # informationally empty. Counting it explicitly is the only way that failure
        # shows up in the table -- it has no quotes, so it cannot lower grounding.
        asserted = len(result.card.asserted_fields())
        fields_asserted += asserted
        if asserted == 0:
            degenerate += 1

        if result.grounding_rate is not None:
            grounding_rates.append(result.grounding_rate)
        quotes_total += result.quotes_total
        quotes_verified += result.quotes_verified
        costs.append(result.cost_usd)
        latencies.append(result.latency_s)
        repaired += 1 if result.attempts > 1 else 0

    tp, fp, fn, tn = confusion(pairs)
    precision, recall, f1 = prf(tp, fp, fn)
    low, high = bootstrap_f1_ci(pairs)
    n = len(pairs)

    is_extractive = results[0].arm == "regex" if results else False

    return {
        "cell": name,
        "arm": results[0].arm if results else "",
        "model": results[0].model if results else "",
        "prompt_version": results[0].prompt_version if results else "",
        "effort": results[0].effort if results else "",
        "n_scored": n,
        "n_errors": errors,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "f1_ci95": [round(low, 4), round(high, 4)] if low is not None else None,
        "accuracy": round((tp + tn) / n, 4) if n else None,
        "cohens_kappa": round(cohens_kappa(tp, fp, fn, tn), 4),
        # Grounding is only informative for arms that GENERATE quotes. The regex arm
        # copies the matched sentence, so its 100% is an artefact, not a result.
        "grounding_rate": (None if is_extractive
                           else (round(quotes_verified / quotes_total, 4) if quotes_total else None)),
        "grounding_note": ("extractive arm -- quotes are copied, so grounding is 100% "
                           "by construction and is not reported"
                           if is_extractive else ""),
        "quotes_total": quotes_total,
        "quotes_verified": quotes_verified,
        "repair_rate": round(repaired / n, 4) if n else None,
        # Degeneracy: valid JSON, nothing said. See agent/README.md.
        "degenerate_cards": degenerate,
        "degenerate_rate": round(degenerate / n, 4) if n else None,
        "fields_asserted_per_doc": round(fields_asserted / n, 2) if n else None,
        "cost_total_usd": round(sum(costs), 4),
        "cost_per_doc_usd": round(statistics.fmean(costs), 5) if costs else 0.0,
        "latency_p50_s": percentile(latencies, 0.50),
        "latency_p95_s": percentile(latencies, 0.95),
        "disagreements": disagreements,
    }


def main():
    gold = load_gold()
    gold_by_path = {row["doc_path"]: row for row in gold}

    results = load_results()
    cells = {}
    for result in results:
        cells.setdefault(cell_name(result), []).append(result)

    reports = [evaluate_cell(name, group, gold_by_path)
               for name, group in sorted(cells.items())]
    reports = [r for r in reports if r["n_scored"] or r["n_errors"]]
    reports.sort(key=lambda r: r["f1"], reverse=True)

    payload = {
        "gold_set": {
            "n_rows": len(gold),
            "n_positive": sum(r["gold_flag"] for r in gold),
            "positive_value": POSITIVE_VALUE,
        },
        "bootstrap": {"samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED},
        "cells": reports,
    }
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    print_table(payload)
    print(f"\nWrote {OUT_FILE}")
    return payload


def print_table(payload):
    gold = payload["gold_set"]
    print(f"\nGold set: {gold['n_rows']} calls, {gold['n_positive']} positive "
          f"(agent equivalent: capacity_status == '{gold['positive_value']}')\n")
    header = (f"{'cell':<46}{'N':>4}{'P':>7}{'R':>7}{'F1':>7}"
              f"{'F1 95% CI':>16}{'kappa':>7}{'ground':>8}{'empty':>7}{'flds':>6}{'$/doc':>9}{'p50s':>7}")
    print(header)
    print("-" * len(header))
    for cell in payload["cells"]:
        ci = cell["f1_ci95"]
        ci_text = f"[{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "-"
        ground = "-" if cell["grounding_rate"] is None else f"{cell['grounding_rate']:.0%}"
        empty = "-" if cell["degenerate_rate"] is None else f"{cell['degenerate_rate']:.0%}"
        print(f"{cell['cell']:<46}{cell['n_scored']:>4}"
              f"{cell['precision']:>7.3f}{cell['recall']:>7.3f}{cell['f1']:>7.3f}"
              f"{ci_text:>16}{cell['cohens_kappa']:>7.3f}{ground:>8}{empty:>7}"
              f"{(cell['fields_asserted_per_doc'] or 0):>6.1f}"
              f"{cell['cost_per_doc_usd']:>9.4f}{(cell['latency_p50_s'] or 0):>7.1f}")
        if cell["n_errors"]:
            print(f"{'':<46}  ({cell['n_errors']} document(s) errored and were excluded)")


if __name__ == "__main__":
    main()
