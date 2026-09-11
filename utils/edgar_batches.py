"""Split the `enrich edgar` queue into N batches for parallel agents (completeness contract, rule 6).

Every company's rows stay together (one agent owns one company, so two agents never write about the same node), and
batches are balanced by how many bytes each agent has to read.

    python -X utf8 utils/edgar_batches.py 9                         # edgar/pending.json -> edgar/batches/batch_01.json ...
    python -X utf8 utils/edgar_batches.py 9 extra_rows.json         # also add rows from another list (e.g. delta rows)

A row may carry its own reading file under "delta" (text a previous pass did not read); its size is used instead.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N = int(sys.argv[1])

rows = json.loads((ROOT / "edgar" / "pending.json").read_text(encoding="utf-8"))
for extra in sys.argv[2:]:
    rows += json.loads(Path(extra).read_text(encoding="utf-8"))
for r in rows:
    read_file = r.get("delta") or (ROOT / r["file"])
    r["bytes"] = os.path.getsize(read_file)

# group by company, then greedily put the biggest company into the lightest batch
groups = {}
for r in rows:
    groups.setdefault(r["company"], []).append(r)
batches = [{"rows": [], "bytes": 0} for _ in range(N)]
for company, company_rows in sorted(groups.items(), key=lambda kv: -sum(x["bytes"] for x in kv[1])):
    lightest = min(batches, key=lambda b: b["bytes"])
    lightest["rows"].extend(company_rows)
    lightest["bytes"] += sum(x["bytes"] for x in company_rows)

out_dir = ROOT / "edgar" / "batches"
out_dir.mkdir(parents=True, exist_ok=True)
for old in out_dir.glob("batch_*.json"):
    old.unlink()                                   # a new split replaces the previous one
for i, b in enumerate(batches, 1):
    if not b["rows"]:
        continue
    b["rows"].sort(key=lambda x: (x["company"], x.get("kind", "filing"), x["file"]))
    (out_dir / f"batch_{i:02d}.json").write_text(json.dumps(b["rows"], indent=1, ensure_ascii=False), encoding="utf-8")
    companies = sorted({x["company"] for x in b["rows"]})
    print(f"batch_{i:02d}: {len(b['rows'])} rows, {b['bytes'] / 1000:.0f} kB, {len(companies)} companies: {', '.join(companies)}")
print(f"total {len(rows)} rows, {len(groups)} companies -> {out_dir}")
