import json, os

all_names = {}

for fname in sorted(os.listdir("chains")):
    if not fname.endswith(".json"):
        continue
    with open(f"chains/{fname}", encoding="utf-8") as f:
        chain = json.load(f)
    for tier in chain["flow"]:
        for p in tier["players"]:
            all_names.setdefault(p["company"], [])
            if fname not in all_names[p["company"]]:
                all_names[p["company"]].append(fname)
            for e in p.get("connects_to", []):
                all_names.setdefault(e["company"], [])
                if fname not in all_names[e["company"]]:
                    all_names[e["company"]].append(fname)

print("=== ALL COMPANY NAMES ===")
for name in sorted(all_names.keys()):
    files = ", ".join(all_names[name])
    print(f"  {name:45s} {files}")
