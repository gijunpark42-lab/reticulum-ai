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
   The chain structure (who supplies whom, the edges, multi-tier links) is the project's real
   value and is curated by the user. When updating, NEVER drop or overwrite existing nodes, edges,
   or data. Only ADD. When in doubt, preserve.

2. **Division of labor:**
   - The **human** owns the chain STRUCTURE — which companies, which tiers, which edges, multi-tier
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

This is NOT a 9-layer cake where every company in tier N connects to every company in tier N+1.
Tiers exist as **layers**, but every connection is a **specific directed edge** between two nodes.

Example of the difference:
- WRONG (flat layers): "hyperscaler" tier → "ai_lab" tier, implying AWS+Google+Meta all feed
  OpenAI+Anthropic+xAI equally.
- RIGHT (graph): AWS → [OpenAI, Anthropic, xAI]; Google Cloud → [Gemini, Anthropic];
  Azure → [OpenAI, Anthropic]; Meta → [] (self-hosted, no outgoing edge).
  Result: the Anthropic node is a HUB with incoming edges from AWS, Google, and Azure.

### Two kinds of connection

**(1) Edges INSIDE a chain file — the `connects_to` field on each player.**
- Edges usually go to the next tier (AWS → OpenAI), but **same-tier edges are allowed and
  expected** when companies genuinely connect (e.g. SK Hynix's HBM gets attached to TSMC's CoWoS,
  both around component/packaging → SK Hynix connects_to TSMC).
- Only create an edge where a REAL supply/customer relationship exists. Do not fully connect tiers.
- A node with no real outgoing relationship gets `"connects_to": []`.

**(2) Edges ACROSS chain files — automatic, by company name (built later).**
- Each product has its own chain file ON PURPOSE, so that the same company appearing in many
  chains becomes a shared hub when merged. (This is why nodes are split per product — to connect
  them later, not to keep them separate forever.)
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

```json
{
  "company": "NVIDIA",
  "chain_focus": "Vera Rubin GPU platform",
  "flow": [
    {
      "tier": "component",
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
}
```

- `flow`: ordered list of tiers (variable length).
- `players`: `{company, product, connects_to, quarterly_data}`.
  - `connects_to`: outgoing edges (objects with `company`, `relationship`, `contracts[]`).
  - `quarterly_data`: node-level signals/figures about the company itself.
- A company MAY appear in more than one tier if it genuinely plays multiple roles
  (e.g. Corning = optical fiber in `component` AND glass substrate in `raw_material`). Intentional.

### Standard tiers (FIXED — use these names, in this order)

```
equipment        # PVA TePla, AIXTRON, ASML/AMAT/Lam/KLA/TEL, Besi
raw_material     # AXT (InP), Soitec, Corning, Shin-Etsu, SUMCO, JSR, Resonac
epiwafer         # IQE, VPEC, GlobalWafers, TSMC front-end
component         # the chip/part: HBM (SK Hynix/Micron/Samsung), MLCC (Murata/TDK),
                  # lasers/EML (Lumentum/Coherent/AAOI), DSP (Marvell), logic die (TSMC), substrate
packaging        # CoWoS (TSMC), OSAT (Amkor/ASE), ABF substrate (Ibiden/Unimicron)
switch_system    # NVIDIA NVLink, Broadcom Tomahawk/Jericho, Marvell, optical transceivers
oem              # Foxconn, Quanta, Wistron, Supermicro, Dell, Arista
hyperscaler      # Microsoft/AWS/Google/Meta/Oracle + neoclouds (CoreWeave, Nebius)
ai_lab           # OpenAI, Anthropic, Google (Gemini), xAI, Mistral, Perplexity, Cursor
```

**Domains that must eventually be represented** (across chains/tiers): MLCC, memory (HBM/DRAM),
photonics/optical, CPU, power semiconductors, packaging, substrate, foundry, AI labs, cloud/neocloud.

### Future tiers (define when needed, don't build yet)
```
power            # Vertiv, Eaton, GE Vernova, Monolithic Power — transformers, VRMs, turbines
cooling          # liquid cooling, thermal
```
Power/cooling are separate sub-chains that attach to a datacenter/cloud node later (its own edges).

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
3. **Saves** back (never drop existing nodes/edges/data).

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
- **Scraping:** `requests` + `BeautifulSoup` (Motley Fool pages; `<p>` tags).
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
├── .env                      # ANTHROPIC_API_KEY (gitignored)
├── .gitignore
├── chains/                   # one JSON per product chain
│   ├── nvidia_vera_rubin.json
│   ├── google_tpu_v6(Trillium).json
│   └── ...
└── transcripts/
    └── nvda_q1_2027.txt
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
- Use ONLY the standard tier names, in order: `equipment`, `raw_material`, `epiwafer`, `component`, `packaging`, `switch_system`, `oem`, `hyperscaler`, `ai_lab`. Skip tiers that don't apply.
- For every player, name the **specific** product in this chain (e.g. SK Hynix → "HBM4 stacks", not "memory").
- Build edges as **specific directed relationships** — do NOT connect every company in one tier to every company in the next. Only create an edge where a real supply/customer relationship exists.
- Same-tier edges are allowed when real (e.g. HBM supplier → packaging fab).
- A player with no real outgoing relationship gets `"connects_to": []`.
- All `contracts` fields start empty `[]` — transcript enrichment fills them later.
- The chain must reach a final end customer (`hyperscaler` and/or `ai_lab`).
- Apply the litmus test before including any company.
- After writing the file, run `graph_build.py` to rebuild `merged_graph.json`.

**Shape every player must follow:**
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

**Output:** The existing chain JSON is updated in place (ADD-only). Then `graph_build.py` is re-run.

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
If the transcript names a company not yet in the chain that passes the litmus test, add it to the correct tier with empty `connects_to` and at least one `quarterly_data` entry from the transcript.

**JOB 4 — New edges:**
If the transcript explicitly states a supply or customer relationship between two companies already in the chain that isn't yet in `connects_to`, add it with any relevant `contracts` entries.

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

## Rules for the AI assistant working in this repo

- Preserve existing nodes, edges, and data. ADD only. Never silently restructure curated chains.
- Build edges as SPECIFIC directed relationships (`connects_to`), not full tier-to-tier links.
  Same-tier edges allowed when real (e.g. HBM → CoWoS). No-relationship nodes get `connects_to: []`.
- Edges are objects carrying `contracts[]`; skeleton leaves contracts empty, transcripts fill them.
- Follow FIXED tier names and the `{company, product, connects_to, quarterly_data}` shape.
- Apply the litmus test before adding any company.
- Keep new Python explicit and commented; explain new concepts to the builder.
- Don't build future phases (scheduler, graph-merge, web) until the current phase is solid.
- Return strict JSON when asked for chain data — no markdown code fences, no prose around it.
