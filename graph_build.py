import os
import json

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

    for filename in sorted(os.listdir(chains_dir)):
        if not filename.endswith(".json"):
            continue

        chain_name = filename.replace(".json", "")  # e.g. "nvidia_vera_rubin"
        filepath = os.path.join(chains_dir, filename)

        with open(filepath, encoding="utf-8") as f:
            chain = json.load(f)

        print(f"  Reading: {filename}")

        for tier_obj in chain["flow"]:
            tier = tier_obj["tier"]

            for player in tier_obj["players"]:
                company = player["company"]

                # First time we see this company → create its node
                if company not in nodes:
                    meta = metadata.get(company, {})
                    nodes[company] = {
                        "id": company,
                        "tiers": [],
                        "chains": [],
                        "products": [],
                        "quarterly_data": [],
                        # metadata fields (null if not in company_metadata.json)
                        "ticker":   meta.get("ticker"),
                        "exchange": meta.get("exchange"),
                        "country":  meta.get("country"),
                        "status":   meta.get("status", "public"),
                    }

                # Add tier (a company can play different roles in different chains)
                if tier not in nodes[company]["tiers"]:
                    nodes[company]["tiers"].append(tier)

                # Add chain source
                if chain_name not in nodes[company]["chains"]:
                    nodes[company]["chains"].append(chain_name)

                # Record this specific product role
                nodes[company]["products"].append({
                    "chain": chain_name,
                    "tier": tier,
                    "product": player["product"]
                })

                # Merge all quarterly_data entries (tag each with chain source)
                for entry in player.get("quarterly_data", []):
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
