"""Add NEW NODES and EDGES to chain files from a node patch, ADD-only.

The company patches applied by dart_apply.py could only attach edges to
counterparties that were already nodes in the same chain file. This script
takes a second kind of patch that introduces the missing counterparties as
nodes (placed in an existing layer/domain -> sector of ONE chain file) and then
wires the edges, in either direction.

Patch shape (dart/node_patches/<slug>.json):
{
  "chain": "chains/components/power_cooling.json",
  "nodes": [
    {"company": "NextEra Energy", "layer": "power", "sector": "Grid",   # layer = layer slug OR domain slug
     "product": "US utility buying UHV transformers for grid/data-center load"}
  ],
  "edges": [
    {"from": "LS Electric", "to": "NextEra Energy", "relationship": "UHV transformers (Safe Harbor project)",
     "contracts": [{"source": "...", "signal": "...", "units": "...", "value": "...",
                    "date_signed": "...", "type": "supply agreement", "topics": ["power_cooling"]}]}
  ]
}

Rules:
  * a node is added only if no player with that name exists anywhere in the chain file;
    the sector must already exist in that layer/domain (a sector holding sub_sectors takes
    the node in its first sub_sector unless "sub_sector" is given). Unknown layer/sector -> skipped, reported.
  * an edge is added on the `from` node (must exist in the chain after node adds); contracts
    are appended to an existing edge when one exists; duplicates (same source + first 40 chars) skipped.
  * Korean characters anywhere in the patch abort it.

Usage:
    python dart_apply_nodes.py dart/node_patches/*.json
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
KOREAN = re.compile(r"[가-힣]")


from taxonomy import LAYERS, DOMAINS  # canonical order, so a created layer lands in the right place

LAYER_ORDER = [slug for slug, *_ in LAYERS]
DOMAIN_SLUGS = {slug for slug, *_ in DOMAINS}


def ensure_layer(chain, slug):
    """Create an empty layer (in taxonomy order) or domain when the chain file lacks it."""
    if slug in DOMAIN_SLUGS:
        layer = {"domain": slug, "sectors": []}
        chain.setdefault("domains", []).append(layer)
        return layer
    if slug not in LAYER_ORDER:
        return None
    layer = {"layer": slug, "sectors": []}
    flow = chain.setdefault("flow", [])
    pos = next((i for i, l in enumerate(flow) if LAYER_ORDER.index(l["layer"]) > LAYER_ORDER.index(slug)), len(flow))
    flow.insert(pos, layer)
    return layer


def groups(chain):
    """Yield (layer_slug, sector_name, sub_sector_name_or_None, players_list)."""
    for layer in chain.get("flow", []) + chain.get("domains", []):
        slug = layer.get("layer") or layer.get("domain")
        for sec in layer["sectors"]:
            if "players" in sec:
                yield slug, sec["sector"], None, sec["players"]
            for sub in sec.get("sub_sectors", []):
                yield slug, sec["sector"], sub["sub_sector"], sub["players"]


def apply(path):
    patch = json.loads(Path(path).read_text(encoding="utf-8"))
    if KOREAN.search(json.dumps(patch, ensure_ascii=False)):
        raise SystemExit(f"{path}: Korean character in patch -- chain entries must be English")
    chain_path = ROOT / patch["chain"]
    chain = json.loads(chain_path.read_text(encoding="utf-8"))

    existing = {p["company"] for _, _, _, pl in groups(chain) for p in pl}
    added_nodes, skipped_nodes, created_sectors = [], [], set()
    for n in patch.get("nodes", []):
        if n["company"] in existing:
            continue
        target = None
        for slug, sector, sub, players in groups(chain):
            if slug == n["layer"] and sector == n["sector"] and (n.get("sub_sector") is None or sub == n.get("sub_sector")):
                target = players
                break
        if target is None and n.get("sub_sector") is None:
            # Sector missing in that layer/domain: create it, so customers/suppliers that have no
            # natural home in a chain (display makers, utilities' metal vendors) get a NAMED sector
            # instead of being forced into an unrelated one.
            layer = next((l for l in chain.get("flow", []) + chain.get("domains", [])
                          if (l.get("layer") or l.get("domain")) == n["layer"]), None)
            if layer is None:
                layer = ensure_layer(chain, n["layer"])
            if layer is not None:
                sec = {"sector": n["sector"], "players": []}
                layer["sectors"].append(sec)
                target = sec["players"]
                created_sectors.add(f"{n['layer']}/{n['sector']}")
        if target is None:
            skipped_nodes.append(f"{n['company']} ({n['layer']}/{n['sector']}/{n.get('sub_sector', '')})")
            continue
        target.append({"company": n["company"], "product": n["product"], "connects_to": [], "quarterly_data": []})
        existing.add(n["company"])
        added_nodes.append(n["company"])

    by_name = {p["company"]: p for _, _, _, pl in groups(chain) for p in pl}
    added_edges = added_contracts = 0
    skipped_edges = []
    for e in patch.get("edges", []):
        src, dst = by_name.get(e["from"]), e["to"]
        if src is None or dst not in by_name:
            skipped_edges.append(f"{e['from']} -> {dst}")
            continue
        edge = next((x for x in src["connects_to"] if x["company"] == dst), None)
        if edge is None:
            edge = {"company": dst, "relationship": e["relationship"], "contracts": []}
            src["connects_to"].append(edge)
            added_edges += 1
        have = {(c["source"], c["signal"][:40]) for c in edge["contracts"]}
        for c in e.get("contracts", []):
            if (c["source"], c["signal"][:40]) not in have:
                edge["contracts"].append(c)
                added_contracts += 1

    chain_path.write_text(json.dumps(chain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{Path(path).stem:28s} {patch['chain'].split('/')[-1]:28s} +{len(added_nodes)} nodes +{added_edges} edges +{added_contracts} contracts"
          + (f"  new sectors: {sorted(created_sectors)}" if created_sectors else "")
          + (f"  SKIPPED nodes: {skipped_nodes}" if skipped_nodes else "")
          + (f"  SKIPPED edges: {skipped_edges}" if skipped_edges else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    paths = [p for a in sys.argv[1:] for p in glob.glob(a)]
    if not paths:
        raise SystemExit("usage: python dart_apply_nodes.py dart/node_patches/*.json")
    for p in paths:
        apply(p)
