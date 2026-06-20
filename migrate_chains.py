"""
migrate_chains.py — one-time migration of every chain file from the OLD tier model
to the NEW layer / sector / domain model defined in taxonomy.py.

WHY a script (not hand-editing 20 files):
  The core project rule is "map preservation > everything" — no player, edge,
  connects_to, or quarterly_data may be dropped. A deterministic script guarantees
  that by construction: it MOVES each player dict verbatim into its new nesting and
  never touches the dict's contents. Routing only decides WHERE a player goes, never
  WHAT it contains. If routing guesses wrong, the player is still fully preserved and
  the placement is flagged for the user to fix in review.

WHAT it does, per chain file:
  - walk every (old_tier, player) in `flow`
  - route the player -> (layer|domain, sector) using product + tier keywords
  - rebuild the file as nested  flow[].layer.sectors[].players[]  (+ a domains[] block)
  - layers are emitted top->bottom in taxonomy LAYER_ORDER
  - write MIGRATION_REVIEW.md: one line per player, flagged rows surfaced at the top

Run:  python migrate_chains.py
Revert: git checkout chains/   (a clean baseline was committed first)
"""

import os
import json
import glob
from collections import OrderedDict

from taxonomy import LAYERS, DOMAINS, LAYER_ORDER, LAYER_NAMES, DOMAIN_NAMES


# ── small keyword helper ────────────────────────────────────────────────────────
def has(text, *words):
    """True if any of `words` appears in `text` (already lower-cased)."""
    return any(w in text for w in words)


# Companies we recognize by name regardless of the product string.
BIG5_CLOUD = {"microsoft", "amazon web services", "google", "oracle", "meta", "huawei cloud"}
COOLING_COS = {"coolit systems", "asetek", "liquidstack", "submer", "nidec", "modine",
               "munters", "fläktgroup", "flaktgroup", "trane technologies",
               "johnson controls", "alfa laval"}
POWER_COS = {"vertiv", "eaton", "schneider electric", "ge vernova", "abb", "hitachi energy",
             "siemens energy", "legrand", "hd hyundai electric", "ls electric",
             "sanil electric", "mitsubishi heavy industries", "constellation energy",
             "bloom energy", "fluence energy", "delta electronics", "lite-on", "vicor",
             "monolithic power systems", "navitas", "power integrations", "wolfspeed",
             "nvent"}
APP_COS = {"cursor", "perplexity"}          # AI-native apps that live in the Application layer


# ── routing result ──────────────────────────────────────────────────────────────
def R(kind, slug, sector, flagged=False, note=""):
    return {"kind": kind, "slug": slug, "sector": sector, "flagged": flagged, "note": note}


def route(tier, company, product):
    """Return where a player goes: kind ('layer'|'domain'), slug, sector, flagged, note.

    Dispatch is TIER-FIRST (the old tier is a strong hint), then product keywords —
    this avoids cross-tier keyword bleed (e.g. a hyperscaler 'buyer of power' must not
    be pulled into the power domain just because its product mentions 'power').
    The known grab-bag tiers (component, switch_system, oem, raw_material) get the
    richest product routing, including escapes into the power/thermal domains.
    """
    p = (product or "").lower()
    c = (company or "").lower()

    # ── thermal / power domains: companies recognized by name (any tier) ──────────
    def thermal_sector():
        if has(p, "immersion"):            return "Immersion"
        if has(p, "two-phase"):            return "Two-Phase"
        if has(p, "tim", "thermal interface"): return "TIM"
        if has(p, "heat exchanger", "brazed-plate", "cdu core"): return "Heat Exchanger / CDU"
        if has(p, "cold plate", "direct-to-chip", "direct to chip", "cdu", "liquid cooling", "cold plates"):
            return "Direct-to-Chip Liquid"
        if has(p, "chiller", "crah", "hvac", "air-handling", "air treatment", "evaporative", "air cooling"):
            return "Air Cooling"
        return "Direct-to-Chip Liquid"

    def power_sector():
        if has(p, "mosfet", "sic ", "sic modules", "sic power", "gan", "pmic", "vrm",
               "voltage regulator", "power management", "gate driver", "dc-dc", "optimos",
               "factorized power", "multiphase", "hot-swap", "intermediate bus", "power ic",
               "power-conversion", "power conversion"):
            return "Power Semiconductors"
        if has(p, "mlcc", "passive", "capacitor", "resistor"):
            return "Power Semiconductors"
        if has(p, "nuclear", "gas", "turbine", "fuel cell", "battery", "bess",
               "energy storage", "generation", "powered-land", "smr"):
            return "Generation"
        if has(p, "transformer", "switchgear", "grid", "hvdc", "substation",
               "electrical steel", "goes", "medium-voltage"):
            return "Grid"
        if has(p, "ups", "pdu", "busbar", "busway", "psu", "power shelf", "power shelves",
               "power supply", "power supplies", "rack power", "48v", "power distribution"):
            return "Datacenter Power"
        return "Datacenter Power"

    # ─────────────────────────── tier dispatch ──────────────────────────────────
    if tier == "ai_lab":
        if c in APP_COS:
            return R("layer", "application", "AI-Native Vertical Apps", True,
                     "was ai_lab; looks like an AI-native app, not a model maker")
        return R("layer", "ai_models", "Foundation Models")

    if tier == "hyperscaler":
        if c in BIG5_CLOUD:
            return R("layer", "cloud_infra", "Hyperscaler Cloud")
        return R("layer", "cloud_infra", "Neocloud (GPU-specialized)")

    if tier == "power":
        return R("domain", "power", power_sector())

    if tier == "software":
        return R("layer", "software_infra", "Inference Optimization Stack")

    if tier == "equipment":
        if has(p, "mocvd") or c == "aixtron":
            return R("layer", "equipment", "Compound Semi Equipment")
        if has(p, "tape-casting", "lamination", "co-firing", "screen-print") or c in {"sacmi", "asada"}:
            return R("layer", "equipment", "MLCC / Passives Equipment", True,
                     "passive-component manufacturing equipment (no PDF sector)")
        if has(p, "litho", "euv", "duv", "scanner", "nil", "mask", "reticle") or c == "lasertec":
            return R("layer", "equipment", "Lithography")
        if has(p, "inspection", "metrology", "process control", "defect", "prober",
               "probe card", "tester", "handler", "socket", "test pins", "test sockets",
               "test systems", "test equipment", "test consumables"):
            return R("layer", "equipment", "Metrology / Inspection")
        if has(p, "bonder", "bonding", "tcb", "thermo-compression", "dicing", "grinding",
               "molding", "rdl", "tsv via", "via-drilling", "plating", "die-attach",
               "debonder", "reflow", "descum", "annealing", "marking"):
            return R("layer", "equipment", "Advanced Packaging Equipment", True,
                     "packaging/bonding tool (no exact PDF sector)")
        return R("layer", "equipment", "Deposition & Etch")

    if tier == "epiwafer":
        if has(p, "nand"):
            return R("layer", "memory", "NAND Flash")
        if has(p, "gan", "sic") and has(p, "foundry", "fab"):
            return R("layer", "foundry", "Compound Semi Foundry (GaN/SiC/InP)")
        if has(p, "eml", "cw laser", "dfb", "laser epiwafer", "laser chips"):
            return R("layer", "interconnect", "Components")
        if has(p, "inp", "gaas", "epiwafer", "epitaxy"):
            return R("layer", "materials", "InP Wafers")
        if has(p, "logic wafer", "logic wafers", "front-end", "n3", "n2", "n5", "18a", "4np", "advanced node"):
            return R("layer", "foundry", "Leading-Edge Logic Foundry (2nm/3nm)")
        return R("layer", "foundry", "Leading-Edge Logic Foundry (2nm/3nm)", True, "was epiwafer; unclear role")

    if tier == "packaging":
        if has(p, "ssd", "nvme") and not has(p, "controller"):
            return R("layer", "memory", "NAND Flash")
        if has(p, "optical module", "optical transceiver", "transceiver"):
            return R("layer", "interconnect", "Components")
        if has(p, "hbm stack", "tc bonder", "hbm bonding"):
            return R("layer", "advanced_packaging", "HBM Stacking & Bonding")
        if has(p, "cowos", "soic", "foveros", "emib", "i-cube", "x-cube", "2.5d", "3d",
               "interposer", "wafer-level", "wafer level", "sip"):
            return R("layer", "advanced_packaging", "Wafer-Level Packaging (CoWoS, SoIC)")
        if has(p, "osat", "assembly", "test", "flip-chip", "flip chip"):
            return R("layer", "foundry", "OSAT (assembly & test)")
        if has(p, "packaging line"):
            return R("layer", "equipment", "Advanced Packaging Equipment", True, "OCS packaging line = equipment")
        if has(p, "epyc", "cpu"):
            return R("layer", "compute_hardware", "Server CPU")
        if has(p, "superchip", "grace-hopper", "blackwell superchip"):
            return R("layer", "compute_hardware", "Training GPU")
        return R("layer", "advanced_packaging", "Wafer-Level Packaging (CoWoS, SoIC)", True, "was packaging; unclear")

    if tier == "switch_system":
        if c in COOLING_COS or has(p, "cool", "cold plate", "immersion", "cdu", "chiller", "thermal"):
            return R("domain", "thermal", thermal_sector())
        if c in POWER_COS or has(p, "ups", "transformer", "switchgear", "pdu", "busway",
                                  "power transformer", "grid", "turbine"):
            return R("domain", "power", power_sector())
        if has(p, "gpu") and has(p, "platform", "systems", "superchip", "b200", "gb200",
                                  "gb300", "rubin", "instinct"):
            return R("layer", "compute_hardware", "Training GPU")
        if has(p, "ultraserver", "trainium"):
            return R("layer", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)")
        if has(p, "co-packaged optics", "co-packaged", "cpo", "photonics switch"):
            return R("layer", "interconnect", "Components")
        if has(p, "coherent", "dci", "dwdm", "metro", "wavelogic", "long-haul", "transport"):
            return R("layer", "interconnect", "Scale-across")
        if has(p, "nvlink", "infinity fabric", "ualink", "pcie", "cxl", "scale-up", "neuronlink"):
            return R("layer", "interconnect", "Scale-up")
        if has(p, "ethernet", "infiniband", "tomahawk", "jericho", "spectrum", "quantum",
               "silicon one", "scale-out", "etherlink"):
            return R("layer", "interconnect", "Scale-out")
        return R("layer", "interconnect", "Components")  # transceivers, DSP, OCS, lasers, connectors

    if tier == "oem":
        if has(p, "xpu", "asic", "accelerator", "gpu accelerator") and c in {"broadcom", "nvidia", "amd"}:
            sec = "Custom AI ASIC (hyperscaler silicon)" if c == "broadcom" else "Training GPU"
            return R("layer", "compute_hardware", sec)
        if has(p, "colocation", "data-center campus", "data center campus", "campuses",
               "powered infrastructure", "data-center colocation"):
            return R("layer", "cloud_infra", "Datacenter Colocation")
        if c in POWER_COS or has(p, "psu", "power shelf", "power shelves", "power supplies", "rack power"):
            return R("domain", "power", power_sector())
        if has(p, "thermal") and not has(p, "rack systems"):
            return R("domain", "thermal", thermal_sector())
        if has(p, "switch system", "ethernet switch", "switch systems", "networking"):
            return R("layer", "system_integration", "Networking Systems")
        if has(p, "co-packaged optics", "silicon photonics", "cpo") and c in {"mediatek"}:
            return R("layer", "compute_hardware", "Networking ASIC", True, "CPO ASIC platform — could be Interconnect")
        if has(p, "fiber network", "fiber carrier"):
            return R("layer", "interconnect", "Components", True, "fiber network carrier")
        if has(p, "silicon photonics", "co-packaged optics", "optical networking", "cpo"):
            return R("layer", "interconnect", "Components", True, "optical system integration")
        # default: server / rack integrators
        odm = {"foxconn", "quanta", "wistron", "pegatron", "wiwynn", "inventec", "compal",
               "celestica", "jabil", "gigabyte", "chenbro", "flex"}
        if c in odm:
            return R("layer", "system_integration", "Server ODM")
        return R("layer", "system_integration", "Server / Rack OEM")

    if tier == "component":
        # memory first
        if has(p, "hbf"):
            return R("layer", "memory", "HBF")
        if has(p, "hbm"):
            return R("layer", "memory", "HBM")
        if has(p, "lpddr"):
            return R("layer", "memory", "LPDDR")
        if has(p, "nand", "v-nand", "3d nand", "bics"):
            return R("layer", "memory", "NAND Flash")
        if has(p, "hdd", "nearline", "hamr"):
            return R("layer", "memory", "Nearline HDD", True, "HDD has no PDF memory sector")
        if has(p, "ssd", "nvme") and has(p, "controller"):
            return R("layer", "memory", "NAND Flash")
        if has(p, "ssd"):
            return R("layer", "memory", "NAND Flash")
        if has(p, "rcd", "rdimm", "mrdimm", "socamm", "memory-interface", "register", "dram"):
            return R("layer", "memory", "DRAM")
        # power / passives escape (incl. server PSUs / power shelves)
        if has(p, "mlcc", "passive", "vrm", "pmic", "mosfet", "voltage regulator",
               "gate driver", "power mosfet", "power management", "optimos", "factorized power",
               "multiphase", "power delivery ic", "power-conversion", "vpd", "intermediate bus",
               "psu", "power shelf", "power shelves", "power supply", "power supplies") \
                or (has(p, "sic", "gan") and has(p, "power", "module")):
            return R("domain", "power", power_sector())
        if has(p, "heat exchanger", "cdu core", "brazed-plate"):
            return R("domain", "thermal", thermal_sector())
        # EDA / IP
        if c in {"synopsys", "cadence"}:
            return R("layer", "software_infra", "GPU Programming Layer (low-level kernels)", True,
                     "EDA software — no clean PDF home")
        if c == "arm holdings":
            return R("layer", "compute_hardware", "Server CPU")
        if c == "aspeed":
            return R("layer", "system_integration", "Server ODM", True, "BMC controller chip")
        # compute silicon
        if has(p, "lpu", "rdu", "dataflow", "inference accelerator", "inference engine"):
            return R("layer", "compute_hardware", "Dedicated Inference Accelerators")
        if has(p, "tpu", "trainium", "xpu", "maia", "custom ai", "custom asic", "npu", "asic"):
            return R("layer", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)")
        if has(p, "epyc", "grace", "graviton", "axion", "cobalt", "neoverse", "ampereone",
               "server cpu", "host cpu", "cpu silicon") or (has(p, "cpu") and not has(p, "gpu")):
            return R("layer", "compute_hardware", "Server CPU")
        if has(p, "gpu", "instinct", "blackwell", "rubin", "cdna"):
            return R("layer", "compute_hardware", "Training GPU")
        if has(p, "apple silicon"):
            return R("layer", "compute_hardware", "Server CPU", True, "client SoC designer — no exact sector")
        # foundries listed as fab providers inside a component tier
        if has(p, "wafer fab", "foundry", "logic dies", "front-end"):
            if has(p, "gan", "sic", "compound", "photonics"):
                return R("layer", "foundry", "Compound Semi Foundry (GaN/SiC/InP)")
            return R("layer", "foundry", "Leading-Edge Logic Foundry (2nm/3nm)")
        # interconnect / optical
        if has(p, "tomahawk", "jericho", "switch asic", "switch silicon"):
            return R("layer", "interconnect", "Scale-out")
        if has(p, "cxl", "pcie switch", "scale-up switch", "switch solutions"):
            return R("layer", "interconnect", "Scale-up")
        if has(p, "co-packaged", "cpo"):
            return R("layer", "interconnect", "Components")
        if has(p, "transceiver", "dsp", "pam4", "laser", "eml", "cw laser", "photonic",
               "silicon photonics", "optical", "tia", "fau", "retimer", "aec", "modulator",
               "optical i/o", "light engine", "pic", "serdes", "interconnect", "connector",
               "connectivity"):
            # silicon photonics FOUNDRY services -> foundry, not a component
            if has(p, "foundry"):
                return R("layer", "foundry", "Silicon Photonics Foundry")
            return R("layer", "interconnect", "Components")
        # substrates / boards
        if has(p, "glass-core", "glass substrate", "glass core"):
            return R("layer", "advanced_packaging", "Glass-Core Substrate")
        if has(p, "abf", "fcbga", "fc-bga", "fc-csp", "substrate", "ic substrate", "hbm substrate"):
            return R("layer", "advanced_packaging", "FC-BGA Substrate")
        if has(p, "pcb", "laminate", "mlb", "boards", "copper-clad", "hdi"):
            return R("layer", "advanced_packaging", "FC-BGA Substrate", True, "high-end PCB/board")
        # ASIC design services
        if has(p, "asic design", "asic backend", "design services", "design service", "edt"):
            return R("layer", "compute_hardware", "Custom AI ASIC (hyperscaler silicon)", True, "ASIC design house")
        return R("layer", "compute_hardware", "(unclassified)", True, "was component; could not classify by product")

    if tier == "raw_material":
        if c in COOLING_COS or has(p, "coolant", "novec", "immersion coolant", "fluorinated"):
            return R("domain", "thermal", "Immersion" if has(p, "immersion") else "Coolants & Fluids")
        if has(p, "busbar", "cold plate stock"):
            return R("domain", "power", "Datacenter Power")
        if has(p, "electrical steel", "goes", "grain-oriented"):
            return R("domain", "power", "Grid")
        if has(p, "glass-core", "glass substrate", "glass panel"):
            return R("layer", "advanced_packaging", "Glass-Core Substrate")
        if has(p, "optical fiber", "fiber cable", "fiber and", "mpo fiber", "single-mode"):
            return R("layer", "interconnect", "Components")
        if has(p, "soi"):
            return R("layer", "materials", "SOI Wafers")
        if has(p, "inp", "indium phosphide"):
            return R("layer", "materials", "InP Wafers")
        if has(p, "sic", "silicon carbide"):
            return R("layer", "materials", "SiC Wafers")
        if has(p, "gan"):
            return R("layer", "materials", "Compound Substrates", True, "GaN substrate (no exact PDF sector)")
        if has(p, "silicon wafer", "300mm", "polished", "prime silicon", "epitaxial silicon"):
            return R("layer", "materials", "Silicon Wafers (300mm)")
        if has(p, "photoresist", "resist"):
            return R("layer", "materials", "Photoresist")
        if has(p, "gas", "filtration", "ultra-pure"):
            return R("layer", "materials", "Specialty / Process Gases")
        if has(p, "slurry", "etchant", "precursor", "chemical", "cmp"):
            return R("layer", "materials", "Process Chemicals & Slurries")
        if has(p, "abf", "bt resin", "build-up film", "buildup film", "encapsulant",
               "molding compound", "die-attach", "dielectric"):
            return R("layer", "materials", "Substrate Materials (ABF/BT)")
        if has(p, "copper foil", "laminate"):
            return R("layer", "materials", "Substrate Materials (ABF/BT)")
        if has(p, "photomask", "mask blank", "sputtering target"):
            return R("layer", "materials", "Photomask & Targets")
        if has(p, "batio3", "barium titanate", "nickel", "paste", "perovskite", "ni "):
            return R("layer", "materials", "Passive Component Materials", True, "MLCC raw material")
        return R("layer", "materials", "Specialty / Process Gases", True, "was raw_material; unclassified")

    # unknown tier
    return R("layer", "compute_hardware", "Networking ASIC", True, f"unknown old tier '{tier}'")


# ── rebuild one chain file into the new nested shape ────────────────────────────
def migrate_chain(chain):
    # layer slug -> OrderedDict(sector -> [players]) ; same for domains
    layer_groups = OrderedDict()
    domain_groups = OrderedDict()
    review = []  # (company, old_tier, kind, slug, sector, flagged, note)

    for tier_obj in chain.get("flow", []):
        old_tier = tier_obj.get("tier")
        for player in tier_obj.get("players", []):
            r = route(old_tier, player.get("company"), player.get("product"))
            bucket = layer_groups if r["kind"] == "layer" else domain_groups
            bucket.setdefault(r["slug"], OrderedDict()).setdefault(r["sector"], []).append(player)
            review.append((player.get("company"), old_tier, r["kind"], r["slug"],
                           r["sector"], r["flagged"], r["note"]))

    # serialize flow: layers top->bottom by taxonomy order
    flow = []
    for slug in sorted(layer_groups, key=lambda s: LAYER_ORDER.get(s, 999)):
        sectors = [{"sector": sec, "players": pls} for sec, pls in layer_groups[slug].items()]
        flow.append({"layer": slug, "sectors": sectors})

    # serialize domains in taxonomy DOMAINS order
    domain_order = {slug: i for i, (slug, *_ ) in enumerate(DOMAINS)}
    domains = []
    for slug in sorted(domain_groups, key=lambda s: domain_order.get(s, 999)):
        sectors = [{"sector": sec, "players": pls} for sec, pls in domain_groups[slug].items()]
        domains.append({"domain": slug, "sectors": sectors})

    new_chain = OrderedDict()
    new_chain["company"] = chain.get("company")
    new_chain["chain_focus"] = chain.get("chain_focus")
    new_chain["flow"] = flow
    if domains:
        new_chain["domains"] = domains
    return new_chain, review


def main():
    files = sorted(glob.glob(os.path.join("chains", "**", "*.json"), recursive=True))
    review_all = OrderedDict()
    tot_players_before = tot_players_after = 0

    for fp in files:
        with open(fp, encoding="utf-8") as f:
            chain = json.load(f)
        before = sum(len(t.get("players", [])) for t in chain.get("flow", []))
        new_chain, review = migrate_chain(chain)
        # preservation check: same number of players out as in
        from taxonomy import iter_players
        after = sum(1 for _ in iter_players(new_chain))
        assert before == after, f"{fp}: player count changed {before} -> {after}"
        tot_players_before += before
        tot_players_after += after

        with open(fp, "w", encoding="utf-8") as f:
            json.dump(new_chain, f, indent=2, ensure_ascii=False)
        review_all[os.path.basename(fp)[:-5]] = review
        print(f"  migrated {os.path.basename(fp):34s} {before} players")

    print(f"\nTotal players: {tot_players_before} -> {tot_players_after} (preserved)")
    write_review(review_all)


def write_review(review_all):
    flagged_rows, clean_by_chain = [], OrderedDict()
    for chain, rows in review_all.items():
        for co, tier, kind, slug, sector, flagged, note in rows:
            name = (LAYER_NAMES if kind == "layer" else DOMAIN_NAMES).get(slug, slug)
            line = f"`{chain}` · **{co}** · {tier} → {name} › {sector}"
            if flagged:
                flagged_rows.append(f"- ⚠ {line} — _{note}_")
            else:
                clean_by_chain.setdefault(chain, []).append(f"- {co}: {tier} → {name} › {sector}")

    out = ["# Migration review — tier → layer/sector\n",
           "Every player below was MOVED verbatim (all edges / quarterly_data / contracts intact); ",
           "only its position in the taxonomy changed. Review the flagged rows first.\n",
           f"\n## ⚠ Needs your decision ({len(flagged_rows)} players)\n"]
    out += flagged_rows or ["- (none)"]
    out.append("\n## Placements by chain\n")
    for chain, lines in clean_by_chain.items():
        out.append(f"\n### {chain}")
        out += lines
    with open("MIGRATION_REVIEW.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"Wrote MIGRATION_REVIEW.md ({len(flagged_rows)} flagged)")


if __name__ == "__main__":
    main()
