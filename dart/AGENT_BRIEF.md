# Brief for a DART enrichment reader (one company per agent)

You are enriching the AI/semiconductor supply-chain graph in this repo from Korean DART filings.
You READ files and WRITE ONE patch JSON. You never edit anything under `chains/` — a separate
script applies patches so parallel readers cannot clobber each other.

Repo root: `C:\Users\calif\OneDrive\Desktop\earnings-ai`

## 1. Read the rules first
Read `CLAUDE.md` sections "How enrichment works", "Workflow 2" (JOB 1-5, canonical label format,
global rules) and "Workflow 2b — Korean companies via DART" in full before touching any file.

## 2. Read EVERY line of EVERY file you were given
The files are large (3,000–12,000 lines). Read them in consecutive chunks with the Read tool
(offset/limit ~300 lines per call because table rows are long) until you have reached the last
line. Do not skim, sample, grep-only, or stop at section II. The notes (주석), section XI
(disclosed contract status) and the related-party sections carry concrete figures the summary
sections lack. If a `supply_contracts/<slug>.txt` file is in your list, read every `====` block.

## 3. Find the company in the graph
`grep -rn '"company": "<Canonical Name>"' chains/` — note every chain file it appears in and read
that node's existing `product`, `connects_to` and `quarterly_data` so you do not duplicate an entry
that is already there (an earlier quarter's DART entry may exist — that is fine, add the new
quarter). Also grep for each customer/supplier the filing names, to know which counterparties are
already nodes (only those can receive an edge).

## 4. What to extract (all of it, with dates)
Write entries the way the existing Sanil Electric entries in `chains/components/power_cooling.json`
are written — dense, factual, numbers exactly as filed, every date spelled out. Typical set for a
half-year report (adapt to what the filing actually contains):
- confirmed P&L + mix + geography (slot `revenue_growth`)
- orders / backlog / customer concentration (slot `backlog_or_b2b`)
- capacity, utilisation, capex programme, plant expansion (slot `supply_status`)
- new products, R&D pipeline, charter changes, ratings, corporate events (slot `next_catalyst`)
- disclosed contract book (section XI) and raw-material suppliers (no slot)
- anything AI / data-center / HBM / advanced-packaging / CPO specific the filing says
One slot per entry, at most one entry per slot. `topics` on EVERY entry — ids are the filenames in
`timelines/` (`cpo, cpu, foundry, hbm, nand_storage, ocs, optical_speed, packaging_substrate,
power_cooling, product_launches, silicon_photonics, supply_tightness, transitions`); `[]` if none.
A preliminary-results file (`*_prelim_*.txt`) yields ONE entry: slot `revenue_growth`, `topics: []`.
A supply-contract block yields a `contracts` entry on the edge company → counterparty when the
counterparty is already a node (add the edge if missing); otherwise ONE `quarterly_data` entry on
the company's own node with slot `backlog_or_b2b` (fold the latest backlog figure from the report
into that entry's `figure` so the screener keeps both). Never invent the counterparty.

## 5. Labels and language — hard rules
- `quarter` / `source` = the `# source label:` line in the file header, verbatim
  (`SK Hynix Q2 FY2026 (08-14-2026)`, `Techwing DART supply contract (08-10-2026)`).
- ENGLISH ONLY in everything you write. Zero Korean characters in the patch. Translate:
  잠정실적 → preliminary results, 반기보고서 → half-year report, 공급계약 → supply contract,
  수주잔고 → order backlog, 신재생 → renewables, 전력망 → grid, 가동률 → utilisation,
  매출액 대비 → % of prior-year revenue, 비공개 → undisclosed, 연결/별도 → consolidated/separate.
  Romanise people (Park Dong-seok) and agencies (Korea National Railway). Keep KRW amounts as
  filed (KRW 314,502M); add USD/EUR only when the filing states them.
- Every date in a signal spelled out with the year (2026-06-30 or 06-30-2026). Never "(03-27)".
- Company names in the patch must be the canonical English node names already used in `chains/`.

## 6. Output — write exactly one file, then stop
`dart/patches/<slug>.json` (slug = lowercase letters/digits of the canonical name, e.g.
`skhynix.json`, `hdhyundaielectric.json`). Shape:
```json
{
  "company": "SK Hynix",
  "quarterly_data": [
    {"quarter": "SK Hynix Q2 FY2026 (08-14-2026)", "signal": "...", "figure": "...",
     "topics": ["hbm"], "slot": "revenue_growth"}
  ],
  "edges": [
    {"company": "TSMC", "relationship": "one-line description of what flows",
     "contracts": [{"source": "SK Hynix Q2 FY2026 (08-14-2026)", "signal": "...", "units": "...",
                    "value": "...", "date_signed": "...", "type": "supply agreement", "topics": ["hbm"]}]}
  ]
}
```
`edges` may be `[]`. If the same filing covers two canonical nodes (Samsung and Samsung Foundry
share one filing) write two patch files, one per node, with the foundry-specific content on
`Samsung Foundry`. If a slot has nothing to say, omit it — do not pad.
Before finishing: re-open your patch, confirm it parses as JSON, contains no `[가-힣]` character,
and every `quarter`/`source` matches a file header exactly. Your final message to the caller is
just: the patch path(s), the count of entries, and any counterparty you wanted an edge for but
that is not a node (name + what the filing says about them, one line each).
