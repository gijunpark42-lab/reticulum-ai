import json

with open("graph/merged_graph.json", encoding="utf-8") as f:
    g = json.load(f)

print("Sample nodes with metadata:")
for n in sorted(g["nodes"], key=lambda x: x["id"])[:8]:
    print(f'  {n["id"]:35s} ticker={str(n.get("ticker")):10s} country={n.get("country")} status={n.get("status")}')

missing = [n["id"] for n in g["nodes"] if not n.get("country")]
if missing:
    print(f"\nMissing metadata ({len(missing)}): {missing}")
else:
    print(f"\nAll {len(g['nodes'])} nodes have metadata.")
