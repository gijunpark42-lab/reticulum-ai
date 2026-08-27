# gold.py -- build the labelled evaluation set from labels that already exist.
#
# The project owner already classified every US-listed earnings call in the graph by
# hand, one company at a time, recording an evidence quote and a written ruling for
# each judgement call (quant/signal_full_capacity.csv). That is a gold set: 71 calls,
# 17 of them positive. No new labelling is needed -- we only have to join it to the
# document each label was read from.
#
# The join works because both sides carry the same canonical source label
# ("Micron Q2 FY2026 (03-18-2026)"), and the transcript filenames encode the same
# (company, quarter, year). See agent/corpus.py.
#
# READ-ONLY: this reads quant/*.csv and transcripts/; it writes only into agent/eval/.
#
# HOW TO RUN (from the project root)
#   python -X utf8 -m agent.eval.gold

import csv
import json
import os

from agent.corpus import find_document_for_label, list_documents

CALLS_FILE = "quant/calls.csv"                       # READ-ONLY
SIGNAL_FILE = "quant/signal_full_capacity.csv"       # READ-ONLY
OUT_FILE = "agent/eval/gold_set.json"

# The single mapping the human label uses: flag=1 means "this company said its own
# capacity is full / sold out / demand exceeds its supply". In the agent's schema
# that is exactly capacity_status == "sold_out".
POSITIVE_VALUE = "sold_out"


def load_gold(path: str = OUT_FILE):
    """Read the gold set back. Used by evaluate.py and ablate.py."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["rows"]


def build():
    with open(CALLS_FILE, encoding="utf-8-sig") as handle:
        calls = list(csv.DictReader(handle))
    with open(SIGNAL_FILE, encoding="utf-8-sig") as handle:
        signal_rows = list(csv.DictReader(handle))

    # calls.csv holds exactly one call per company, so a company-keyed flag is
    # unambiguous here. (Checked: 71 calls / 71 unique companies.)
    flagged = {row["company"]: row for row in signal_rows if row["flag"] == "1"}

    documents = list_documents()
    rows, unresolved = [], []
    for call in calls:
        document = find_document_for_label(call["source_label"], documents)
        if document is None or not document.is_full_transcript:
            unresolved.append(call)
            continue
        evidence = flagged.get(call["company"])
        rows.append({
            "company": call["company"],
            "ticker": call["ticker"],
            "date": call["date"],
            "source_label": call["source_label"],
            "doc_path": document.path,
            "doc_words": len(document.read().split()),
            "gold_flag": 1 if evidence else 0,
            # Carried through for error analysis: when the agent disagrees, we want
            # the owner's own quote and ruling next to it in the report.
            "gold_evidence": evidence["evidence"] if evidence else "",
            "gold_ruling": evidence["owner_ruling"] if evidence else "",
        })

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    payload = {
        "note": (
            "Gold set for the capacity signal. gold_flag=1 means the project owner "
            "ruled that the company said its own capacity is full/sold out/demand "
            f"exceeds supply. The agent's equivalent is capacity_status == '{POSITIVE_VALUE}'."
        ),
        "source_labels": {"universe": CALLS_FILE, "labels": SIGNAL_FILE},
        "positive_value": POSITIVE_VALUE,
        "n_rows": len(rows),
        "n_positive": sum(r["gold_flag"] for r in rows),
        "unresolved": [{"company": c["company"], "source_label": c["source_label"]}
                       for c in unresolved],
        "rows": rows,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    print(f"Wrote {OUT_FILE}")
    print(f"  rows          : {payload['n_rows']} of {len(calls)} calls")
    print(f"  positives     : {payload['n_positive']}")
    print(f"  negatives     : {payload['n_rows'] - payload['n_positive']}")
    if unresolved:
        print(f"  UNRESOLVED    : {len(unresolved)} (no full transcript in the corpus)")
        for call in unresolved:
            print(f"      {call['company']} -- {call['source_label']}")
    words = sorted(r["doc_words"] for r in rows)
    if words:
        print(f"  doc words     : min {words[0]}  median {words[len(words) // 2]}  max {words[-1]}")
    return payload


if __name__ == "__main__":
    build()
