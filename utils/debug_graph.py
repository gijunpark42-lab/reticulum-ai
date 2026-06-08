import json

with open("chains/nvidia_vera_rubin.json", encoding="utf-8") as f:
    chain = json.load(f)

# collect all node IDs
node_ids = set()
for tier in chain["flow"]:
    for p in tier["players"]:
        node_ids.add(p["company"])

print("=== ALL NODES ===")
for n in sorted(node_ids):
    print(" ", n)

print()
print("=== BROKEN EDGES (target not in nodes) ===")
for tier in chain["flow"]:
    for p in tier["players"]:
        for e in p.get("connects_to", []):
            if e["company"] not in node_ids:
                print(f"  {p['company']} --> {e['company']}  [MISSING]")

print()
print("=== ISOLATED NODES (no in or out edges) ===")
connected = set()
for tier in chain["flow"]:
    for p in tier["players"]:
        if p.get("connects_to"):
            connected.add(p["company"])
            for e in p["connects_to"]:
                connected.add(e["company"])

for n in sorted(node_ids):
    if n not in connected:
        print(" ", n, "- no edges at all")
