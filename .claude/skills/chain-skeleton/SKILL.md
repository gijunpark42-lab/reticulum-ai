---
name: chain-skeleton
description: Build a new supply-chain skeleton JSON in chains/. Use when the user says "build chain skeleton for X", "make a chain for X", or asks for a new product/generation chain file. Covers the layer/domain slugs, the player shape, edge rules and the graph_build.py --sync step.
---

### Workflow 1 — Build a chain skeleton

**Trigger:** User says "build chain skeleton for X" or "make a chain for X."

**Output:** A complete JSON written directly to `chains/<filename>.json`.

Rules to follow:
- Use ONLY the standard layer slugs, top→bottom (see "Standard layers" above): `application`, `ai_models`, `software_infra`, `cloud_infra`, `system_integration`, `compute_hardware`, `memory`, `interconnect`, `advanced_packaging`, `foundry`, `equipment`, `materials`, `minerals`. Skip layers that don't apply.
- Put cross-cutting participants in a separate `domains` block (`power`, `thermal`, `security`, `edge_ai`), NOT in the layer stack.
- Give each layer its `sectors` (free-text). A sector holds EITHER `players` OR `sub_sectors` (each with `players`).
- For every player, name the **specific** product in this chain (e.g. SK Hynix → "HBM4 stacks", not "memory").
- Build edges as **specific directed relationships** — do NOT connect every company in one layer to every company in the next. Only create an edge where a real supply/customer relationship exists.
- Same-layer edges are allowed when real (e.g. HBM supplier → packaging fab).
- A player with no real outgoing relationship gets `"connects_to": []`.
- All `contracts` fields start empty `[]` — transcript enrichment fills them later.
- The chain must reach a final end customer (`application` / `ai_models` / `cloud_infra`).
- Apply the litmus test before including any company.
- After writing the file, run `python graph_build.py --sync` — rebuilds `graph/merged_graph.json`, re-derives the Timelines / Screener / Capex views (see `derive.py`), and syncs `web/public/data`.

**Shape every player must follow (unchanged — only its nesting moved):**
```json
{
  "company": "exact company name",
  "product": "specific product in this chain",
  "connects_to": [
    { "company": "target name", "relationship": "one-line description of what flows", "contracts": [] }
  ],
  "quarterly_data": []
}
```

---

