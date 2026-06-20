# extract_calls.py — builds the UNCLASSIFIED call universe.
#
# After v1 signal taxonomy was rejected (no sector-adjusted edge), the base
# table is now simply: EVERY US-listed earnings call found in the graph,
# with no signal classification at all. Signal design happens later, on top
# of this table, with explicit owner sign-off for every rule.
#
# Output: quant/calls.csv — one row per (company, call date).
#
# HOW TO RUN (from the project root)
#   python -X utf8 quant/extract_calls.py

import json
import re
import csv

GRAPH_FILE = "graph/merged_graph.json"   # READ-ONLY
META_FILE = "company_metadata.json"      # READ-ONLY
OUT_FILE = "quant/calls.csv"

EARNINGS_LABEL = re.compile(r"Q\d\s*FY\s*\d{4}", re.I)
LABEL_DATE = re.compile(r"\((\d{2})-(\d{2})-(\d{4})\)")
US_EXCHANGES = {"NYSE", "NASDAQ"}


def main():
    with open(GRAPH_FILE, encoding="utf-8") as f:
        graph = json.load(f)
    with open(META_FILE, encoding="utf-8") as f:
        meta = json.load(f)
    meta.pop("_schema", None)

    us_ticker = {c: m["ticker"] for c, m in meta.items()
                 if isinstance(m, dict) and m.get("ticker")
                 and m.get("exchange") in US_EXCHANGES}

    # A node carries quarterly_data from MANY source documents — including other
    # companies' calls that merely mention it. Only the company's OWN call counts
    # as its event: the label's company prefix must match the node's name.
    # e.g. on the Google node, "Google Q1 FY2026 (...)" is Google's call, but
    # "Lumentum Q3 FY2026 (...)" is Lumentum's call quoting Google -> skip.
    def is_own_call(node_name, label):
        m = re.search(r"\sQ\d", label)
        if not m:
            return False
        prefix = label[:m.start()].strip().lower()
        name = node_name.lower()
        return name.startswith(prefix) or prefix.startswith(name)

    calls = {}   # (ticker, date) -> (company, label) — ticker dedupes sub-nodes
    for node in graph["nodes"]:
        company = node["id"]
        if company not in us_ticker:
            continue
        for qd in node.get("quarterly_data", []):
            label = qd.get("quarter") or ""
            if not EARNINGS_LABEL.search(label):
                continue   # GTC keynotes / news notes are not earnings calls
            if not is_own_call(company, label):
                continue   # someone else's call mentioning this company
            dm = LABEL_DATE.search(label)
            if not dm:
                continue
            date = f"{dm.group(3)}-{dm.group(1)}-{dm.group(2)}"
            # (ticker, date) key: "Intel" and "Intel Foundry" are both INTC —
            # one call, one event. Keep the shortest company name as canonical.
            key = (us_ticker[company], date)
            if key not in calls or len(company) < len(calls[key][0]):
                calls[key] = (company, label.strip())

    rows = [{"company": co, "ticker": t, "date": d, "source_label": lab}
            for (t, d), (co, lab) in sorted(calls.items(), key=lambda kv: kv[1][0])]
    with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "ticker", "date", "source_label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} calls ({len({r['company'] for r in rows})} companies) -> {OUT_FILE}")
    print(f"  date range: {min(r['date'] for r in rows)} .. {max(r['date'] for r in rows)}")


if __name__ == "__main__":
    main()
