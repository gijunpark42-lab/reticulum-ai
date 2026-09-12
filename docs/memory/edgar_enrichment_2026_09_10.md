---
name: edgar-enrichment-2026-09-10
description: "First full `enrich edgar` run (2026-09-10) — 389 queued SEC filings → 243 patches via 9 enricher + 9 adversarial verifier agents; rulings that emerged, XBRL traps, open curation items"
metadata: 
  node_type: memory
  type: project
  originSessionId: d1c1a724-8d81-4857-8dc0-fb528f72c823
  modified: 2026-09-11T07:08:12.047Z
---

On 2026-09-10 the user said "enrich edgar … multi agent, 병렬로처리, verification 도꼭, 정확도 최우선".
Result: 389 queued filings (134 companies) → 243 patches, 120 companies, 356 quarterly_data + 43 contracts,
11 new edges; `verify_graph` 399 entries = 390 pass / 9 unchecked / 0 fail. `edgar_pull.py done` ran. UNCOMMITTED.

**Recipe that worked:** coordinator splits `edgar/pending.json` by company (9 batches), one enricher per batch writes
only `patches/edgar_<file stem>.json`, then a separate verifier per batch re-reads every filing and edits/deletes
patches; coordinator runs ONE `graph_build.py --sync`. Tooling lived in the job tmp dir (gone): a paged/wrapped file
viewer (needed — 8-K exhibits are single 15k-char lines the Read tool truncates) and a pre-flight checker that imports
verify_graph (resolve_label_docs + check_entry) plus structural checks (no new node, locator match, reverse-edge).

**Rulings that emerged (reuse them):**
- A contract goes on an existing edge only if the fact matches that edge's relationship AND direction.
- Existing edges may target a company that is not a player in that chain file — contracts on them are valid.
- Company-wide facts (total revenue, concentration, guidance) → the placement holding the company's call entries;
  a segment that maps to exactly one placement → that placement.
- No restated duplicates of call numbers; M&A → only operating capacity facts, never deal terms or pro-formas.
- A deal fact naming no generation → the edge already recording that deal, else the least generation-specific chain.

**Traps seen:** node renamed after pull (Cipher Mining → Cipher Digital) → `edgar_pull.py --tickers CIFR --force`
before enriching (label prefix must equal node name). XBRL mis-tags: Sterling "RPO" lines = segment revenue; Sandisk
receivables tagged as revenue; Bloom "Customer One 73%" impossible; Core Scientific "One Customer" twice.

**Follow-up (user: "싹다 니가알아서 추가해라", decide on full text):** Fluidstack added as a private neocloud node
(metadata GB) with edges TeraWulf/Cipher Digital/Hut 8/IREN → Fluidstack; SB Energy = existing SoftBank node (no new
node); Core42 (chart legend only), AES (utility storage, not AI), Nanjing Casela (product unstated) NOT added.
Marvell tpu_v8t copy (subset) deleted, fuller copy stays on optical_networking. Eversource 8-K $4.57–$4.72 added
WITHOUT slot (derive.py `latest_only` keeps all same-date entries, so a second guidance slot is ambiguous); the call
entry still says $4.52. MKS 44% vs 43.2% = call rounding, no change.

**Round 1 read EXTRACTS, not full text** — 8-K exhibits were cut at 15k chars (172/486 files) and 10-Ks gave only
customer-10% paragraphs + XBRL, so supplier edges (TSMC foundry, Amkor/ASE OSAT, contract manufacturers) were never
seen. `edgar_pull.py` now: EXHIBIT_CAP 60k with a truncation marker, and `<TICKER>_10-K_<date>_supplychain.txt` =
ranked supplier/named-counterparty paragraphs of the FULL 10-K (same label; queue keeps them). Full 10-K reading of
everything judged not worth it (400–800k chars of boilerplate). Round 2 = `--force` re-pull + supplychain rows +
exhibit-tail rows (text past 15k of already-enriched 8-Ks), same enricher/verifier pattern.

**Completeness contract (user: "앞으로 sec공시 다시볼일없게 꼼꼼히 하는 규칙확립", 2026-09-10)** now lives in
`.claude/skills/enrich/references/edgar.md`: save filings whole (all Items, ALL EX-99 exhibits, safety cap 400k +
TRUNCATED flag; 10-K/10-Q `_supplychain.txt` = every matching paragraph, no cap), enriched files immutable (new
extraction = new file kind; forced re-pull → snapshot + delta only), read with `utils/show_filing.py`, pre-flight with
`utils/check_edgar_patch.py`, split with `utils/edgar_batches.py`, enricher + verifier always, settled rulings listed there.

**Round 2 (2026-09-10/11):** 405 rows (272 supplychain files + 131 round-1 deltas + 2 8-Ks), 24 enrichers + 24
verifiers (20-agent concurrency cap; a rate-limit 429 killed 14 mid-run — resumed each via SendMessage, which continues
from its own transcript). Build: 263 patches, 823 entries → 772 pass / 50 unchecked / 1 warn (ASE Group alias) / 0 fail,
18 new edges. Round 3 = HTML re-pull + unread-sentence deltas (make_deltas_r3: normalised-key containment) + XBRL
precision correction.
**Extractor lessons (all fixed in edgar_pull.py):** edgartools `.text()` shortens blocks with "..." (Hut 8 ROFO "1,000 M...",
Credo EX-99 lost ~9%) → build text from `.html()` / attachment `.download()`; SEC text splits paragraphs at page breaks
mid-sentence → `paragraphs()` re-joins, drops page numbers / "Table of Contents", never glues table rows; `_pct` rounded
XBRL % to integers (9.6% → "10%") → one decimal.
**Merge lesson:** `apply_patches.find_player` took the first of duplicate same-locator players (two Amazon in AWS chains,
two AMD) → now exact `product`, then existing edge to the patch target.
**Rulings added in round 2 (edgar.md):** unnamed purchase obligations kept only when the filing ties the total to
supply / capacity / capex ("mostly inventory", "to secure component supply"); unlabelled chart / deck values never used;
a unit the filing does not print is never written; warrant-only customer ties → quarterly_data, not an edge; a fact must
not hang on a node whose product is something else (GE Vernova's only power_cooling node is Grid → turbine deals go on
the customer's node; pre-existing GE Vernova → AEP "gas turbine supply" edge on that node is a curation item for the user).

**User decision (2026-09-11): read ALL dropped filings** ("333건 전부 읽기") — rounds 1–2 had read only 153 of 486 8-Ks;
the keyword filter's 333 drops (122 earnings releases, 112 with the call already enriched; 65 personnel; ~95 financing;
~50 weak keyword drops) + 16 dropped 10-K/10-Q files go into round 3 as triage rows. edgar.md rule 4b: the noise filter
only orders the work; `edgar_pull.py done --with-dropped` marks triaged files read.

**Round-3 resume point:** ledger `~/.claude/jobs/d1c1a724/tmp/R3_PROGRESS.md` (steps + batch status); snapshot of what
agents already read `tmp/r3_snapshot`; briefs `tmp/AGENT_BRIEF.md` + `AGENT_BRIEF_R2.md` + `AGENT_BRIEF_R3.md`; reports
`tmp/reports/r3_*.md`. User asked (2026-09-11) to guard against mid-run cut-offs: ≤8 concurrent agents, ~250 kB batches,
resume cut agents with SendMessage, re-run only batches without a report.

**Round-3 lessons (2026-09-11; user raised concurrency to 15, then 20):**
- **Call transcripts drop the zero in "$X.0Y"** (Motley Fool / defeatbeta renderings): Vicor "GAAP diluted EPS $1.4" =
  filed $1.04; Ultra Clean Q3 guide "$0.83-$1.3" = filed $1.03. Chain entries copied them faithfully (verify passes!).
  Sweep script `tmp/sweep_dropped_zero.py` (per-share figures vs same-company 8-K ±7 days); fixes = ADD 8-K entry +
  reviewed correction on the call entry. Speakers also misstate (Eversource CFO $4.52 / $21.5B vs filed $4.57 / $26.5B).
- **Call label dates can be wrong** (transcript header dates "approximate"): Eaton Q2 label 08-05 but call held 07-31;
  Eversource label 07-30 vs webcast 07-31 — curation items, relabel breaks label→file resolution unless header fixed.
- **Tables:** a flattened table is LABELLED when its column headers print the periods and each row has exactly one
  value per header (tie-outs confirm) — kept Coherent D&C $1,615.0M, Microsoft recast deck, Semtech segments. Chart
  data / cells without headers stay banned.
- **"The call already states it" = the node's call entries**, not the raw transcript; a same-period figure the node
  carries even rounded ($5.97B vs $5,965M) is not re-added — keep only year-ago / six-month / new splits.
- **Image pages:** some releases file pages as JPG (Linde 07-31 EX-99.1 pages 4–10) → html_to_text now writes
  `[image: <src> — not text]`; such pages need a visual read.
- **8-K Item splitter cut sections at inline cross-references** ("As described in Item 5.07") in ~151 files → ITEM_RE now
  line-start only; round 3b re-pull recovers the text.
- **The HTML re-pull silently DROPPED TABLES** from 10-K/10-Q `_supplychain`/`_customers` files (117/135 10-K
  supplychain files lost numbers): each `<tr>` became its own short paragraph and the paragraph filter (<120 chars /
  keyword) discarded them; `<p>` inside cells split rows further. Found only because verify failed 5 old entries.
  Fix: `table_blocks()` judges a table whole (+ lead-in), in-cell block tags → space. LESSON: after ANY re-pull run a
  NUMBER-COVERAGE test (numbers in the old file missing from the new) — a delta that looks only for new text never
  sees lost text. 8-K "losses" there were old `.text()` truncations ("1,230…"), not real.
- `edgar_pull.py done --with-dropped` was a no-op until fixed (main() didn't pass the flag).
- GE Vernova has no gas-turbine node → Power-segment facts removed (curation item); Dominion segment non-GAAP
  earnings out of scope; plain balance-sheet lines (inventory, PP&E net) skipped unless tied to supply.

**Round 3 PUSHED (2026-09-10, commit db1da1f on main)** — everything except `transcripts/edgar/` (being re-pulled).
**USER DECISION (2026-09-10 night): round 3b = OPTION A, read ALL recovered tables, NEXT WEEK** ("다음주에 그냥 싹다
모든표") — out of tokens now. Estimate ≈ round 3 size (~7 MB unread, ~14M subagent tokens, 25–26 batches). Do NOT
narrow to in-scope tables. Durable archive (job tmp dir gets deleted): `C:\Users\calif\edgar_round3b\` — ledger
`R3_PROGRESS.md`, briefs (AGENT_BRIEF*.md incl. `AGENT_BRIEF_R3B.md`, VERIFIER_BRIEF.md), `deltas_r3b/` +
`delta_rows_r3b.json`, `r3b_images.json`, `r3b_number_loss.json`, scripts, snapshots. Resume next week:
`python -X utf8 utils/edgar_batches.py 26 <archive>/delta_rows_r3b.json` → enricher + verifier per batch (brief R3B,
patches `edgar_<stem>_r3b.json`) → one `graph_build.py --sync` → full `verify_graph.py` (the 5 round-3 fails: AMAT 10-Q,
Intel Foundry 10-K, Cummins 10-K, Solstice 10-K, TTM 10-K must pass) → commit `transcripts/edgar/` + results only when
the user says 푸시해. Also look at the image-only pages listed in `r3b_images.json` (e.g. Linde 07-31 pages 4–10).
**3b prep FINISHED (2026-09-11 night, no agents):** re-pull 137/137 tickers, exit 0 (transcripts/edgar/ now final,
UNCOMMITTED). The 5 old verify fails all PASS again. Delta = 437 files, 9.7 MB (10-K 5.4 MB, 10-Q 4.2 MB, 8-K 59 kB)
→ ~35 batches, ~20M subagent tokens (≈140% of round 3) — larger than the 7 MB sample estimate. Image pages worth a
visual read: 64 8-Ks, 1,168 slide images (`r3b_image_pages.json`; separate, optional). Filing-level number coverage:
45 10-K / 21 10-Q / 11 8-K filings still miss some old numbers, almost all out of scope; 47 in-scope-looking in 24
filings (`r3b_inscope_loss.json`) — real tables still dropped: Kulicke & Soffa bookings table, TE Connectivity
region x segment table (TABLE_KEEP_RE lacks "bookings" / region words) → consider adding those words + a no-token
re-pull before the 3b batches. Rounds 1–2 had read those tables in the old files, so no chain entry depends on them.

**User decision (2026-09-10): do NOT add Core42, AES or Nanjing Casela** ("걍셋다 넣지마") — don't re-propose them. Related:
[[concurrent-job-race]], [[us-expansion-2026-09-10]].
