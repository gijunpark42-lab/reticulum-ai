"""Apply a batch of DART enrichment entries to the chain files, ADD-only.

`enrich dart` can put dozens of Korean filings in the queue at once. Reading them
is delegated per company; the reader hands back a small JSON "patch" and THIS
script is the only thing that writes to chains/, so parallel readers can never
clobber each other's edits.

Patch shape (one file per company, e.g. dart/patches/skhynix.json):
{
  "company": "SK Hynix",                      # canonical node name
  "quarterly_data": [ {quarter, signal, figure, topics, slot?, capex?}, ... ],
  "edges": [                                   # optional
    {"company": "TSMC", "relationship": "...", "contracts": [ {source, signal, units, value, date_signed, type, topics} ]}
  ]
}

Rules enforced here:
  * quarterly_data goes on EVERY node with that company name (a company that sits in
    several chains gets the entry in each, like the manual workflow does).
  * an edge is added on the first node whose chain already holds the counterparty;
    its contracts are appended to an existing edge when one exists.
  * entries already present (same quarter + first 40 chars of signal) are skipped.
  * any Korean character in a label/signal/figure aborts the patch (English-only rule).

Usage:
    python dart_apply.py dart/patches/*.json
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CHAINS = sorted(ROOT.glob("chains/**/*.json"))
KOREAN = re.compile(r"[가-힣]")


def players(chain):
    for layer in chain.get("flow", []) + chain.get("domains", []):
        for sec in layer["sectors"]:
            for g in ([sec] if "players" in sec else sec.get("sub_sectors", [])):
                for p in g["players"]:
                    yield p


def check_english(obj, where):
    text = json.dumps(obj, ensure_ascii=False)
    hit = KOREAN.search(text)
    if hit:
        raise SystemExit(f"{where}: Korean character {text[hit.start():hit.start()+20]!r} -- chain entries must be English")


def apply(patch_path):
    patch = json.loads(Path(patch_path).read_text(encoding="utf-8"))
    company = patch["company"]
    check_english(patch.get("quarterly_data", []), patch_path)
    check_english(patch.get("edges", []), patch_path)

    added_q = added_c = added_e = 0
    nodes_hit = 0
    edge_done = {e["company"]: False for e in patch.get("edges", [])}

    for chain_path in CHAINS:
        chain = json.loads(chain_path.read_text(encoding="utf-8"))
        names = {p["company"] for p in players(chain)}
        if company not in names:
            continue
        touched = False
        for node in players(chain):
            if node["company"] != company:
                continue
            nodes_hit += 1
            have = {(q["quarter"], q["signal"][:40]) for q in node["quarterly_data"]}
            for q in patch.get("quarterly_data", []):
                if (q["quarter"], q["signal"][:40]) not in have:
                    node["quarterly_data"].append(q)
                    have.add((q["quarter"], q["signal"][:40]))
                    added_q += 1
                    touched = True
            for e in patch.get("edges", []):
                if edge_done[e["company"]] or e["company"] not in names:
                    continue
                target = next((x for x in node["connects_to"] if x["company"] == e["company"]), None)
                if target is None:
                    target = {"company": e["company"], "relationship": e["relationship"], "contracts": []}
                    node["connects_to"].append(target)
                    added_e += 1
                have_c = {(c["source"], c["signal"][:40]) for c in target["contracts"]}
                for c in e.get("contracts", []):
                    if (c["source"], c["signal"][:40]) not in have_c:
                        target["contracts"].append(c)
                        added_c += 1
                edge_done[e["company"]] = True
                touched = True
        if touched:
            chain_path.write_text(json.dumps(chain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    skipped_edges = [k for k, v in edge_done.items() if not v]
    print(f"{company:28s} nodes={nodes_hit} +{added_q} quarterly_data +{added_e} edges +{added_c} contracts"
          + (f"  (edge target not in any shared chain: {skipped_edges})" if skipped_edges else "")
          + ("  ** NODE NOT FOUND **" if not nodes_hit else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    paths = [p for a in sys.argv[1:] for p in glob.glob(a)]
    if not paths:
        raise SystemExit("usage: python dart_apply.py dart/patches/*.json")
    for p in paths:
        apply(p)
