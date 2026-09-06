# data-exposure — integration notes

"Who benefits" view: per-chain / per-transition ranking of companies by an explainable
exposure score, with a basket (tickers / TradingView list / CSV), a customer-supplier
concentration table, and the generation delta. Agent: `data-exposure`, 2026-09-05.

## Files (all new or append-only)

| File | What |
|---|---|
| `derive.py` | **Append-only.** New section "4) EXPOSURE" (constants, `_first_pct`, `_chain_files`, `_days_between`, `derive_exposure(graph, today=None)`) inserted before the entry-point block, plus ONE line `derive_exposure(graph)` inside `derive_all`. No existing function or constant was modified. |
| `web/src/lib/exposure.ts` | Types for `exposure.json`, `loadExposure()` (fetch once, module cache, resolves `null` on 404/network error instead of throwing), `tradingViewSymbol()`, `daysSince()`, `freshnessOf()`, `scoreBreakdown()`, `csvLine()`, `labelDate()`. |
| `web/src/components/Exposure.tsx` | The tab. Reuses `computeTransition` / `nodeExposure` from `transitions.ts`, `CellText` for clamped cells, `.co-link` / `.btn` / `.tbl-wrap` / `table.data` from globals. |
| `web/src/components/Exposure.css` | All new styles, every class prefixed `.xp-`; imported by the component. Includes its own ≤700px card-stack rules (same `data-label` trick as `.screener` / `.tl`) because globals.css is not mine to edit. |
| `graph/exposure.json` | Output of `python derive.py` (542 KB, compact JSON). |
| `web/public/data/exposure.json` | Local copy for type-testing only — `graph_build.py --sync` / `npm run sync` regenerates and overwrites it (`sync-data.mjs` already lists `graph/exposure.json`). |

No change is needed in `graph_build.py` (it calls `derive_all`, which now also calls
`derive_exposure`), `sync-data.mjs`, `types.ts`, `data.ts` or `globals.css`.

## Mounting the tab (page.tsx — the only shared-file change)

```tsx
// 1) import, next to the other component imports
import Exposure from "@/components/Exposure";

// 2) add the tab name (anywhere you like in the order; after "Generations" reads naturally)
const TABS = ["Graph", "Chain 2D", "Generations", "Exposure", "Timelines", "Screener", "Capex", "Coverage"] as const;

// 3) render it with the others
{viz && tab === "Exposure" && (
  <Exposure nodes={viz.nodes} byId={viz.byId} onOpen={openNode} />
)}
```

Props: `nodes: VizNode[]`, `byId: Map<string, VizNode>`, `onOpen(id: string)` (the existing
`openNode` — opens the NodePanel). The component fetches `/data/exposure.json` itself.

## exposure.json schema

```jsonc
{
  "generated": "2026-09-05",                 // ISO date the file was built
  "formula": "score(company, chain) = role weight (...) + 0.5 x min(contracts ..., 10) + ...",
  "weights": {                               // the constants behind the score (UI uses them for the bar scale + tooltip)
    "role": { "compute_hardware": 3, "memory": 3, "interconnect": 3, "advanced_packaging": 3, "foundry": 3,
              "equipment": 2, "materials": 2, "cloud_infra": 2, "ai_models": 2, "application": 2,
              "system_integration": 2, "power": 2, "thermal": 2,
              "minerals": 1, "software_infra": 1, "security": 1, "edge_ai": 1 },
    "default_role": 1,
    "contract_step": 0.5, "contract_cap": 10,
    "edge_step": 0.5, "edge_cap": 8,
    "fresh_days": 90, "fresh_bonus": 2, "aging_days": 180, "aging_bonus": 1
  },
  "transitions": [ { "key": "nvidia", "from": ["nvda_b200"], "to": ["nvidia_vera_rubin"] }, ... ],  // mirror of transitions.ts
  "companies": {
    "Hanmi Semiconductor": {
      "ticker": "042700", "exchange": "KRX", "country": "KR", "status": "public",
      "chains": ["hbm_memory"],
      "primary": "equipment",                              // first layer slug, else first domain slug
      "roles": [ { "chain": "hbm_memory", "layer": "equipment", "domain": null,
                   "sector": "Advanced Packaging Equipment", "sub_sector": null,
                   "product": "TC bonders for HBM stacking (DUAL TC Bonder)" } ],
      "in_degree": 0, "out_degree": 13,
      "edges_with_contracts": 13, "contracts_total": 13,
      "counterparties": 17,                                // distinct edge partners + folded counterparties (all chains)
      "signals": 12,                                       // quarterly_data entries
      "latest": "2026-08-14", "days_since": 22,            // newest source label (quarterly_data + contracts on its edges)
      "freshness_bonus": 2,                                // 0 | 1 | 2 as used in the score
      "topics": { "hbm": 6, "packaging_substrate": 12, ... },   // explicit `topics` tags only (no keyword fallback)
      "slots": { "revenue_growth": "Q2 rev KRW 251.2B (+39.5% YoY ...)", "supply_status": "...", ... },  // latest-dated per slot
      "slot_sources": { "revenue_growth": "Hanmi Semiconductor Q2 FY2026 (08-14-2026)", ... },
      "generations": { },                                  // transition key -> "retained" | "gained" | "lost" (only where the company appears)
      "concentration": [                                   // sorted: pct desc, null pct last, then counterparty A→Z
        { "counterparty": "SK Hynix", "role": "customer", "pct": null,
          "text": "Half-year report (filed 08-14-2026) lists SK Hynix first ...",
          "label": "Hanmi Semiconductor Q2 FY2026 (08-14-2026)", "chain": "hbm_memory" } ],
      "score_by_chain": { "hbm_memory": 13.0 },
      "chain_stats": { "hbm_memory": { "role_weight": 2, "edges": 13, "contracts": 13, "counterparties": 17 } }
    }
  },
  "chains": {
    "nvda_b200": { "anchor": "NVIDIA",                     // chain file's top-level "company" when it is a node id, else null
                   "group": "accelerators",                // chains/ sub-folder → selector optgroup
                   "members": ["NVIDIA", "TSMC", "Anthropic", ...],   // score desc, then id A→Z
                   "edges": 52, "contracts": 3 }
  }
}
```

Score (per company, per chain — documented in `derive.py` comments and in `"formula"`):

```
role weight (heaviest role the company plays in that chain; 3 / 2 / 1 per the table above)
+ 0.5 × min(contracts on the company's edges in that chain, 10)     — both directions
+ 0.5 × min(edges in that chain touching the company, 8)             — both directions
+ freshness: +2 if newest source ≤ 90 days old, +1 if ≤ 180, else 0  — company-level
rounded to 1 decimal; max possible = 14.0
```

Only chains the company is a MEMBER of (`node.chains`) get a score. Concentration facts come
from (a) `quarterly_data` entries with `counterparty` / `counterparty_role`, and (b) edge
contracts of type `"customer share"` (attached to the edge SOURCE with role `"customer"`).
`pct` = a share-shaped percentage first (`x% of …`, `x% share`), else the first percentage,
anything > 100 ignored (it is a growth rate). Raw text always travels with it.

## What the tab does

- **Selector**: 4 generation transitions + all 20 chains grouped by `chains/` sub-folder
  (accelerators / components / manufacturing); the option shows the anchor company.
- **Summary strip**: chain colour dot, members / edges / contracts, anchor link, data date, and
  a `<details>` with the formula. In transition mode: gained / retained / lost counts.
- **Layer chips** (taxonomy colours, with counts) + **text filter** (company, ticker, product,
  sector, layer name).
- **Ranked table** (`table.data.xp-table`): Basket ☑, #, Company (→ `onOpen`) with sector
  sub-line, Gen chip (when the chain belongs to a transition, via `nodeExposure`; always in
  transition mode), Role in chain, Layer, Score (+ bar on a fixed 0–14 scale; hover = breakdown
  "role 3 + contracts 5.0 (25, capped) + edges 4.0 (29, capped) + fresh 2 = 14.0"), Contracts,
  Partners, Latest (freshness dot, recomputed client-side from `latest`), Ticker + exchange
  (hover = TradingView symbol), Latest signal (newest screener slot, `CellText` dialog with its
  source label). Every column sorts; rank stays fixed to score order.
- **Basket bar**: per-row checkbox + select-all-visible; "Copy tickers" (comma list),
  "Copy TradingView list" (`EXCHANGE:CODE` per line, unmapped exchanges skipped and counted),
  "Download CSV" (visible rows, narrowed to the basket when it holds any; UTF-8 BOM). If the
  clipboard API is blocked, the text appears in a read-only box to copy by hand.
- **Generation delta** (transition mode): three columns — new in next gen, not in next gen,
  retained-with-content-change (`productFrom → productTo`) — from `computeTransition`.
- **Concentration** section for the selection's members: company, counterparty (link when it
  is a node), role, share %, detail (`CellText`), source label; sorted by share desc.
- **Missing JSON**: friendly notice with the command to run; the generation delta still renders.
- Transition mode semantics: numbers come from the successor chain where the company scores
  highest (TPU v8t vs v8i); a company not in the successor shows "—" for score, its prior-gen
  figures muted, and sorts last on the score column.

## How I verified

- `python -X utf8 -c "import derive"` → ok. `python -X utf8 derive.py` → clean, prints the
  exposure summary (312 companies, 20 chains, 23 with concentration facts, 542 KB, top-3 per chain).
- Inspected the JSON: no Korean characters; 185 concentration facts, 128 with a `%`, none > 100
  after the share-first regex (it had picked "price +211% YoY" for Samsung ← Kioxia; now 12.2%).
- `cd web && npx tsc --noEmit --incremental false` → the ONLY error is in
  `src/components/AskGraph.tsx` (another agent's file, `Status` vs `string`). An isolated pass
  over my entry files (scratchpad tsconfig extending `web/tsconfig.json`, includes
  `exposure.ts` + `Exposure.tsx` and everything they import) exits 0.
- Runtime smoke test (transpiled `exposure.ts` with the repo's TypeScript, ran under node):
  TradingView mapping over every ticker in the data — 229/245 mapped (NASDAQ 69/69, NYSE 41/41,
  TSE 42/42, TWSE 29/29, KOSDAQ 14/14, KOSPI 11/11, KRX 10/10, SZSE 7/7, XETRA 5/5, SSE 1/1; the
  16 unmapped are AMS/EPA/Euronext/HKEX/IDX/LSE/MIL/OMX/OSE/SIX/STO/VIE — null by design);
  14/14 fixed mapping cases; `daysSince`, `freshnessOf`, `labelDate`, `csvLine` as expected;
  every one of the 779 (company, chain) scores re-derives from its `chain_stats` + `weights`;
  every `chains[].members` list is in score order.
- Not visually tested (no dev server allowed) — please check: the table at ~1200px (fixed
  widths; "Latest signal" absorbs the rest), the ≤700px card-stack, the `<details>` formula
  toggle, and the Score bar/tooltip.

## Caveats

- `days_since` / `freshness_bonus` are frozen at build time; the UI recomputes the dot from
  `latest`, but the SCORE keeps the build-time bonus (by design — the score must match the file).
- 15 edges point at a company that is not a member of that chain (e.g. Anthropic inside
  `amd_mi450_helios`); they count in company-level totals but not in that chain's score.
- `topics` counts only explicit tags — legacy untagged entries are not keyword-matched here.
- Concentration `pct` is a heuristic (first share-shaped %); "top-5 customers ~25%" style
  aggregates and "contract = 99% of prior-year revenue" facts sit next to true customer shares.
  The text and label are always shown so the reader can judge.
- `EXPOSURE_TRANSITIONS` in `derive.py` mirrors `TRANSITIONS` in `transitions.ts` — update both
  when a new generation chain is added (the component uses the TS list for the selector and the
  delta; the JSON `generations` map uses the Python list).
- The tab's default selection is the NVIDIA transition (`t:nvidia`); change `useState` in
  `Exposure.tsx` if a chain should open first.
- The basket persists across selections within the tab (not across page reloads).
