# Investment feature ideas — September 2026

Written 2026-09-05 for the project owner. Every number below was computed from files already in the repo: `graph/merged_graph.json` (312 companies, 1,250 edges, 20 chains, 1,986 `quarterly_data` entries, 489 contracts on 411 edges — 839 edges still carry none) and `graph/verification.json` (2,475 entries: 1,682 pass / 417 unchecked / 258 fail / 118 warn; 31 source labels have no file on disk).

**Ground rules respected:** transcript/filing-grounded data only (no news scraping, no "knowledge edges"), English UI, the generation delta is the differentiator, accuracy over volume, the litmus test for nodes, no Quant tab.
**Being built right now by sibling agents — not repeated here:** the Exposure tab (per-chain "who benefits" ranking, basket export, customer concentration, generation delta), source-evidence buttons (`graph/evidence.json`), the Ask-the-Graph chat, richer NodePanel/search, sortable/exportable tables, 2D/3D focus modes. The ideas below feed those or sit beside them.
**Effort key:** S = a day or less, M = 2–4 days, L = a week or more. Every idea is deterministic Python in the style of `derive.py` plus a React view. Nothing calls an LLM at build time.

## Priority 1 — foundations (small, and everything else stands on them)

### 1. "What changed since last build" — graph changelog (S/M)
- **You see:** a *What's new* panel: new companies, new edges, new `quarterly_data`/contract entries and — honestly — removals, grouped by source label and chain, since the previous build or a chosen date.
- **Why an investor cares:** after an earnings week you want the delta, not the whole graph. August 2026 alone added 762 entries; the 2026-08-29 DART import and the 2026-09-05 cleanup (about 110 nodes removed, 145 filed deals folded onto the filers as `counterparty` entries) are invisible today unless you read git.
- **Data today:** 55 commits of `graph/merged_graph.json`, 43 receipts in `patches/applied/` (each with its label), branch `pre-cleanup-2026-09-05`. **Needs:** `graph_build.py` diffs the previous graph (`git show HEAD:graph/merged_graph.json`) against the new one and writes `graph/changelog.json`; `sync-data.mjs` copies it.
- **Depends / risks:** nothing. A cleanup shows as "110 nodes removed" — show it; ADD-only is an enrichment rule, not a display rule.
- **Transcript-only:** a pure diff of stored data.

### 2. Rebuild-time alerts, no external services (S, after #1)
- **You see:** an inbox written by the build: "new *Supply tight* badge", "guidance raised", "new contract of $1B or more", "edge became two-sided", "first data for a node", "verification fail introduced", "node crossed 180 days stale".
- **Why:** the build that applied `Nebius Q1 FY2026 (05-13-2026)` would have raised "Nebius → Meta: $27B over 5 years ($12B dedicated + $15B optional)". The project's own evidence (`agent/README.md`: a twelve-line regex ties a single LLM call on the sold-out signal) says rules, not a model, are the right tool here.
- **Data today:** the badge regexes in `web/src/lib/signals.ts` (`BADGE_RULES`), `slot`/`topics` tags, `verification.json`. **Needs:** `graph/alerts.json` derived from the #1 diff; a bell in the header; `graph_build.py` prints the same list.
- **Depends / risks:** #1. The *tight* regex fires on "demand exceeds" phrasing; every alert links to the entry and its label so it is judged in one click.
- **Transcript-only:** alerts are only about entries already in the graph.

### 3. Trust score per company and per edge (S)
- **You see:** on the NodePanel and as a Screener column: "machine-verified 82% (n=11)", plus counts of "not machine-checkable" and "source file missing"; on each edge a corroboration chip: two-sided / multi-source / single-source / structure only.
- **Why:** accuracy over volume means showing where the evidence is thin. Today Navitas, ASMPT and TTM Technologies verify at 100%; Mirae Industry at 38%, Soulbrain 40%, Tokyo Electron 45%. Only 70 of the 411 contract-bearing edges are two-sided (both companies name each other on their own calls); 332 are single-source. The sibling evidence buttons show one excerpt; this aggregates them into a filterable badge.
- **Data today:** `graph/verification.json` (`entries[].verdict/issues`, `edges[].tier`). **Needs:** add it to the `singles` list in `web/scripts/sync-data.mjs` (not synced today) and about 40 lines of aggregation in `derive.py`.
- **Depends / risks:** none. Many DART "fails" are verifier limits (rounded KRW billions against 백만원 tables, computed sums) — label them "not machine-verified", never "wrong".
- **Transcript-only:** the score is about provenance; it adds no data.

### 4. Data-freshness SLA view, plus an own-call freshness fix (S)
- **You see:** per pipeline and exchange, expected lag (Alpha Vantage about a day after the call; DART 잠정실적 same day, 정기보고서 up to 45 days after quarter end; Investing.com about a day) versus actual, and fresh / aging / no-data counts.
- **Why:** it shows where the map is blind. Today NASDAQ is 61 fresh (data since July 2026) / 5 aging / 3 none; TWSE 4 / 13 / 12; TSE 11 / 17 / 14; Korea 26 / 0 / 9; private 13 / 18 / 36. Taiwan is the weak spot because Investing.com does not carry Chinese-language calls (Quanta, Wiwynn, Wistron, Foxconn … — CLAUDE.md, Workflow 2d).
- **Data today:** label dates, `company_metadata.json`, `av/sync_state.json` (`last_sync`, `waiting`), `dart/sync_state.json`, `investing/sync_state.json`. **Needs:** `graph/freshness.json` from `derive.py`; the sync states copied by `sync-data.mjs`.
- **Bug to fix first:** `nodeSignalMeta` in `web/src/lib/signals.ts` takes the newest date of *any* label on a node, so Micron looks fresh as of 08-26 because NVIDIA mentioned it, and `Coverage.tsx` can mark an un-enriched call "Covered" on the strength of a peer's mention. Freshness must use labels whose company prefix is the node itself.
- **Transcript-only:** metadata about stored data.

### 5. Watchlist overlay (S)
- **You see:** star companies (kept in `localStorage`, no account); the Graph highlights them, Screener / Timelines / Coverage / alerts gain a "watchlist only" filter, and #1/#2 show "changes to your watchlist since your last visit". The Exposure tab's basket export becomes "add basket to watchlist".
- **Why:** it turns the map into a daily tool. A watchlist of Coherent, Lumentum and AXT would have surfaced `AXT Q2 FY2026 (07-30-2026)` (long-term InP supply agreements with both) and `Coherent Q4 FY2026 (08-12-2026)` together.
- **Data today:** everything. **Needs:** about 150 lines of React and a `lastVisit` timestamp.
- **Depends / risks:** #1/#2 for "since last visit". Signals only — no P&L, no returns (no Quant tab).
- **Transcript-only:** nothing new is ingested.

## Priority 2 — investor views the existing tags can already support

### 6. Supply-tightness heatmap over time (M)
- **You see:** rows = layers/sectors, columns = quarters (label dates), cell colour = how many suppliers in that sector said "sold out / allocated / constrained" that quarter, with the quote and label on hover. The curated "Tight until" column in `timelines/supply_tightness.json` stays as the baseline.
- **Why:** direction beats a snapshot. The graph holds tight-supply statements from 62 companies, 13 of them in two different quarters — Micron (03 → 06-2026), ASML (04 → 07), Lumentum, Fabrinet and MACOM (05 → 08) — enough to show whether optical and memory tightness is spreading or easing. The Screener's `supply_status` slot is replace-with-latest (69 companies, one with two dated entries), so this history is invisible today.
- **Data today:** all `quarterly_data` (history is kept), `topics: ["supply_tightness"]` tags, the *tight* regex for legacy entries. **Needs:** `graph/tightness.json` (company × quarter × sector); optionally a `tight_until` string on new entries.
- **Depends / risks:** none. "Constrained" also appears in buyer complaints (Dell ranking DRAM first) — split "supplier says" from "buyer says".
- **Transcript-only:** counts of stored, labeled statements.

### 7. DART supply-contract and backlog tracker (M)
- **You see:** per Korean filer, a bar per 공급계약 (amount, % of prior-year revenue, term, counterparty) on a timeline, and backlog per quarter — the backlog-to-revenue trend the filings make possible.
- **Why:** these are filed numbers, not call colour. Sanil Electric: TMEIC USA reactors KRW 51.2B / USD 36.3M = 10.20% of FY2025 revenue (2026-08-17 to 2027-08-26), backlog KRW 556.8B at 06-30-2026 (+16.6% QoQ), top-4 customers 89.5% of sales. LS Electric: US "Big Tech" data-center power equipment KRW 230.9B (4.65%), parent backlog KRW 6,999.8B (+24% QoQ). Hyosung backlog KRW 23,834.4B (+49.6% since year-end); Techwing → Micron KRW 9.18B (5.77%).
- **Data today:** `supply_contracts/*.txt` (5 companies, 7 filings), the entries and edges enriched under `… DART supply contract (MM-DD-YYYY)` labels, `backlog_or_b2b` slot entries. **Needs:** the numbers sit inside free-text `figure` strings — add a numeric tag on new entries, e.g. `"kpi": {"kind": "backlog" | "contract", "krw_b": 556.8, "pct_prior_rev": 10.2, "asof": "2026-06-30"}` (same pattern as `capex`), and back-tag the roughly 30 existing Korean entries once.
- **Depends / risks:** `dart.py sync` cadence. The revenue base differs per filing (HD Hyundai's 3.06% is against FY2022 revenue, as filed) — always show the base.
- **Transcript-only:** DART filings are the approved Korean source.

### 8. Generation-transition dashboard v2: content per unit and socket history (M/L)
- **You see:** per transition (B200 → Vera Rubin, MI355 → MI450, Trainium2 → 3, TPU v7 → v8), a table per layer of content per accelerator or rack in the current versus next generation (stacks, GB, optical attach, CPO share, $/GW) with the transcript sentence behind each cell, and a timeline of socket wins and losses (entry dates from patch receipts and git history).
- **Why:** this is the thesis, and the engine today (`web/src/lib/transitions.ts`) only knows membership: NVIDIA 31 retained / 27 gained / 9 lost; all three HBM vendors read "HBM3E 8-Hi/12-Hi stacks → HBM4 DRAM stacks" with no quantity. Transcript facts exist to fill cells: `NVIDIA Q2 FY2027 (08-26-2026)` — Vera Rubin (HBM4) production shipments began August 2026, about 20% of data-center revenue in Q3 FY2027; `SK Hynix Q1 FY2026 (04-23-2026)` — 192 GB SOCAMM2 in mass production for Vera Rubin; the HBM3E → HBM4 stage table in `timelines/transitions.json`.
- **Data today:** `products[]` per chain, `timelines/transitions.json`, `timelines/product_launches.json`. **Needs:** an owner-curated `content/<transition>.json` baseline (content per unit is structure, so human-owned like `timelines/`) that `derive.py` turns into deltas, and a way to tell "lost" from "not yet curated" (a `status` on the row, or carrying customers forward into the next-gen chain).
- **Depends / risks:** #1 for socket history. The richest content numbers in the graph today (dollar content per NVL72, attach ratios 1:8–12) come from `Goldman Sachs optical note (04-17-2026)` — 51 entries with no file on disk. Do not build on them (see debts).
- **Transcript-only:** cells cite transcripts or the owner's own research, never sell-side notes.

### 9. Customer concentration and dependency risk, numeric (M — builds on Exposure)
- **You see:** per supplier, disclosed customer shares as bars with the filing behind them, and the mirror view per customer ("who depends on you"); plus structural dependency from edges (the share of a node's outgoing edges that land on one hub).
- **Why:** SK Hynix's half-year report shows two customers above 10% (13.35% and 13.03%, unnamed); Supermicro's top customer went 63% → 27% → 28% while customers above $1B rose to nine; HD Hyundai Electric: NextEra 15.9% of H1 sales; Hyosung's US arm: Constellation 15%, Intersect 13%; Samsung: top-5 about 25%.
- **Data today:** 41 contracts typed "customer share", 145 `counterparty` entries, roughly 227 concentration-like statements across 97 companies — all free text. **Needs:** a `share: {"pct": 15.9, "of": "H1 2026 revenue"}` tag on those contracts and entries. The Exposure tab owns the ranking UI; this adds the numbers and the history.
- **Depends / risks:** Exposure tab. Unnamed ">10% customers" stay unnamed — never guess.
- **Transcript-only:** shares come from filings and calls only.

### 10. Capex flow-through: hyperscaler → supplier (M)
- **You see:** pick a buyer (Meta, Microsoft, Amazon, Google, OpenAI, CoreWeave); see its capex/backlog tags, then the suppliers one and two edges upstream with the contracts on those edges, ranked by how many chains the edge appears in.
- **Why:** capex is the demand signal for everyone below. Meta has 50 incoming edges (16 with contracts) and one outgoing; OpenAI 43 in, 0 out; Google 58 in (22 with contracts). On those edges: Vistra → Meta PPAs (`Vistra Q2 FY2026 (08-06-2026)`: PPAs plus Cogentrix could add about $700M to the 2027 EBITDA midpoint), Nebius → Meta $27B, CoreWeave backlog $104.2B (+246% YoY) tagged `capex.field = backlog`.
- **Data today:** edges; `capex` tags on only 6 entries (CoreWeave 3, IREN 2, SoftBank 1). **Needs:** capex tags on the Big-4 — Meta, Microsoft, Amazon and Google each carry 5–6 capex-mentioning entries and zero tags, so the Capex tab's Big-4 bars still come from the curated baseline; a two-hop traversal in `derive.py`.
- **Depends / risks:** none. 839 of 1,250 edges have no contracts — show structure-only edges dimmed.
- **Transcript-only:** edges and tags only.

### 11. Hub centrality and single points of failure (S)
- **You see:** a ranked hub table (degree, in/out, chains) and, per chain, the sectors served by exactly one player — the chokepoints — each with the hub's latest tight-supply statement.
- **Why:** TSMC has degree 248 (198 incoming) across 16 chains and is the only player in "Wafer-Level Packaging (CoWoS, SoIC)" in at least nine of the ten accelerator chains; ASML is alone in Lithography in the AMD, AWS, Broadcom and NVIDIA chains; Amkor is the only OSAT in the AWS, Broadcom and both NVIDIA chains; Ibiden is alone in FC-BGA in the Broadcom and Google chains. Read with `TSMC Q2 FY2026` ("packaging capacity is so tight that now it's limiting my customers' growth"), one sentence gates ten chains. It also flags pure sinks (Anthropic: 32 in, 0 out) and pure sources (Applied Materials: 30 out, 1 in).
- **Data today:** all in `merged_graph.json` and `chains/`. **Needs:** about 80 lines in `derive.py`.
- **Depends / risks:** none. A single-player sector can be a curation gap (Amkor alone because ASE was never added to that chain) — caption it "as curated" and link to Coverage.
- **Transcript-only:** structure only.

## Priority 3 — workflow and chat

### 12. Earnings-season workflow: pre-call checklist (M)
- **You see:** in Coverage, for each upcoming call, a generated checklist: (a) what they guided last time (`guidance` slot), (b) `next_catalyst` items whose date has passed, (c) edges with contracts that need an update, (d) what suppliers and customers said since the last call, (e) this company's verification fails to fix, (f) the exact `Transcript:<name>` or `enrich us` command.
- **Why:** before Micron's next call the checklist would list `SK Hynix Q2 FY2026 (08-14-2026)` (utilisation 100%), `Samsung Q2 FY2026 (08-14-2026)` (HBM4 shipping since February), `NVIDIA Q2 FY2027 (08-26-2026)` (memory price increases exceeded expectations), `Techwing DART supply contract (08-10-2026)` → Micron, and Dell ranking DRAM first among constraints — the questions to have ready.
- **Data today:** `Coverage.tsx` (Yahoo dates fetched at runtime through a cookie-and-crumb handshake that can fail), `av.py calendar` (Alpha Vantage `EARNINGS_CALENDAR`, 3-month horizon), the `waiting` list in `av/sync_state.json`, slots, edges. **Needs:** a build-time `graph/coverage.json` from `av.py calendar` plus the DART/Investing states, so Coverage stops depending on Yahoo; a checklist generator in `derive.py`.
- **Depends / risks:** the own-call freshness fix in #4. Calendar dates are estimates — show them as such.
- **Transcript-only:** call dates are schedule metadata; the checklist content is stored signals.

### 13. Ask-the-Graph follow-ups: per-chain briefs and saved questions (M, after the chat lands)
- **You see:** a per-chain brief generated at build time — companies by layer, latest signal per company, tight sectors, top contracts, transition status, verification rate — that the chat cites; saved questions with a shareable URL (`#q=`) and graph-shaped templates ("who supplies X in chain Y", "what did X say about HBM4 last quarter").
- **Why:** a Vera Rubin brief today would put the chain's 86 edges, the HBM4 rows and the `NVIDIA Q2 FY2027 (08-26-2026)` ramp statement on one page.
- **Data today:** everything. **Needs:** `graph/briefs/<chain>.json` from `derive.py` (deterministic, no LLM); templates in the chat UI.
- **Depends / risks:** the sibling chat. The chat must answer "nothing stored" rather than guess — briefs make that easier.
- **Transcript-only:** every sentence in a brief carries a label.

## Rejected — they need data the project refuses to ingest
- News-driven alerts, sentiment, "market chatter" (Reddit/X): the news pipeline was reverted on 2026-06-11.
- LLM "knowledge edges" (relationships the model remembers but no transcript states): reverted with the above.
- Analyst consensus, price targets, valuation screens: external vendor data, and no Quant tab.
- Shipment/customs data (Panjiva-style), satellite imagery, job postings: not transcripts.
- Vendor relationship feeds (Bloomberg SPLC, FactSet): would replace the owner's curation with a black box.
- Automatic node creation for every filed counterparty: tried 2026-08-29, reverted 2026-09-05 (litmus test).
- Return backtests inside the app: `quant/` stays a folder, by owner decision.
- Parked, not rejected: MOPS 法說會 decks and TWSE monthly revenue for the Taiwan gap — an open question for the owner (CLAUDE.md, Workflow 2d).

## Four-week sequencing
- **Week 1 — see the delta:** #1 changelog, #2 alerts, and the own-call freshness fix from #4. Everything downstream ("since last visit", pre-call checklists, socket history) needs a diff.
- **Week 2 — trust:** #3 trust score (sync `verification.json`), #4 SLA view, #5 watchlist; and pay the debts below, because they distort the trust numbers.
- **Week 3 — the views the tags already support:** #6 tightness heatmap, #11 hubs and chokepoints; introduce the `kpi` and `share` tags and back-tag the roughly 30 Korean entries so #7 and #9 start accumulating from the next `enrich dart`.
- **Week 4 — the differentiator:** #8 content baseline for the NVIDIA transition first, #10 capex flow-through with Big-4 capex tags, #12 checklist. #13 waits for the chat.

Why this order: small deterministic pieces first; each week's output is a JSON under `graph/` that the next week reads; the thesis feature (#8) comes last because it needs the owner's curated baseline, not code.

## Accuracy debts noticed while reading (file paths)
1. **A sell-side note is in the graph.** `Goldman Sachs optical note (04-17-2026)` accounts for 51 entries (13 of NVIDIA's 15 fails), and ten more note/press labels (DigiTimes ×5, Simply Wall St, PV Magazine, Semiconductor Today, Motley Fool Modine, TDK-NCI JV press) bring it to 62 entries with no file on disk, against the transcript-only rule. `timelines/product_launches.json` cites the note as a source. Decide: remove, or keep visibly flagged as legacy.
2. **Korean header label.** `supply_contracts/sanilelectric.txt` has `# source label: Sanil Electric DART 공급계약 (08-20-2026)` while the graph uses `Sanil Electric DART supply contract (08-20-2026)`; `verify_graph.py` therefore resolves the label to `transcripts/dart/sanilelectric_q2_2026_dart.txt` and reports two false `number_not_in_source` fails. Rename the header.
3. **Verifier false negatives on KRW.** Rounded billions (Hyosung Heavy "3,045.2B") against 백만원 tables, and computed sums (Mirae Industry "KRW 6,281,940,966 = a + b", the Meta/Microsoft H1 totals) fail as `number_not_in_source`. Add a `derived: true` flag for computed figures and a rounded-rescale rule in `Doc.has_number` (`verify_graph.py`).
4. **Missing transcripts behind real labels.** The 31 unresolved labels include actual calls — `Tokyo Electron Q4 FY2026 (04-30-2026)`, `Kioxia Q4 FY2026 (05-15-2026)`, `Shin-Etsu Chemical Q4 FY2026 (04-28-2026)`, `TDK Q4 FY2026 (04-28-2026)`, Wistron / Inventec / Lite-On / Phison / Yageo Q1 FY2026. Save the files or the entries stay "fail".
5. **Freshness borrowed from other companies' calls.** `web/src/lib/signals.ts` (`nodeSignalMeta`) and `web/src/components/Coverage.tsx` (see #4). The same effect makes 14 curated Screener rows look stale in `derive.py`'s report (Micron, Dell, Broadcom, Arm Holdings …), mostly because `NVIDIA Q2 FY2027 (08-26-2026)` mentioned them.
6. **Big-4 capex untagged.** Meta, Microsoft, Amazon and Google carry capex entries with no `capex` tag; the Big-4 bars in `graph/capex_backlog.json` are still the curated baseline from `capex_backlog.json`.
7. **"Lost" often means "not curated".** The Google transition lists OpenAI, Meta, NVIDIA and Jabil as lost (in `chains/accelerators/google_tpu_v7_ironwood.json`, absent from `tpu_v8t.json` / `tpu_v8i.json`); the NVIDIA transition lists Wistron, Pegatron, Gigabyte, Wiwynn, Chenbro and ASPEED (`nvda_b200.json` vs `nvidia_vera_rubin.json`).
8. **Corroboration gaps.** `SK Hynix → TSMC` exists in 12 chains with zero contracts although both discuss HBM4 and CoWoS on their calls; 118 contracts sit on edges whose source document never names the counterparty (`counterparty_not_in_source`: Lam Research 8, Monolithic Power 6, AMD, ASML, Hanmi, KLA 5 each).
9. **Stale README.** `README.md` says 264 companies · 1,067 edges · 174 transcripts; the graph is 312 · 1,250 · 319 indexed documents.
10. **92 nodes with no data** (JSR, Pegatron, Gigabyte, Wiwynn, SPIL, JCET, Siltronic, SK Siltron, …), mostly the Investing.com coverage gap; they still count in the Generations tab.
