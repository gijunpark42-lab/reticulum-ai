# CLAUDE.md

This file gives Claude (and any AI coding assistant) the full context for this project.
Read it before making changes. Keep it updated as the project evolves.

---

## What this project is

An agentic system that maps the **global AI / semiconductor supply chain** as a connected
**graph** (not a flat list of layers), and enriches it with real data pulled from earnings call
transcripts, news articles, and event transcripts (e.g. GTC).

The end goal is a **web app** where the user clicks any company/product node and the whole supply
web lights up — like a multidimensional scaling map — every supplier, customer, and the actual
deals/figures connecting them. Search a company → drill deep into the web.

The builder is a transfer student learning Python through this project. Code should be
**explicit and beginner-friendly**, commented in English. Explain reasoning when introducing
new concepts. Prefer clarity over cleverness.

---

## Core philosophy (do not violate)

1. **Map preservation > hallucination avoidance.**
   The chain structure (who supplies whom, the edges, multi-layer links) is the project's real
   value and is curated by the user. When updating, NEVER drop or overwrite existing nodes, edges,
   or data. Only ADD. When in doubt, preserve.

2. **Division of labor:**
   - The **human** owns the chain STRUCTURE — which companies, which layers/sectors, which edges, multi-layer
     placement. This is domain research and is the competitive moat. AI must not silently change it.
   - The **AI** owns the repetitive enrichment — extracting deal/figure data from a transcript and
     attaching it to the right existing node or edge.

3. **Specific, not vague.**
   Never "lasers → some laser companies." Always the specific component → its real suppliers →
   the segment it feeds → the actual figure. Each company carries the SPECIFIC product it makes
   in THAT chain (e.g. Marvell → "1.6T DSP", SK Hynix → "HBM4", NVIDIA → "Vera Rubin").

4. **Only real supply-chain participants.**
   A node belongs only if it directly builds, supplies, packages, manufactures, hosts, or
   consumes the product. Exclude mere tool vendors, partners, or unrelated customers.
   Litmus test: "Does this company's stock directly benefit from {product} being built and sold?"
   If no, exclude it.

5. **Build for the web from day one.**
   Keep LOGIC (functions that do the work) separate from EXECUTION (how it's triggered).

---

## THE GRAPH MODEL (most important section)

This is NOT a layer cake where every company in layer N connects to every company in layer N+1.
Layers exist as a **top-down stack**, but every connection is a **specific directed edge** between two nodes.

Example of the difference:
- WRONG (flat layers): "cloud_infra" layer → "ai_models" layer, implying AWS+Google+Meta all feed
  OpenAI+Anthropic+xAI equally.
- RIGHT (graph): AWS → [OpenAI, Anthropic, xAI]; Google Cloud → [Gemini, Anthropic];
  Azure → [OpenAI, Anthropic]; Meta → [] (self-hosted, no outgoing edge).
  Result: the Anthropic node is a HUB with incoming edges from AWS, Google, and Azure.

### Two kinds of connection

**(1) Edges INSIDE a chain file — the `connects_to` field on each player.**
- Edges usually go up one layer (SK Hynix HBM → TSMC packaging), but **same-layer edges are
  allowed and expected** when companies genuinely connect (e.g. SK Hynix's HBM gets attached to
  TSMC's CoWoS → SK Hynix connects_to TSMC).
- Only create an edge where a REAL supply/customer relationship exists. Do not fully connect layers.
- A node with no real outgoing relationship gets `"connects_to": []`.

**(2) Edges ACROSS chain files — automatic, by company name (built later).**
- Each product has its own chain file ON PURPOSE, so that the same company appearing in many
  chains becomes a shared hub when merged. (This is why nodes are split per product — to connect
  them later, not to keep them separate forever.)
- **Generation separation (core differentiator).** "Product" means an investment-significant
  *generation*, not a vendor. Split accelerators by generation — `nvda_b200` (Blackwell) vs
  `nvidia_vera_rubin` (Rubin), and likewise MI450/Helios, Trainium2, Trainium3, TPU v7, TPU v8t/v8i.
  This is a STOCK tool: the value is the generational transition delta (HBM3E→HBM4 content growth,
  copper→optical scale-up, CPO penetration 2026→2028, attach ratio 1:2→1:4→1:8), not a static
  snapshot. **Split when a transition materially shifts content or winners** (CPO intro, HBM jump,
  packaging/foundry change). Do NOT split trivial SKUs/refreshes — those accumulate as
  `contracts`/`quarterly_data` entries on the same chain. Accuracy over volume.
- `vera_rubin.json`'s TSMC == `tpu_v6.json`'s TSMC == `b200.json`'s TSMC → one TSMC hub after merge.
- A future `graph build` step reads ALL chain files and merges by company name into one big
  nodes+edges graph. Current data is not lost; this is a one-time automated merge.

### An EDGE is an object that carries data, not just a line

An edge is not "A → B (supplies)". It holds the concrete deals/figures on that relationship,
and ACCUMULATES new entries over time as transcripts/articles are read.

```json
"connects_to": [
  {
    "company": "Anthropic",
    "relationship": "GPU compute supply",
    "contracts": [
      {
        "source": "NVIDIA Q1 FY2027 (05-28-2026)",
        "signal": "AWS expanding Anthropic's compute capacity",
        "units": "1M+ Blackwell and Rubin GPUs",
        "value": "no specific figure",
        "date_signed": "2026",
        "type": "infrastructure deployment"
      }
    ]
  }
]
```

- The skeleton creates edges with **empty `contracts: []`** (structure only).
- Transcript/article analysis ADDS entries to `contracts` (units, $ value, dates, deal type).
- This deal-level detail comes almost entirely from transcripts/news, not from the skeleton.

---

## Data model (full shape)

Each product gets its own JSON file in `chains/` (e.g. `nvidia_vera_rubin.json`).
The vocabulary (13 layers, 4 domains, colors, order) lives in **`taxonomy.py`** — the single
source of truth, imported by `app.py`, `graph_build.py`, `main.py`.

```json
{
  "company": "NVIDIA",
  "chain_focus": "Vera Rubin GPU platform",
  "flow": [
    {
      "layer": "memory",
      "sectors": [
        {
          "sector": "HBM",
          "players": [
            {
              "company": "SK Hynix",
              "product": "HBM4 stacks",
              "connects_to": [
                { "company": "TSMC", "relationship": "HBM integrated into CoWoS package", "contracts": [] }
              ],
              "quarterly_data": [
                { "quarter": "NVIDIA Q1 FY2027 (05-28-2026)", "signal": "...", "figure": "..." }
              ]
            }
          ]
        }
      ]
    },
    {
      "layer": "interconnect",
      "sectors": [
        { "sector": "Scale-up",
          "sub_sectors": [ { "sub_sector": "Co-Packaged Optics (CPO)", "players": [] } ] }
      ]
    }
  ],
  "domains": [
    { "domain": "power",
      "sectors": [ { "sector": "Power Semiconductors", "players": [] } ] }
  ]
}
```

- `flow`: ordered list of **layers** (top→bottom). Each layer has `sectors`.
- A `sector` holds EITHER `players` directly OR `sub_sectors` (each sub-sector then holds `players`).
  Use `sub_sectors` only where a sector genuinely splits (e.g. Interconnect → Scale-up/out/across/Components).
- `domains` (optional, parallel to `flow`): cross-cutting groups (power/thermal/security/edge_ai),
  same shape but keyed `domain`.
- `players`: `{company, product, connects_to, quarterly_data}` — UNCHANGED.
  - `connects_to`: outgoing edges (objects with `company`, `relationship`, `contracts[]`).
  - `quarterly_data`: node-level signals/figures about the company itself.
- A company MAY appear in more than one layer/sector if it genuinely plays multiple roles
  (e.g. Corning = optical fiber in `interconnect` AND glass-core in `advanced_packaging`). Intentional.

### Standard layers (FIXED — top → bottom; use these slugs, in this order)

```
application          # AI assistants/chatbots, agentic platforms, enterprise SaaS, AI-native vertical apps
ai_models            # foundation models (LLM/multimodal), fine-tuned models, inference serving, agent frameworks
software_infra       # ML frameworks, GPU programming/kernels, distributed training, Kubernetes, inference opt
cloud_infra          # hyperscaler cloud, neocloud (GPU-specialized), edge/distributed cloud, colocation
system_integration   # server OEM/ODM (Foxconn, Quanta, Wistron, Supermicro, Dell, Arista) — OWNER-ADDED (not in source PDF)
compute_hardware     # training/inference GPU, custom AI ASIC, dedicated accelerators, server CPU, networking ASIC
memory               # HBM, HBF, DRAM, NAND flash, LPDDR
interconnect         # Scale-up / Scale-out / Scale-across / Components (NVLink, transceivers, DSP, optics, CPO, OCS)
advanced_packaging   # CoWoS/SoIC, HBM stacking & bonding, FC-BGA substrate, glass-core substrate, TIM
foundry              # leading-edge logic, specialty/legacy, silicon photonics, compound (GaN/SiC/InP), OSAT
equipment            # litho (EUV/DUV), deposition & etch, metrology/inspection, MOCVD
materials            # silicon/SOI/InP/SiC wafers, photoresist, process gases, substrate materials
minerals             # silicon, copper, gallium, indium, germanium, hafnium, tantalum, tungsten, cobalt, lithium, rare earths
```

### Cross-cutting domains (FIXED — sit BESIDE the stack, keyed `domain`)
```
power     # generation (nuclear/gas/SMR), grid (transformer/substation), datacenter power (UPS/PDU/busbar),
          # power semiconductors (GaN/SiC/PMIC/MLCC & passives)
thermal   # air cooling, direct-to-chip liquid, immersion, two-phase, TIM, heat exchanger/CDU
security  # AI model security, AI workload cybersecurity, post-quantum crypto, optical encryption, HW root of trust
edge_ai   # autonomous vehicles, humanoid robotics, drones/UAV, edge inference chips, AR/VR, quantum/parallel compute
```
Power and thermal are real sub-chains that attach to datacenter/compute nodes via their own edges.

---

## How enrichment works (the transcript loop)

The user gives a URL (earnings call, news article, GTC-style event). The system:

1. **Fetches** the transcript → saves to `transcripts/`.
2. **Analyzes** it against a chain with these jobs (ADD-only):
   - add `quarterly_data` to existing nodes (figures about the company).
   - add `contracts` entries to existing edges (deal detail: units, value, date).
   - ADD a new company ONLY IF it passes the litmus test, with empty `contracts`/`quarterly_data`.
   - ADD a new edge ONLY IF the transcript states a real relationship (e.g. "AWS supports
     Anthropic compute") → add/extend that `connects_to` entry.
3. **Saves** the additions as a patch in `patches/`; `apply_patches.py` merges it into the chain
   (never drop existing nodes/edges/data — and never write `chains/` directly, see Workflow 2).

**Caching:** building a skeleton (Opus) is expensive → runs rarely, saved to disk. Loading is free.
Re-build only on explicit "update" command, never automatically.

**Future automation:** later, auto-fetch new transcripts on a schedule (GitHub Actions cron) so it
runs even when the computer is off. Do NOT build the scheduler until the core loop is solid.

---

## Tech stack

- **Language:** Python (beginner — explicit and commented).
- **Editor:** VS Code + Claude extension.
- **LLM:** Claude Code terminal (no API calls). Skeleton building and transcript enrichment are
  done directly by Claude in this editor. Python functions in `main.py` are kept for reference
  but no longer invoked for LLM tasks.
- **US transcripts:** `av.py` pulls the FULL call (prepared remarks + Q&A, speaker turns) from
  Alpha Vantage `EARNINGS_CALL_TRANSCRIPT` into `transcripts/av/*.txt` (needs `ALPHAVANTAGE_API_KEY`
  in `.env`, free key, 25 requests/day). See Workflow 2c. Motley Fool scraping (`main.py`) is the
  fallback for a call Alpha Vantage has not posted yet.
- **Korean filings:** `dart.py` pulls DART (opendart.fss.or.kr) periodic reports + full financial
  statements into `transcripts/dart/*.txt` (needs `DART_API_KEY` in `.env`). See Workflow 2b.
- **Storage:** JSON files (`chains/`, `transcripts/`). Migrates later to a merged nodes+edges graph,
  then a web backend.
- **Web (future):** Streamlit MVP → full frontend. Functions stay reusable so the web layer calls them.
- **Automation (future):** GitHub Actions cron.

---

## Project structure

```
earnings-ai/
├── CLAUDE.md
├── main.py                   # functions for now; split into modules later
├── av.py                     # US companies: Alpha Vantage full call transcripts → transcripts/av/*.txt (Workflow 2c)
├── av/sync_state.json        # GENERATED by `python av.py sync` — last sync + (symbol, quarter) saved + waiting list
├── av/pending.json           # GENERATED — files saved by sync, not yet enriched (`enrich us` queue)
├── investing.py              # Taiwan/Japan/Europe/HK/China: Investing.com call transcripts → transcripts/investing/*.txt (Workflow 2d)
├── investing/sync_state.json # GENERATED by `python investing.py sync` — article URLs already saved
├── investing/pending.json    # GENERATED — files saved by sync, not yet enriched (`enrich intl` queue)
├── dart.py                   # Korean companies: DART filings → transcripts/dart/*.txt (Workflow 2b)
├── dart/corp_codes.json      # GENERATED by `python dart.py corp` — stock code → DART corp_code
├── dart/sync_state.json      # GENERATED by `python dart.py sync` — last sync date + saved rcept_nos
├── dart/pending.json         # GENERATED — files saved by sync, not yet enriched (`enrich dart` queue)
├── supply_contracts/         # Korean 공급계약 공시, one accumulating txt per company (dart.py sync)
├── apply_patches.py          # patches/*.json → chains/ — the ONLY writer of chains/ during enrichment (safe under parallel jobs)
├── patches/                  # enrichment INBOX: one ADD-only patch per transcript; applied/ holds the receipts
├── graph_build.py            # applies patches, then chains/ → graph/merged_graph.json, then calls derive.py (--sync also refreshes web/public)
├── verify_graph.py           # AUDIT (read-only): every quarterly_data/contract re-checked against its source file → graph/verification.json
├── derive.py                 # graph → Timelines / Screener / Capex views (graph/timelines.bundle.json, graph/company_metrics.json, graph/capex_backlog.json)
├── timelines/                # hand-curated BASELINE tables — INPUT to derive.py, never auto-written
├── company_metrics.json      # hand-curated screener BASELINE — input, never auto-written
├── capex_backlog.json        # hand-curated capex BASELINE — input, never auto-written
├── graph/                    # GENERATED on every build (merged graph + the three derived views) — never hand-edit
├── .env                      # ANTHROPIC_API_KEY, DART_API_KEY, ALPHAVANTAGE_API_KEY (gitignored)
├── .gitignore
├── chains/                   # one JSON per product chain
│   ├── nvidia_vera_rubin.json
│   ├── google_tpu_v6(Trillium).json
│   └── ...
└── transcripts/
    ├── nvda_q1_2027.txt
    ├── av/                   # US calls written by av.py: nvidia_q3_2027.txt (header carries the source label)
    ├── investing/            # non-US calls written by investing.py: alchip_q2_2026.txt (header carries the source label)
    └── dart/                 # Korean filings written by dart.py: skhynix_q2_2026_dart.txt (정기보고서),
                              #   sanilelectric_prelim_2026-08-07.txt (잠정실적)
```

Functions in `main.py`:
- `fetch_transcript(url, filename)` — scrape Motley Fool URL → save to `transcripts/` → return text.
- `load_transcript(filename)` — read a saved transcript.
- `build_chain_skeleton(company, chain_focus)` — Opus builds the structural skeleton INCLUDING
  `connects_to` edges (with empty `contracts: []`).
- `save_chain(chain_data, filename)` / `load_chain(filename)` — JSON read/write in `chains/`.
- `analyze_with_transcript(chain, transcript, quarter_label)` — ADD quarterly_data + edge contracts
  + new nodes/edges (ADD-only, litmus-test guarded).

Later split into: `supply_chain.py`, `analyzer.py`, `graph.py` (merge chains → nodes+edges), `main.py`.

---

## Roadmap (build order)

1. **[in progress]** Per-chain skeletons for multiple products, each WITH `connects_to` edges from
   the start. Cover many domains (memory, photonics, packaging, substrate, foundry, cloud, ai_lab).
   Human curates/corrects each (especially photonics/optical depth, which AI under-fills).
2. Transcript/article enrichment that ADDS deal detail to edges (units, $, dates) and node figures.
3. Graph build: merge all chains by company name → one nodes+edges graph (cross-file hubs).
4. Web app: clickable multidimensional map + search + drill-down (Streamlit MVP → full frontend).
5. Automation: scheduled auto-fetch (GitHub Actions).

---

## AI Workflows (Claude Code terminal — no API call needed)

These are the exact rules Claude follows when the user asks for a skeleton build or transcript enrichment.
The Python functions in `main.py` still exist for reference but are no longer called — Claude does this work directly.

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

### Workflow 2 — Enrich a chain with a transcript or article

**Trigger:** User gives a URL or paste of an earnings call, news article, or event transcript, plus a chain filename and a source label (e.g. "NVIDIA Q1 FY2027 (05-28-2026)" — see canonical format below).

**Output:** A PATCH file `patches/<company>_<quarter>.json` holding ONLY the additions (ADD-only) —
NOT a direct edit of `chains/`. Then `python graph_build.py --sync` is run — it first merges every
pending patch into the chains (`apply_patches.py`), rebuilds the graph, regenerates the Timelines /
Screener / Capex views from the tags added in JOB 5, and syncs `web/public/data`.
**Then it audits the additions:** `graph_build.py` passes the labels of the patches it just applied
to `verify_graph.py`, which re-checks every new entry against the source file (label resolves to a
file, numbers in `figure`/`units`/`value` appear in it, the counterparty is named, no Korean). Read
its `[fail]`/`[warn]` lines before reporting: a `number_not_in_source` on a figure you computed
(a sum, a QoQ delta) is fine — say so; a `source_not_found` means the transcript was not saved
under the expected name — fix the filename; anything else, fix the patch and re-run. To re-check
one label by hand: `python -X utf8 verify_graph.py --label "<label>"`.

**Why patches instead of editing chains/ directly (do not skip this):** several enrichment jobs
often run in parallel and many companies share one chain file (every power company → `power_cooling.json`,
every optical name → `optical_networking.json`). "Read chain → think for 10 minutes → write the whole
chain back" silently overwrites whatever another job added in those 10 minutes — no error, valid JSON,
data just gone (a *lost update*). A patch file has a unique name, so nothing collides, and
`apply_patches.py` is the single writer of `chains/`: it re-reads the live file, finds-or-creates each
player/edge by name, appends the new entries, and saves — all in milliseconds. It is idempotent
(re-applying skips duplicates) and moves each patch to `patches/applied/` as a receipt.

How to work: READ the chain (and the transcript) as before to decide what to add and where; then
WRITE those decisions as a patch. Patch shape (see the `apply_patches.py` docstring for the full spec):
```json
{ "source": "<label>",
  "chains": { "components/power_cooling.json": { "players": [
    { "company": "Vistra", "domain": "power", "sector": "Generation",       // locator: layer|domain + sector (+sub_sector); used only if the player must be CREATED
      "product": "…",                                                        // used only when created
      "quarterly_data": [ { "quarter": "<label>", "signal": "…", "figure": "…", "topics": [] } ],
      "connects_to": [ { "company": "Meta", "relationship": "…",             // relationship used only if the edge must be CREATED
                         "contracts": [ { "source": "<label>", "signal": "…", "topics": [] } ] } ] } ] } } }
```
Every player in a patch carries its locator even when it already exists — the merge ignores it if
the player is found, and the patch stays self-describing.

Four jobs — all ADD-only, never remove or overwrite existing data:

**JOB 1 — Node-level figures (quarterly_data):**
If the transcript mentions a company already in the chain (revenue, growth %, capacity, demand, shortages), add a `quarterly_data` entry to that player.
```json
{ "quarter": "<label>", "signal": "exact quote or paraphrase", "figure": "the number, or 'no specific figure'" }
```

**JOB 2 — Edge-level deal detail (contracts):**
If the transcript reveals a concrete deal, contract, or commitment on an existing edge (units shipped, $ value, delivery date, deal type), add a `contracts` entry to that edge.
```json
{
  "source": "<label>",
  "signal": "what was said",
  "units": "quantity or 'no specific figure'",
  "value": "$ amount or 'no specific figure'",
  "date_signed": "year/quarter or 'not stated'",
  "type": "supply agreement / deployment / partnership / etc."
}
```

**JOB 3 — New companies:**
If the transcript names a company not yet in the chain that passes the litmus test, add it to the correct layer→sector (or domain→sector) with empty `connects_to` and at least one `quarterly_data` entry from the transcript.

**JOB 4 — New edges:**
If the transcript explicitly states a supply or customer relationship between two companies already in the chain that isn't yet in `connects_to`, add it with any relevant `contracts` entries.

**JOB 5 — Tag every new entry for the derived views (Timelines / Screener / Capex):**
The Timelines, Screener and Capex tabs are GENERATED from the graph by `derive.py` (run by
`graph_build.py`). They are never hand-maintained any more. The generator only knows where an
entry belongs through these optional keys, so add them to EVERY `quarterly_data` entry you write
(and `topics` to every `contracts` entry):
```json
{ "quarter": "<label>", "signal": "...", "figure": "...",
  "topics": ["ocs", "cpo"],          // timeline ids this entry belongs to; [] = none (pure financials)
  "slot":   "guidance",              // OPTIONAL screener column this entry fills (one entry per slot)
  "capex":  { "field": "capex_year", "busd": 220, "display": "~$220B", "period": "2026 plan" } }
```
- `topics` ids = the filenames in `timelines/`: `cpo`, `cpu`, `foundry`, `hbm`, `nand_storage`, `ocs`,
  `optical_speed`, `packaging_substrate`, `power_cooling`, `product_launches`, `silicon_photonics`,
  `supply_tightness`, `transitions`. Always write the key — `[]` opts the entry out of the keyword
  fallback that covers untagged legacy entries.
- `slot` ∈ `revenue_growth` | `guidance` | `backlog_or_b2b` | `supply_status` | `next_catalyst`.
  Tag the ONE best entry per slot; the screener shows the latest-dated tagged entry per slot.
- `capex` (hyperscalers / neoclouds only): `field` ∈ `capex_q` | `capex_year` | `backlog` | `signal`.
  `busd` + `display` (+ `period` for capex_year, `metric`/`growth` for backlog) drive the bar charts.
- Rules the generator enforces: graph keeps full history; every derived view is REPLACE-WITH-LATEST
  per company; curated baseline files (`timelines/*.json`, `company_metrics.json`, `capex_backlog.json`)
  are inputs that are never auto-written and act as fallback; outputs land in `graph/` — never hand-edit those.

**Global enrichment rules:**
- Do NOT invent companies or deals. Only use what the transcript explicitly states.
- Do NOT add a company already in the chain — find it and update it instead.
- Use the same source label consistently across the entire chain (every node/edge touched by one transcript gets the identical label). The label identifies WHICH source document a data point came from. Use the canonical format below — never mix formats.
- Keep every existing node, edge, and data point intact. Only ADD.

**Canonical source-label format (FIXED — use everywhere `quarter`/`source` appears):**

| Source type | Format | Example |
|-------------|--------|---------|
| Earnings call | `[Company] Q[N] FY[YYYY] (MM-DD-YYYY)` | `NVIDIA Q1 FY2027 (05-28-2026)` |
| Event (keynote/conference) | `[Company] [Event] [YYYY] (MM-DD-YYYY)` | `NVIDIA GTC 2026 (03-18-2026)` |
| News / research note | `[Source] (MM-DD-YYYY)` | `Goldman Sachs optical note (04-15-2026)` |

Rules: (1) Always write `FY` for earnings — NVIDIA's fiscal year is offset from the calendar (NVDA Q1 FY2027 = the quarter ending ~April 2026); calendar-year filers (TSMC, SK Hynix) have FY = calendar year. (2) The date in parentheses is the SOURCE DOCUMENT date (earnings-call date / event date / article publish date), NOT the quarter-end date. (3) `[Company]` is the node's canonical name (`NVIDIA`, not `NVDA`).

---

### Workflow 2b — Korean companies via DART (한국 회사)

Korean listed names (SK Hynix, Samsung, Samsung Electro-Mechanics, Hanmi Semiconductor, HD Hyundai
Electric, LS Electric, Simmtech, Daeduck, Soulbrain, Dongjin Semichem, Wonik IPS, Jusung, PSK,
Leeno, ISC, Techwing, EO Technics, Gaonchips, AD Technology, Doosan Enerbility, Hyosung Heavy,
Sanil Electric, Isu Petasys, Mirae Industry, Naver …) have no Motley Fool transcript. Their source
documents are DART filings. Three kinds matter, each on its own clock (verified on 산일전기 2Q26):

| DART filing | When | Goes to | What it gives |
|---|---|---|---|
| 영업(잠정)실적(공정공시) — **잠정실적** | earnings day itself (Sanil: 08-07) | `transcripts/dart/<slug>_prelim_<date>.txt` | revenue / OP / NI table, QoQ + YoY |
| 사업·반기·분기보고서 — **정기보고서** | ~1 week later, ≤45 days after quarter end (Sanil: 08-14) | `transcripts/dart/<slug>_q<N>_<year>_dart.txt` | the full report + full statements |
| 단일판매ㆍ공급계약체결 — **공급계약** | any day, unannounced (Sanil: 06-22, 08-20) | `supply_contracts/<slug>.txt` (one file per company, appended) | customer, amount, % of revenue, period |

So on earnings day only the 잠정실적 numbers can be enriched within the hour; the supply-chain
text (customers, suppliers, backlog) arrives with the 정기보고서 a week or so later. Not every
company files a 잠정실적 (KOSDAQ small caps often don't) — for those, earnings day == 정기보고서 day.

**Universe:** every company in `company_metadata.json` whose `exchange` is KRX/KOSPI/KOSDAQ and
whose ticker is a 6-digit stock code. `dart.py sync` scans the WHOLE DART feed (so 풍산 or any
other Korean filer technically passes by) but keeps ONLY these companies. To cover a new Korean
name (e.g. 풍산), add it to `company_metadata.json` with its stock code — nothing else to configure.
Samsung and Samsung Foundry share 005930 → one filing, fetched once.

**Trigger: the user says `enrich dart`** (no company name — there are dozens of Korean names and
the user will not list them). That one phrase means: run the whole loop below for EVERY new filing.
1. `python dart.py sync` — pulls everything filed on DART since the last sync (the user is on PST;
   DART runs on KST, so "today" simply means everything not yet pulled — `sync` handles the gap).
2. `python dart.py pending` — the queue of saved files that have NOT been enriched yet. Enrich
   every row in it (Step 2), one file at a time, all sections. Never re-enrich a file that is not
   in the queue — the queue is the duplicate guard; `dart/sync_state.json` is the download guard.
3. `python graph_build.py --sync` (this also runs `verify_graph.py` on the labels just applied —
   read its `[fail]`/`[warn]` lines, see Workflow 2), then `python dart.py done` to clear the queue.
4. Report per company: label, what was added (n quarterly_data, n contracts, new edges), and the
   verify result (n pass / n fail, with the reason for each fail).
If the queue is empty after `sync`, say so and stop — do not go looking for more.

**Step 1 — pull (what `enrich dart` runs; manual forms below):**
```
python dart.py corp                     # once; refresh yearly — builds dart/corp_codes.json
python dart.py sync                     # new 잠정실적 / 공급계약 / 정기보고서 for our companies since
                                        #   the last sync; dart/sync_state.json remembers what's saved,
                                        #   dart/pending.json queues what still needs enriching
python dart.py pending / done           # show the enrichment queue / clear it after enriching
python dart.py sync --since 20260801    # backfill from a date
python dart.py fetch --all 2026 2       # bulk-pull one quarter's 정기보고서 for every Korean company
python dart.py fetch "SK Hynix" 2026 2  # one company (quarter 1-4; 4 = 사업보고서)
```
A 정기보고서 file `transcripts/dart/<slug>_q<N>_<year>_dart.txt` holds, in order:
1. header — the exact **source label** to use, rcept_no, filing date, DART URL
2. `## FINANCIAL STATEMENTS` — full BS / IS / CF from `fnlttSinglAcntAll` (연결; 별도 if no consolidated).
   Columns: `account | this period | YTD | same period last year | two years ago`, **KRW (원)**.
   For Q1/Q3 the first amount is the quarter and YTD is cumulative; for H1 and annual read YTD.
3. `## REPORT TEXT` — the whole filing, tables flattened to `a | b | c` rows.

A 잠정실적 file `transcripts/dart/<slug>_prelim_<date>.txt` holds the header + the full text of the
공정공시 (the results table, plus any 첨부/comment the company added).

A 공급계약 file `supply_contracts/<slug>.txt` is one file per company; every 공급계약 공시 is appended
as a `====` block with its own header/label, oldest at the top. The full 공시 text is kept —
계약상대방 (customer, sometimes 비공개), 계약금액, 최근 매출액 대비 %, 계약기간, 판매·공급지역, 조건.

**Step 2 — enrich (Workflow 2, with these Korean-specific rules):**
- **ENGLISH ONLY in the chain.** Every `quarter` / `source` label, `signal`, `figure`, `units`,
  `value`, `type`, `relationship` and `product` you write must contain no Korean characters.
  Translate filing terms as you go: 잠정실적 → "preliminary results", 반기보고서 → "half-year
  report", 분기보고서 → "quarterly report", 사업보고서 → "annual report", 공급계약 → "supply
  contract", 수주잔고 → "order backlog", 신재생 → "renewables", 전력망 → "grid", 가동률 →
  "utilisation", 매출액 대비 → "% of prior-year revenue", 비공개 → "undisclosed". People and
  agencies get romanised names (Park Dong-seok, Korea National Railway). Korean is fine inside the
  source txt files and in this CLAUDE.md — never inside `chains/`. Before finishing, grep the
  entries you added for `[가-힣]` and fix any hit.
- **Never summarise, skim, or sample any DART file — read every line of every file** (정기보고서,
  잠정실적, and every block of a supply_contracts file) before touching the chain. The pipeline
  deliberately saves full text, not extracts; the reading is your job.
- **Source label** = the header's `# source label:` line, e.g. `SK Hynix Q2 FY2026 (08-14-2026)`.
  Korean filers are calendar-year, so FY = calendar year; the date is the FILING date (not quarter-end);
  the 사업보고서 is labelled Q4 of the year it covers (`Samsung Q4 FY2025 (03-15-2026)`).
  A 잠정실적 and the later 정기보고서 for the same quarter carry the same `Q2 FY2026` but different
  dates — both are valid entries; the 정기보고서 entry supersedes for `slot` purposes.
- **잠정실적 →** `quarterly_data` on the company's own node: `revenue_growth` slot (revenue, OP,
  YoY/QoQ % exactly as the table states), `topics: []` unless the company wrote a comment about a
  product. Nothing else — the file has no supplier/customer content.
- **공급계약 →** a `contracts` entry on the edge company → 계약상대방. If that edge doesn't exist
  and the counterparty is already a node, add the edge (JOB 4). If the counterparty is 비공개 /
  not a node, the deal goes on the company's own `quarterly_data` with `slot: backlog_or_b2b`
  and the amount — never invent the customer. Label format for contracts:
  `[Company] DART supply contract (MM-DD-YYYY)` (already written in each block's header). `type` =
  "supply agreement"; `units` = contract term + region; `value` = amount in KRW (and USD/EUR if
  stated) + % of prior-year revenue.
- **Read the ENTIRE filing, every section.** A DART filing is not a call transcript — the
  supply-chain facts are spread across the whole document (사업의 내용, 재무에 관한 사항, 주석,
  이사회/계약 내용, 계열회사, 기타 참고사항 …), and the 주석 (notes) often carry the concrete
  figures (segment revenue, major-customer concentration, purchase commitments, capex in
  progress) that the main sections summarise. Never skim or sample sections. Do not stop at
  `II. 사업의 내용`. If the file is too long for one pass, read it in consecutive chunks until
  the end, then enrich — the pass is complete only when the last line has been read.
  Sections and what they usually yield:
  - `II. 사업의 내용` — 주요 제품 (product mix, % of revenue), 원재료 및 생산설비 (raw-material
    SUPPLIERS by name + purchase amounts = incoming edges; capacity / 가동률 = supply_status),
    매출 및 수주상황 (수주잔고 = backlog_or_b2b, major CUSTOMERS = outgoing edges), 연구개발
    (next-gen products = product_launches / transitions), 기타 참고사항 (contracts, licences).
  - `III. 재무에 관한 사항` + 주석 — 부문별 매출, 주요 고객 매출 비중, 유형자산 취득 (capex),
    건설중인자산, 매입/판매 약정, 우발채무 (long-term supply agreements).
  - `IV~VI. 이사회, 주주, 임원` — usually nothing; still read, JV/투자 결의 can appear here.
  - `VII~IX. 계열회사, 이해관계자 거래, 기타` — related-party supply (e.g. 삼성전자 ↔ 삼성전기),
    material contracts signed after period end.
- Amounts are KRW; keep them as written in `figure` (e.g. `매출 27조 8,000억원`) — do not convert to USD.
- Company names inside the filing are Korean (`SK하이닉스`, `삼성전자`, `한미반도체`). Map to the
  canonical English node name already in the chain (`SK Hynix`, `Samsung`, `Hanmi Semiconductor`);
  never add a Korean-named duplicate.
- A DART filing is the single most reliable source for **who supplies whom in Korea** (원재료
  매입처, 주요 매출처) — it may name a supplier that an earnings call would never mention. Litmus
  test still applies before adding a node.
- Then `python graph_build.py --sync` as usual.

---

### Workflow 2c — US companies via Alpha Vantage (`enrich us`)

US-listed names (NASDAQ/NYSE ticker in `company_metadata.json`, 102 companies) get their full
earnings-call transcript from Alpha Vantage instead of a hand-found Motley Fool URL. `av.py` mirrors
`dart.py`: `sync` → `pending` → enrich → `graph_build.py --sync` → `done`.

**Trigger: the user says `enrich us`.** That means run the whole loop for every new call:
1. `python av.py sync` — reads the earnings calendar, finds OUR companies that reported since the
   last sync, and pulls each transcript that Alpha Vantage has posted. Prints `saved` / `waiting`
   (reported, transcript not up yet — retried next sync, usually the next morning) / `skip`
   (already in `transcripts/` from the Motley Fool days) / `QUOTA` (25 requests/day spent — the
   rest carries over to tomorrow). If a call is `waiting` and the user needs it today, fall back to
   the Motley Fool paste (Workflow 2) under the same label.
2. `python av.py pending` — the queue. Enrich every row (Workflow 2, all four jobs + JOB 5 tags),
   reading the whole file. Never re-enrich a file that is not in the queue.
3. `python graph_build.py --sync` (runs `verify_graph.py` on the labels just applied — read its
   `[fail]`/`[warn]` lines), then `python av.py done`.
4. Report per company: label, what was added, verify result.
If the queue is empty after `sync`, say so and stop.

File format `transcripts/av/<slug>_q<N>_<year>.txt`: `SOURCE:` / `CALL DATE:` / `QUARTER:` /
`# source label:` header (use that label verbatim), then one paragraph per speaker turn,
`Speaker (Title): text`. It is the whole call — prepared remarks and every analyst question.
The quarter in the label is the company's FISCAL quarter, derived from the company's latest label
already in the graph (+1), so labels stay consistent with history (`NVIDIA Q3 FY2027 (…)`).
Manual pull: `python av.py fetch NVDA 2027Q3 --date 2026-11-19`; `python av.py calendar` lists
upcoming calls for our companies.

### Workflow 2d — Taiwan / Japan / Europe / HK / China via Investing.com (`enrich intl`)

The 88 names whose exchange is neither US nor Korean (Alchip, MediaTek, Nanya Technology,
ASMPT, Tokyo Electron, Advantest, SUMCO, Infineon, ASM International …) hold quarterly calls
but publish no written transcript, and no free API carries them. Investing.com transcribes the
ENGLISH-language calls as articles (full speaker turns + Q&A, ~15–20k words) within a day.
`investing.py` mirrors `dart.py`/`av.py`: `sync` → `pending` → enrich → `graph_build.py --sync` → `done`.
It reaches the site with a Chrome TLS fingerprint (`curl_cffi`) because plain requests get 403 —
public article pages only, one request per second. Fallback if that ever breaks: open the article
in Chrome and paste (Workflow 2) under the same label.

**Trigger: the user says `enrich intl`.**
1. `python investing.py sync` — one site search per company, downloads every transcript not yet
   saved. Prints `saved` / `FAIL`. Takes ~2–3 minutes.
2. `python investing.py pending` — the queue. Enrich every row (Workflow 2, all four jobs + JOB 5),
   but **at most the 2 most recent quarters per company** — anything older in the queue is marked
   done without enriching (history, not signal). Duplicates never reach the queue: `sync` skips a
   call the graph already carries under another source and same-call repeat articles.
3. `python graph_build.py --sync` (verify_graph runs on the labels just applied), then `python investing.py done`.
4. Report per company: label, what was added, verify result.

**Coverage reality (checked 2026-08-31):** Investing.com has Alchip, MediaTek, ASMPT, Nanya
Technology, Tokyo Electron, Advantest, SUMCO, Infineon, Sivers … It does NOT have the companies
whose calls are held in Chinese/Japanese — Quanta, Wiwynn, Wistron, Unimicron, Foxconn, GlobalWafers,
Yageo, Lasertec. For those the only free sources are the MOPS 法說會 deck + TWSE monthly revenue
(`openapi.twse.com.tw/v1/opendata/t187ap05_L`), which are not transcripts — do not enrich from
them unless the user decides to (open question, see memory).

File format `transcripts/investing/<slug>_q<N>_<year>.txt`: `SOURCE:` (article URL) / `TITLE:` /
`CALL DATE:` (article publish date) / `QUARTER:` / `# source label:` header, then one paragraph per
speaker turn `Speaker, Title, Company: text`. The first few paragraphs are the article's own summary
("Key Takeaways") — the transcript proper starts after them; enrich from the transcript, not the summary.
A `# note: prepared remarks only` header line means Investing.com did not include the analyst Q&A
(happens for some Japanese calls, e.g. TDK, Advantest) — enrich what is there, don't go looking for more.
**Label FY for Japanese March-FY companies** is derived from the graph's latest label (+1 quarter) or,
with no history, from the article date (Q1/Q2 → FY = year+1; Q3/Q4 → FY = year), NOT from the title —
Investing.com's title years are inconsistent for Japan. Result matches what the graph already carries
(`Tokyo Electron Q4 FY2026 (04-30-2026)` → `Tokyo Electron Q1 FY2027 (07-31-2026)`). A call the graph
already has under another source (Motley Fool era) is skipped, not re-saved.
Manual pull: `python investing.py fetch <article url> [--company "Name"]`.

## Rules for the AI assistant working in this repo

- Preserve existing nodes, edges, and data. ADD only. Never silently restructure curated chains.
- Enrichment NEVER writes to `chains/` directly — it writes a patch to `patches/` and lets
  `apply_patches.py` (via `graph_build.py`) merge it. Parallel jobs overwrite each other otherwise
  (Workflow 2 explains the lost-update problem). Skeleton builds (Workflow 1) still write `chains/` directly —
  they create a new file, so nothing to collide with.
- Build edges as SPECIFIC directed relationships (`connects_to`), not full layer-to-layer links.
  Same-layer edges allowed when real (e.g. HBM → CoWoS). No-relationship nodes get `connects_to: []`.
- Edges are objects carrying `contracts[]`; skeleton leaves contracts empty, transcripts fill them.
- Follow FIXED layer/domain slugs and the `{company, product, connects_to, quarterly_data}` player shape (nested under layer→sector).
- Apply the litmus test before adding any company.
- Tag every new `quarterly_data` / `contracts` entry with `topics` (plus `slot` / `capex` where relevant) —
  the Timelines, Screener and Capex tabs are derived from these tags (Workflow 2, JOB 5). Never hand-edit `graph/`.
- Keep new Python explicit and commented; explain new concepts to the builder.
- Don't build future phases (scheduler, graph-merge, web) until the current phase is solid.
- Return strict JSON when asked for chain data — no markdown code fences, no prose around it.
