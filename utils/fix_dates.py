import json, os, re

# Quarter label -> correct label with US date format (MM-DD-YYYY)
DATE_FIXES = {
    "NVDA Q1 2027":         "NVDA Q1 2027 (05-20-2026)",
    "NVDA GTC Taipei 2026": "NVDA GTC Taipei 2026 (06-01-2026)",
    "Google Q1 2026":       "Google Q1 2026 (04-29-2026)",
    # already-dated versions (YYYY-MM-DD) -> convert to US format
    "NVDA Q1 2027 (2026-05-20)":         "NVDA Q1 2027 (05-20-2026)",
    "NVDA GTC Taipei 2026 (2026-06-01)": "NVDA GTC Taipei 2026 (06-01-2026)",
    "Google Q1 2026 (2026-04-29)":       "Google Q1 2026 (04-29-2026)",
    "Broadcom Q2 2026 (2026-06-03)":     "Broadcom Q2 2026 (06-03-2026)",
}

def fix_labels(obj):
    if isinstance(obj, dict):
        for key in ("quarter", "source"):
            if key in obj and obj[key] in DATE_FIXES:
                obj[key] = DATE_FIXES[obj[key]]
        for v in obj.values():
            fix_labels(v)
    elif isinstance(obj, list):
        for item in obj:
            fix_labels(item)

for fname in sorted(os.listdir("chains")):
    if not fname.endswith(".json"):
        continue
    path = f"chains/{fname}"
    with open(path, encoding="utf-8") as f:
        chain = json.load(f)

    before = json.dumps(chain)
    fix_labels(chain)
    after = json.dumps(chain)

    if before != after:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chain, f, indent=2, ensure_ascii=False)
        print(f"Updated: {fname}")
    else:
        print(f"No change: {fname}")
