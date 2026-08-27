# retrieval_curve.py -- how much evidence does retrieval lose at each context budget?
#
# The retrieval_single arm can only cite what we put in front of it. So before asking
# how well a model scores on that arm, measure the CEILING: of the evidence a
# full-reading agent found, how much survives into the retrieved context?
#
# Ground truth for "evidence that exists" = the quotes produced by the full-document
# tool-loop arm, restricted to the ones our verifier confirmed appear verbatim in the
# source. Those are real spans, so asking whether retrieval kept them is a fair test.
#
# READ-ONLY. Prints a table; writes nothing.
#
# HOW TO RUN (from the project root, after an `--arm agent` run has been cached)
#   python -X utf8 -m agent.eval.retrieval_curve

import glob
import json

from agent.retrieval import select_context
from agent.schema import ExtractionResult, SIGNAL_FIELDS
from agent.verify import normalize

REFERENCE_GLOB = "agent/out/signals/agent__claude-opus-5__*.json"

# (top_k per field, max context words)
SETTINGS = [(3, 2600), (4, 3200), (5, 4000), (6, 5000), (8, 7000), (12, 10**9)]


def load_reference():
    """Cached full-document agent runs, paired with their source text."""
    reference = []
    for path in sorted(glob.glob(REFERENCE_GLOB)):
        result = ExtractionResult.model_validate(json.load(open(path, encoding="utf-8")))
        if result.card is None:
            continue
        with open(result.doc_path, encoding="utf-8") as handle:
            reference.append((result, handle.read()))
    return reference


def main():
    reference = load_reference()
    if not reference:
        print(f"No cached runs match {REFERENCE_GLOB}. Run:\n"
              f"  python -X utf8 -m agent.run_extract --arm agent --model claude-opus-5")
        return

    verified_quotes = sum(
        1 for r, _ in reference for f in SIGNAL_FIELDS
        if r.quote_checks.get(f) in ("exact", "normalized")
    )
    print(f"reference: {len(reference)} documents, {verified_quotes} verified quotes\n")

    header = (f"{'top_k':>6}{'budget':>9}{'med ctx words':>15}"
              f"{'quote recall':>14}{'capacity recall':>17}")
    print(header)
    print("-" * len(header))

    for top_k, max_words in SETTINGS:
        kept = lost = capacity_kept = capacity_lost = 0
        sizes = []
        for result, text in reference:
            context, _ = select_context(text, top_k=top_k, max_words=max_words)
            sizes.append(len(context.split()))
            normalized_context = normalize(context)
            for field in SIGNAL_FIELDS:
                if result.quote_checks.get(field) not in ("exact", "normalized"):
                    continue
                present = normalize(result.card.quote_of(field)) in normalized_context
                kept += present
                lost += not present
                if field == "capacity_status":
                    capacity_kept += present
                    capacity_lost += not present
        median = sorted(sizes)[len(sizes) // 2]
        budget = "-" if max_words > 10**8 else str(max_words)
        print(f"{top_k:>6}{budget:>9}{median:>15}"
              f"{kept / (kept + lost):>14.0%}"
              f"{capacity_kept / (capacity_kept + capacity_lost):>17.0%}")

    print("\nThe capacity column is the ceiling on retrieval_single's recall for the\n"
          "one field that has a human label.")


if __name__ == "__main__":
    main()
