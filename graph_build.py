import os
import json

from taxonomy import iter_players  # the one shared layer/sector/domain walker

# Read all chain files in chains/ and merge by company name into one flat graph.
# Original chain files are never modified — this only writes to graph/merged_graph.json.
# To revert: delete graph/merged_graph.json and re-run.

METADATA_PATH = "company_metadata.json"

def load_metadata():
    """Load company_metadata.json if it exists, else return empty dict."""
    if not os.path.exists(METADATA_PATH):
        return {}
    with open(METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)

def build_graph(chains_dir="chains", output_path="graph/merged_graph.json"):
    metadata = load_metadata()
    nodes = {}  # key: company name → merged node data
    edges = []  # flat list of all directed edges across all chains

    # discover chain files recursively — chains/ may be organized into sub-folders
    # (e.g. chains/accelerators/, chains/components/). The chain id is still the
    # filename stem, so sub-foldering does not change node/edge data or colors.
    chain_files = []
    for _root, _dirs, _files in os.walk(chains_dir):
        for _fn in _files:
            if _fn.endswith(".json"):
                chain_files.append(os.path.join(_root, _fn))

    for filepath in sorted(chain_files):
        filename = os.path.basename(filepath)
        chain_name = filename.replace(".json", "")  # e.g. "nvidia_vera_rubin"

        with open(filepath, encoding="utf-8") as f:
            chain = json.load(f)

        print(f"  Reading: {filename}")

        # iter_players walks flow[] (layers) AND domains[] at any nesting depth, so
        # graph_build never re-implements the 4-deep loop. kind is "layer" or "domain".
        for player, slug, kind, sector, sub_sector in iter_players(chain):
                company = player["company"]

                # First time we see this company → create its node
                if company not in nodes:
                    meta = metadata.get(company, {})
                    nodes[company] = {
                        "id": company,
                        "layers": [],    # layer slugs this company plays in
                        "domains": [],   # cross-cutting domain slugs (power/thermal/…)
                        "sectors": [],   # sector strings across all its roles
                        "chains": [],
                        "products": [],
                        "quarterly_data": [],
                        # metadata fields (null if not in company_metadata.json)
                        "ticker":   meta.get("ticker"),
                        "exchange": meta.get("exchange"),
                        "country":  meta.get("country"),
                        "status":   meta.get("status", "public"),
                    }

                # Add layer/domain slug (a company can play different roles in different chains)
                group_field = "layers" if kind == "layer" else "domains"
                if slug not in nodes[company][group_field]:
                    nodes[company][group_field].append(slug)

                # Add sector (free string)
                if sector and sector not in nodes[company]["sectors"]:
                    nodes[company]["sectors"].append(sector)

                # Add chain source
                if chain_name not in nodes[company]["chains"]:
                    nodes[company]["chains"].append(chain_name)

                # Record this specific product role
                nodes[company]["products"].append({
                    "chain": chain_name,
                    "layer": slug if kind == "layer" else None,
                    "domain": slug if kind == "domain" else None,
                    "sector": sector,
                    "sub_sector": sub_sector,
                    "product": player["product"]
                })

                # Merge all quarterly_data entries (tag each with chain source).
                # Dedupe by (quarter, signal): a company that appears in several
                # chains often carries the same company-level figure in each, which
                # must not be double-counted in the merged node.
                _seen_qd = {(q.get("quarter"), q.get("signal"))
                            for q in nodes[company]["quarterly_data"]}
                for entry in player.get("quarterly_data", []):
                    key = (entry.get("quarter"), entry.get("signal"))
                    if key in _seen_qd:
                        continue
                    _seen_qd.add(key)
                    entry_with_chain = dict(entry)
                    entry_with_chain["chain"] = chain_name
                    nodes[company]["quarterly_data"].append(entry_with_chain)

                # Build edges — one edge object per connects_to entry
                for edge in player.get("connects_to", []):
                    # Skip self-loops (TSMC → TSMC from epiwafer → packaging)
                    if edge["company"] == company:
                        continue
                    edges.append({
                        "source": company,
                        "target": edge["company"],
                        "relationship": edge["relationship"],
                        "contracts": edge.get("contracts", []),
                        "chain": chain_name  # which chain this edge came from
                    })

    # Write merged graph
    graph = {
        "nodes": list(nodes.values()),
        "edges": edges
    }

    os.makedirs("graph", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\nSaved to {output_path}")
    print(f"Total nodes : {len(nodes)}")
    print(f"Total edges : {len(edges)}")

    # Show hub nodes — companies that appear in 2+ chains
    hubs = [n for n in nodes.values() if len(n["chains"]) >= 2]
    print(f"\nHub nodes ({len(hubs)} companies shared across 2+ chains):")
    for h in sorted(hubs, key=lambda x: len(x["chains"]), reverse=True):
        print(f"  {h['id']:30s} chains: {h['chains']}")

    return graph


if __name__ == "__main__":
    print("Building merged graph from all chain files...\n")
    build_graph()
