# AI Supply Chain

A living map of the **global AI / semiconductor supply chain** as a connected graph —
every supplier, customer, and deal, extracted from earnings calls and connected.
Click any company and the whole supply web lights up.

**Live app:** [gijun42.com](https://gijun42.com) — Next.js on Vercel (see [`web/`](web/README.md)). **Current graph:**
264 companies · 1,067 directed edges · 20 product chains · 174 source transcripts.

## Quant: does "sold out" move stocks? (`quant/`)

An event study on the hand-labeled **"capacity sold out"** signal across 71 US-listed earnings calls: entry at t+1 close, +5/+10/+20-trading-day windows, abnormal returns vs. SOXX/SPY/QQQ, one-sample t-tests and hit rates. Code and outputs live in [`quant/`](quant/) (`event_study.py`, `results.json`).

---

## What makes it different

1. **A graph, not a layer cake.** Layers exist (memory → packaging → foundry → …),
   but every connection is a *specific directed edge* between two companies —
   AWS → Anthropic, SK Hynix → TSMC — never "layer N connects to layer N+1".
   Companies that appear in many chains merge into shared hubs (TSMC sits in 16
   chains, ASML in 15, Amkor in 14).

2. **Edges carry deals, not just lines.** An edge holds the actual contracts on the
   relationship — units, dollar values, dates — and accumulates new entries every
   quarter. Examples currently in the graph: Anthropic → AMD (up to 2 GW of MI450 in
   Helios racks), Nebius → Meta ($27B over 5 years), Vistra → Meta (nuclear PPAs),
   AXT → Coherent / Lumentum (InP long-term supply agreements).

3. **Generations are separated.** `nvda_b200` and `nvidia_vera_rubin` are different
   chains on purpose — the investment signal is the *transition delta* (HBM3E→HBM4
   content growth, copper→optical, CPO penetration, attach ratios), not a static
   snapshot.

4. **Transcript-grounded only.** Every data point carries a canonical source label
   (`NVIDIA Q1 FY2027 (05-28-2026)`) pointing at the earnings call, official IR
   document, or SEC filing it came from. No news scraping, no invented figures.
   Enrichment is ADD-only: existing nodes, edges, and history are never dropped.

## The web app (`web/`)

| Tab | What it shows |
|---|---|
| **Graph** | 3D force graph of the merged supply web — search, filter by chain/layer/domain, click for the node dossier |
| **Chain 2D** | One product chain at a time, top-down layer flow with de-spaghettied edges |
| **Generations** | The transition engine — B200→Vera Rubin, MI355→MI450, Trainium2→3, TPU v7→v8: who's retained, gained, lost |
| **Timelines** | Hand-curated thematic tables: CPO, HBM, foundry roadmaps, supply tightness, 800 VDC transition, … |
| **Screener** | One row per company: latest revenue/growth, guidance, backlog, supply status, next catalyst |
| **Capex** | Hyperscaler + neocloud money view — capex (the demand signal) and backlog/RPO/contracted revenue, with sourced bar charts |
| **Coverage** | The enrichment queue: each company's earnings calendar joined with data freshness — what to enrich next |

## How data gets in (the enrichment loop)

`Transcript: <company>` runs a fixed six-step pipeline:

1. **Fetch** the latest full earnings transcript (Motley Fool first for US names;
   official IR / SEC 8-K as fallback) → save under `transcripts/<sector>/` with a
   source header.
2. **Enrich** every chain where the company is a node — add `quarterly_data` to
   nodes and `contracts` to edges. ADD-only; new companies/edges only when the
   transcript states them and they pass the litmus test (*"does this company's
   stock directly benefit from the product being built and sold?"*).
3. **Verify** — JSON validity plus internal consistency (segments sum to totals).
4. **Rebuild** the merged graph: `python graph_build.py` → `graph/merged_graph.json`.
5. **Timelines** — update the relevant thematic tables (replace-with-latest).
6. **Screener** — replace the company's `company_metrics.json` row with the new quarter.

Then `npm run sync` in `web/` copies everything into `web/public/data` and a push to
`main` deploys via Vercel.

## Repository layout

```
chains/               one JSON per product chain (accelerators / components / manufacturing)
graph/                merged_graph.json — built by graph_build.py, never edited by hand
timelines/            hand-curated thematic tables (13)
reports/              per-company equity-research dossiers (42)
transcripts/          source documents, one folder per sector (174 files)
company_metrics.json  screener — one latest-quarter row per company
company_metadata.json tickers / exchanges / listing status (267 companies)
capex_backlog.json    hyperscaler + neocloud capex & backlog (feeds the Capex tab)
taxonomy.py           the fixed 13-layer / 4-domain vocabulary (single source of truth)
graph_build.py        merges all chains by company name into the nodes+edges graph
web/                  the Next.js app (see web/README.md; Vercel root directory = web)
```

## Working on it

- **Rebuild the graph** after touching any chain: `python graph_build.py`
- **Run the app**: `cd web && npm install && npm run dev` (the predev hook syncs data)
- **Division of labor**: humans own the chain *structure* (which companies, which
  edges); AI assistants own the repetitive transcript enrichment. Rules for
  assistants live in [`CLAUDE.md`](CLAUDE.md) — read it before changing anything.
