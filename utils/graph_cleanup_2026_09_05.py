"""
graph_cleanup_2026_09_05.py -- one-off structural cleanup of chains/ (run once on 2026-09-05).

Why this exists
---------------
The 2026-08-29 "DART counterparties" import turned EVERY customer / supplier named in the
Korean half-year reports into a graph node (banks, display-panel makers, rail contractors,
steel machine shops, foreign utilities ...). Most of them fail the CLAUDE.md litmus test
("does this company's stock directly benefit from the product being built and sold?"), and
several were parked in layers that do not describe them (a substrate maker under
compute_hardware, GPUs under interconnect). This script applies a reviewed decision table:

  REMOVE   - the player is deleted. Nothing filed is lost: every contract on an edge to or
             from it is FOLDED into the counterpart's own quarterly_data (the rule CLAUDE.md
             already uses when a DART counterparty is not a node).
  MOVE     - the player is moved to the layer/sector that describes its role. All data rides along.
  MERGE    - two cards for one company in one chain become one card (edges + data unioned).
  RENAME   - a subsidiary / brand is folded into the canonical listed parent (naming rules).
  SECTOR   - a sector created by the import is renamed to the name the other chains use.
  PRODUCT  - a boiler-plate product string is replaced by a specific one.

The engine is generic; the decision table at the bottom (ACTIONS) is the review itself.
Revert point: git branch `pre-cleanup-2026-09-05` (the commit before this ran).

How to read the code (for the builder)
--------------------------------------
* A chain file is  flow[] -> layer -> sectors[] -> (sub_sectors[]) -> players[]  plus an
  optional domains[] block of the same shape. `walk()` yields every player together with the
  LIST that holds it, so we can pop it out of one place and append it somewhere else.
* We never touch the merged graph directly; graph_build.py rebuilds it from chains/ afterwards.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from taxonomy import LAYER_ORDER, DOMAINS            # canonical layer order / domain order
from apply_patches import load_chain, save_chain     # keeps each file's newline style

CHAINS_DIR = os.path.join(ROOT, "chains")
DOMAIN_ORDER = {slug: i for i, (slug, *_r) in enumerate(DOMAINS)}
EMPTY = {"", "no specific figure", "not stated", "n/a", "-"}

FOLD_LOG = []      # (chain, owner, role, counterpart, label) -- one line per folded contract
REPORT = []        # human-readable log lines


def log(msg):
    REPORT.append(msg)
    print(msg)


# ---------------------------------------------------------------------------
# Walking a chain
# ---------------------------------------------------------------------------

def walk(chain):
    """Yield (holder_list, index, player, kind, group_slug, sector, sub_sector) for every player.

    holder_list is the actual Python list the player sits in, so callers can mutate it.
    kind is "layer" or "domain"."""
    for kind, key in (("layer", "flow"), ("domain", "domains")):
        for group in chain.get(key, []):
            slug = group.get(kind)
            for sec in group.get("sectors", []):
                for sub in sec.get("sub_sectors", []):
                    for i, p in enumerate(sub.get("players", [])):
                        yield sub["players"], i, p, kind, slug, sec.get("sector"), sub.get("sub_sector")
                for i, p in enumerate(sec.get("players", [])):
                    yield sec["players"], i, p, kind, slug, sec.get("sector"), None


def find(chain, company, group=None, sector=None):
    """All placements of `company`, optionally narrowed to a group slug and/or sector name."""
    out = []
    for holder, i, p, kind, slug, sec, sub in walk(chain):
        if p["company"] != company:
            continue
        if group and slug != group:
            continue
        if sector and sec != sector:
            continue
        out.append((holder, i, p, kind, slug, sec, sub))
    return out


def find_one(chain, company, group=None, sector=None):
    hits = find(chain, company, group, sector)
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one {company!r} (group={group}, sector={sector}), found {len(hits)}")
    return hits[0]


def ensure_sector(chain, kind, slug, sector):
    """Return the sector dict for (kind, slug, sector), creating the group and/or sector if
    needed. New layers are inserted at their canonical position so the column order stays right."""
    key = "flow" if kind == "layer" else "domains"
    order = LAYER_ORDER if kind == "layer" else DOMAIN_ORDER
    groups = chain.setdefault(key, [])
    group = next((g for g in groups if g.get(kind) == slug), None)
    if group is None:
        group = {kind: slug, "sectors": []}
        pos = next((i for i, g in enumerate(groups) if order.get(g.get(kind), 999) > order.get(slug, 999)), len(groups))
        groups.insert(pos, group)
    sec = next((s for s in group["sectors"] if s.get("sector") == sector), None)
    if sec is None:
        sec = {"sector": sector, "players": []}
        group["sectors"].append(sec)
    sec.setdefault("players", [])
    return sec


def prune(chain):
    """Drop sub-sectors / sectors / groups that ended up with no players."""
    for key in ("flow", "domains"):
        for group in chain.get(key, []):
            for sec in group.get("sectors", []):
                if "sub_sectors" in sec:
                    sec["sub_sectors"] = [s for s in sec["sub_sectors"] if s.get("players")]
                    if not sec["sub_sectors"]:
                        del sec["sub_sectors"]
            group["sectors"] = [s for s in group.get("sectors", [])
                                if s.get("players") or s.get("sub_sectors")]
        chain[key] = [g for g in chain.get(key, []) if g.get("sectors")]
        if not chain[key]:
            del chain[key]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def informative(text):
    return (text or "").strip().lower() not in EMPTY


def add_qd(player, entry):
    """Append a quarterly_data entry unless the same (quarter, signal) is already there."""
    seen = {(q.get("quarter"), q.get("signal")) for q in player.setdefault("quarterly_data", [])}
    if (entry["quarter"], entry["signal"]) in seen:
        return False
    player["quarterly_data"].append(entry)
    return True


def merge_edge(player, edge):
    """Add `edge` to player.connects_to, merging contracts if the target already exists."""
    for e in player.setdefault("connects_to", []):
        if e["company"] == edge["company"]:
            seen = {(c.get("source"), c.get("signal")) for c in e.setdefault("contracts", [])}
            for c in edge.get("contracts", []):
                if (c.get("source"), c.get("signal")) not in seen:
                    e["contracts"].append(c)
            return
    player["connects_to"].append(edge)


def fold_contract(chain_name, owner, counterpart, role, contract):
    """Turn one edge contract into a node-level quarterly_data entry on `owner`.

    role is how the counterpart relates to the owner: "Customer" or "Supplier"."""
    parts = [contract.get(k) for k in ("value", "units") if informative(contract.get(k))]
    figure = "; ".join(parts) if parts else "no specific figure"
    tail = []
    if informative(contract.get("type")):
        tail.append(contract["type"])
    if informative(contract.get("date_signed")):
        tail.append("signed " + contract["date_signed"])
    signal = f"{role} {counterpart}: {contract.get('signal', '')}"
    if tail:
        signal += f" [{'; '.join(tail)}]"
    entry = {
        "quarter": contract.get("source", ""),
        "signal": signal,
        "figure": figure,
        "topics": list(contract.get("topics", [])),
        "counterparty": counterpart,
        "counterparty_role": role.lower(),
    }
    if add_qd(owner, entry):
        FOLD_LOG.append((chain_name, owner["company"], role.lower(), counterpart, entry["quarter"]))


# ---------------------------------------------------------------------------
# The six operations
# ---------------------------------------------------------------------------

def op_remove(chain, chain_name, company, group=None, sector=None):
    holder, i, player, kind, slug, sec, sub = find_one(chain, company, group, sector)
    if player.get("quarterly_data"):
        raise SystemExit(f"refusing to remove {company!r} in {chain_name}: it carries its own quarterly_data")
    # 1) edges going OUT of the removed player -> fold into each target (the target's supplier is gone)
    for edge in player.get("connects_to", []):
        targets = find(chain, edge["company"])
        if not targets:
            raise SystemExit(f"{company!r} -> {edge['company']!r}: target is not in {chain_name}, cannot fold")
        target = targets[0][2]
        for c in edge.get("contracts", []):
            fold_contract(chain_name, target, company, "Supplier", c)
    # 2) edges coming IN from other players -> fold into the source, then drop the edge
    for h2, j, other, *_r in list(walk(chain)):
        if other is player:
            continue
        keep = []
        for edge in other.get("connects_to", []):
            if edge["company"] == company:
                for c in edge.get("contracts", []):
                    fold_contract(chain_name, other, company, "Customer", c)
            else:
                keep.append(edge)
        if "connects_to" in other:
            other["connects_to"] = keep
    del holder[i]
    log(f"  REMOVE  {company}  ({slug}/{sec})")


def op_move(chain, chain_name, company, from_group, from_sector, to_kind, to_group, to_sector):
    holder, i, player, *_r = find_one(chain, company, from_group, from_sector)
    del holder[i]
    ensure_sector(chain, to_kind, to_group, to_sector)["players"].append(player)
    log(f"  MOVE    {company}  {from_group}/{from_sector}  ->  {to_group}/{to_sector}")


def op_merge(chain, chain_name, company, keep_group, keep_sector, drop_group, drop_sector, product=None):
    _h, _i, keep, *_r = find_one(chain, company, keep_group, keep_sector)
    holder, i, drop, *_r = find_one(chain, company, drop_group, drop_sector)
    for edge in drop.get("connects_to", []):
        merge_edge(keep, edge)
    for q in drop.get("quarterly_data", []):
        add_qd(keep, q)
    if product:
        keep["product"] = product
    del holder[i]
    log(f"  MERGE   {company}  {drop_group}/{drop_sector}  into  {keep_group}/{keep_sector}")


def op_rename(chain, chain_name, old, new, product=None):
    """Rename a player; if `new` already exists in the chain the old card is merged into it.
    Every edge in the chain that pointed at `old` is re-pointed at `new`."""
    hits = find(chain, old)
    if len(hits) != 1:
        raise SystemExit(f"rename {old!r}: found {len(hits)} placements in {chain_name}")
    holder, i, player, kind, slug, sec, sub = hits[0]
    existing = find(chain, new)
    if existing:
        target = existing[0][2]
        for edge in player.get("connects_to", []):
            merge_edge(target, edge)
        for q in player.get("quarterly_data", []):
            add_qd(target, q)
        if product:
            target["product"] = product
        del holder[i]
        how = f"merged into existing {new!r} ({existing[0][4]}/{existing[0][5]})"
    else:
        player["company"] = new
        if product:
            player["product"] = product
        how = "renamed in place"
    for _h, _j, other, *_r in walk(chain):
        edges = other.get("connects_to", [])
        for edge in list(edges):
            if edge["company"] == old:
                edges.remove(edge)
                if other["company"] != new:           # never create a self-loop
                    merge_edge(other, dict(edge, company=new))
    log(f"  RENAME  {old}  ->  {new}  ({how})")


def op_sector(chain, chain_name, kind, group, old, new):
    key = "flow" if kind == "layer" else "domains"
    grp = next(g for g in chain.get(key, []) if g.get(kind) == group)
    old_sec = next(s for s in grp["sectors"] if s.get("sector") == old)
    new_sec = next((s for s in grp["sectors"] if s.get("sector") == new), None)
    if new_sec is None:
        old_sec["sector"] = new
    else:
        new_sec.setdefault("players", []).extend(old_sec.get("players", []))
        old_sec["players"] = []
    log(f"  SECTOR  {group}: {old!r} -> {new!r}")


def op_product(chain, chain_name, company, group, sector, product):
    _h, _i, player, *_r = find_one(chain, company, group, sector)
    log(f"  PRODUCT {company}: {player.get('product')!r} -> {product!r}")
    player["product"] = product


OPS = {"remove": op_remove, "move": op_move, "merge": op_merge,
       "rename": op_rename, "sector": op_sector, "product": op_product}


# ---------------------------------------------------------------------------
# THE DECISION TABLE  (reviewed by hand on 2026-09-05 -- the "why" is in the report)
# ---------------------------------------------------------------------------

def R(*names):
    """Shorthand: plain removals by name."""
    return [("remove", n) for n in names]


ACTIONS = {
    # ---- accelerators -------------------------------------------------------------------
    "accelerators/nvidia_vera_rubin.json": R(
        # Naver Cloud's public-sector / overseas platform customers: not AI supply-chain participants
        "Bank of Korea", "Korea Hydro & Nuclear Power", "Saudi NHC Innovation",
    ),

    # ---- components ---------------------------------------------------------------------
    "components/hbm_memory.json": R(
        # display / battery customers of Korean chemical & equipment makers (non-semiconductor)
        "LG Display", "Samsung Display", "Samsung SDI",
        # component distributors in Samsung's top-5 customer table
        "Hong Kong Techtronics", "Supreme Electronics",
        # IDMs / device makers that appear only as buyers of non-HBM back-end equipment or as
        # Samsung DX (phone) suppliers -- they stay hubs in the chains where they have an AI role
        "Texas Instruments", "Infineon", "STMicroelectronics", "Skyworks", "Intel",
        "Apple", "Qualcomm", "Kioxia", "Yangtze Memory Technologies",
        # obscure test / EMS houses and related-party machine shops
        "Luxshare", "Yilining Precision", "Unimos Microelectronics",
        "MC Solution", "Materials Park", "Partron", "Dasom Tech", "Nano Ace", "Trutech", "Wonik Corp",
    ) + [
        # MediaTek keeps its own HBM comment -> keep the node, but as a chipmaker, not a "Mobile SoC & Device Maker"
        ("move", "MediaTek", "compute_hardware", "Mobile SoC & Device Makers",
                 "layer", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)"),
        ("product", "MediaTek", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)",
                    "AI accelerator ASICs (HBM buyer); Dimensity mobile APs supplied to Samsung DX"),
        # substrate maker was filed under Training GPU
        ("move", "Ibiden", "compute_hardware", "Training GPU", "layer", "advanced_packaging", "FC-BGA Substrate"),
        # TSMC's CoWoS is wafer-level packaging, not HBM stacking; sector name used by every other chain
        ("sector", "layer", "advanced_packaging", "HBM Stacking & Bonding", "Wafer-Level Packaging (CoWoS, SoIC)"),
        ("sector", "layer", "software_infra", "EDA & IP Vendors", "EDA / Design Tools"),
    ],

    "components/cpu_datacenter.json": [
        ("move", "Unimicron", "compute_hardware", "Server CPU", "layer", "advanced_packaging", "FC-BGA Substrate"),
        ("move", "Intel", "advanced_packaging", "Wafer-Level Packaging (CoWoS, SoIC)", "layer", "compute_hardware", "Server CPU"),
        ("move", "Arista", "interconnect", "Components", "layer", "interconnect", "Scale-out"),
    ],

    "components/neocloud.json": [
        ("move", "AMD", "interconnect", "Components", "layer", "compute_hardware", "Training GPU"),
    ],

    "components/power_semiconductor.json": [
        ("move", "NVIDIA", "interconnect", "Components", "layer", "compute_hardware", "Training GPU"),
        ("move", "AMD", "interconnect", "Components", "layer", "compute_hardware", "Training GPU"),
        ("move", "Cerebras", "interconnect", "Components", "layer", "compute_hardware", "Dedicated Inference Accelerators"),
    ],

    "components/optical_networking.json": [
        ("move", "Anthropic", "cloud_infra", "Neocloud (GPU-specialized)", "layer", "ai_models", "Foundation Models"),
        ("move", "Marvell", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)", "layer", "interconnect", "Components"),
        ("move", "Broadcom", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)", "layer", "compute_hardware", "Networking ASIC"),
        ("move", "Celestial AI", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)", "layer", "interconnect", "Scale-up"),
        ("move", "Ranovus", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)", "layer", "interconnect", "Scale-up"),
        ("merge", "MediaTek", "compute_hardware", "Networking ASIC", "interconnect", "Components"),
        ("move", "NVIDIA", "interconnect", "Components", "layer", "interconnect", "Scale-out"),
        ("move", "Lumen Technologies", "interconnect", "Components", "layer", "interconnect", "Scale-across"),
    ],

    "components/mlcc.json": [
        ("move", "Sakai Chemical Industry", "materials", "Substrate Materials (ABF/BT)", "layer", "materials", "Passive Component Materials"),
        ("move", "Nippon Chemical Industrial", "materials", "Substrate Materials (ABF/BT)", "layer", "materials", "Passive Component Materials"),
    ],

    "components/power_cooling.json": R(
        # utilities / grid operators with no AI-datacenter angle (generic transformer buyers)
        "KEPCO", "Korea Midland Power", "Korea Southern Power", "Korea Hydro & Nuclear Power", "KAPES",
        "Saudi Electricity Company", "National Grid", "Statnett", "AusNet", "Eskom", "NSW Electricity",
        # IPP / BESS project companies and renewables developers
        "Jabel Power", "Coastal Power", "Jumin Sandeulbaram Power", "LS Power", "Tangkam BESS",
        "Burnley BESS", "Hanwha Q Cells",
        # EPC / construction contractors
        "HL D&I Halla", "Semco Maritime", "Algihaz Contracting Company", "Burns & McDonnell", "Samsung E&C",
        # rail, shipbuilding and industrial customers
        "HD Hyundai Heavy Industries", "HD Construction Equipment", "Hanwha Ocean", "ST Engineering",
        "Hyundai Rotem", "Bombardier Transportation",
        # transformer-tank steel, castings, bushings and wire from small private fabricators / traders
        "Tuwaiq Casting & Forging", "Shinhyun Electric", "Changsung Precision", "Hitech&Sol", "Taeyang Electric",
        "Daehwa Precision", "Samdong", "Sungdo Hitech", "TC Materials", "DY Electric", "Hanbit KSE", "Luxco",
        "POSCO Mobility Solution", "Goa Precision", "Joincore", "JFE Shoji Trade", "Kumkang Steel",
        "Encross", "DSE", "LS MnM",
        # non-AI buyers filed under Datacenter Power
        "LG Energy Solution", "Samsung SDI", "Power Electronics", "TMEIC USA", "CTC Property", "EPC Power Corporation",
        # Samsung as a fab-substation end customer does not belong in power/Grid (deal folded into HD Hyundai Electric)
        "Samsung",
    ) + [
        # empty duplicate card (Infineon already sits in power/Power Semiconductors with its data)
        ("remove", "Infineon", "materials", "SiC Wafers"),
        # keep the utilities that ARE the AI-load story together in one sector
        ("move", "Exelon", "power", "Grid", "domain", "power", "Utilities & Grid Operators"),
        # the three kept raw-material suppliers carried copy-pasted boiler-plate product text
        ("product", "POSCO", "power", "Power Equipment Components & Materials",
                    "electrical steel and steel plate for transformer cores and tanks (HD Hyundai Electric / Hyosung Heavy / Sanil Electric supplier)"),
        ("product", "Maschinenfabrik Reinhausen", "power", "Power Equipment Components & Materials",
                    "on-load tap changers, bushings and insulation components for power transformers (HD Hyundai Electric supplier)"),
        ("product", "Taihan Cable", "power", "Power Equipment Components & Materials",
                    "winding conductor and power cable for transformers (HD Hyundai Electric supplier)"),
    ],

    # ---- manufacturing ------------------------------------------------------------------
    "manufacturing/foundry.json": R(
        "LG Display", "Samsung Display", "BOE", "CSOT",          # display fabs buying Dongjin chemicals
        "Siemens Healthineers",                                  # ultrasound probes (Leeno)
        # photoresist raw-material traders / affiliates of Dongjin Semichem
        "PURAC Asia Pacific", "Ashland", "Samyang NC Chem", "Dongjin Advanced Materials",
        "Jaewon Industrial", "Tokyo Electronic Materials",
        "SKC",                                                   # shareholder / lessor of ISC, not a supplier
        "BOS Semiconductor",                                     # automotive fabless (AD Technology customer)
        "Leeno Precision",                                       # related-party machining affiliate
    ) + [
        # Siemens EDA is a division of Siemens (already a node) -> canonical parent name, keeps its data
        ("rename", "Siemens Industry Software", "Siemens",
                   "Siemens EDA (Mentor) design software; custom ASIC design-services customer of AD Technology"),
        ("sector", "layer", "software_infra", "EDA & IP Vendors", "EDA / Design Tools"),
        # two AMD cards (GPU die + 'platform systems' under interconnect) -> one
        ("merge", "AMD", "compute_hardware", "Training GPU", "interconnect", "Components",
                  "Instinct MI300/MI350 GPU accelerators and MI300X platform systems"),
    ],

    "manufacturing/packaging_substrate.json": R(
        # Samsung Electro-Mechanics' phone / automotive customers, distributors and camera-module inputs
        "Xiaomi", "Bosch", "Continental", "Rutronik", "Future Electronics", "Sony", "Tesla",
        "Haesung Optics", "Actro", "Toray", "Cosmo", "Guangbo",
        # small-share laminate / foil / plating inputs (traders, affiliates, non-core suppliers)
        "LG Chem", "Lotte Energy Materials", "Circuit Foil Luxembourg", "Mitsui & Co.", "Heesung Catalysts",
        "DNP Corporation",
    ) + [
        ("rename", "PTI", "Powertech Technology",
                   "OSAT (memory packaging) - package substrate buyer (Simmtech 'Big 5' packaging customer)"),
        ("rename", "STATS ChipPAC", "JCET",
                   "OSAT (incl. JCET STATS ChipPAC Korea) - package substrate buyer from Simmtech and Daeduck Electronics"),
        ("rename", "Atotech", "MKS Instruments"),
        ("rename", "Atotech Korea", "MKS Instruments"),
        ("rename", "Doosan Electronics", "Doosan Corporation",
                   "copper-clad laminate (CCL), thin-core and prepreg for package substrates and AI-server PCBs (Electro-Materials BG, 'Doosan Electronics')"),
        ("rename", "Taiyo Ink Products", "Taiyo Holdings",
                   "solder-resist ink and substrate process materials (Taiyo Ink) - Daeduck Electronics / Simmtech supplier"),
        # wrong layers
        ("move", "Samsung Electro-Mechanics", "compute_hardware", "Server CPU", "layer", "advanced_packaging", "FC-BGA Substrate"),
        ("move", "Intel", "compute_hardware", "IDM / Other Chipmakers", "layer", "compute_hardware", "Server CPU"),
        ("move", "Simmtech", "memory", "HBM", "layer", "advanced_packaging", "FC-BGA Substrate"),
        ("move", "AT&S", "interconnect", "Components", "layer", "advanced_packaging", "FC-BGA Substrate"),
        ("move", "AMD", "interconnect", "Components", "layer", "compute_hardware", "Training GPU"),
        ("move", "Google", "interconnect", "Components", "layer", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)"),
        ("move", "Tokyo Electron", "equipment", "Metrology / Inspection", "layer", "equipment", "Advanced Packaging Equipment"),
    ],
}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run():
    for rel, actions in ACTIONS.items():
        path = os.path.join(CHAINS_DIR, rel)
        chain, crlf = load_chain(path)
        log(f"\n{rel}")
        for act in actions:
            OPS[act[0]](chain, rel, *act[1:])
        prune(chain)
        # sanity: no edge may point at a company that is no longer in the graph. Cross-chain
        # targets are fine (the merged graph resolves them) -- we only check the names we removed.
        removed = {a[1] for a in actions if a[0] == "remove"} | {a[1] for a in actions if a[0] == "rename"}
        for _h, _i, p, *_r in walk(chain):
            for e in p.get("connects_to", []):
                if e["company"] in removed:
                    raise SystemExit(f"{rel}: dangling edge {p['company']} -> {e['company']}")
        save_chain(path, chain, crlf)

    out = os.path.join(ROOT, "utils", "graph_cleanup_2026_09_05.fold_log.tsv")
    with open(out, "w", encoding="utf-8") as f:
        f.write("chain\towner\trole\tcounterparty\tlabel\n")
        for row in FOLD_LOG:
            f.write("\t".join(row) + "\n")
    log(f"\nfolded contracts -> quarterly_data: {len(FOLD_LOG)}  (log: utils/graph_cleanup_2026_09_05.fold_log.tsv)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run()
