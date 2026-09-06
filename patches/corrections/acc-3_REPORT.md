# acc-3 accuracy review — report

Worklist: `patches/corrections/todo_acc3.json` — 91 entries, 33 companies, 43 source documents.
Proposals: `acc-3_1.json` (todo 0-22), `acc-3_2.json` (23-45), `acc-3_3.json` (46-68), `acc-3_4.json` (69-90).
Every one of the 91 items appears in exactly one file; each file passes `apply_corrections.py --check` with 0 errors.
Each item carries a `todo_idx` key (ignored by the applier) pointing back to the worklist.
No `move` patches were needed (no contract sat on a wrong edge whose correct counterparty is a node).

## Counts by action

| action | items |
|---|---|
| keep | 64 |
| set | 11 |
| delete | 16 |
| relabel | 0 |
| **total** | **91** |

Of the 64 keeps, 20 are entries the auditor flagged only because it opened the WRONG or an INCOMPLETE file
(see "Mis-resolved sources" below) — the numbers are all in the document the label actually names.

## Deletes (16) — contracts whose document never names the counterparty

| # | edge | label | why |
|---|---|---|---|
| 0 | ASE Group → AMD | ASE Group Q1 FY2026 | 3.5KB call summary names no customer ("a large GPU customer"); LEAP facts already on ASE's node |
| 1 | ASE Group → Broadcom | ASE Group Q1 FY2026 | CPO work is with "foundry + end customer" (unnamed) |
| 2 | ASE Group → Google | ASE Group Q1 FY2026 | Google never appears |
| 3 | Amkor Technology → NVIDIA | Amkor Q1 FY2026 | "broad-based strength across multiple customers"; no customer named |
| 4 | Amkor Technology → AMD | Amkor Q1 FY2026 | same |
| 37 | KLA → SK Hynix | KLA Q3 FY2026 | KLA names no customer (only Intel, in an analyst question); KLA-level facts already on KLA's node |
| 38 | KLA → Micron | KLA Q3 FY2026 | same |
| 39 | KLA → TSMC (foundry chain) | KLA Q3 FY2026 | same |
| 40 | KLA → TSMC (packaging chain) | KLA Q3 FY2026 | same |
| 41 | KLA → Amkor Technology | KLA Q3 FY2026 | same |
| 70 | SK Hynix → AMD | AMD Q1 FY2026 | Lisa Su: "our partnerships with the memory vendors" — no vendor named; not attributable to SK Hynix vs Samsung/Micron |
| 79 | Silicon Motion → Solidigm | Silicon Motion Q1 FY2026 | only "NAND flash makers"/"NAND makers"; Solidigm never appears |
| 80 | Silicon Motion → Kioxia | Silicon Motion Q1 FY2026 | Kioxia never appears |
| 85 | onsemi → Delta Electronics | onsemi Q1 FY2026 | "all major power supply vendors"; only FlexPower is named |
| 86 | onsemi → NVIDIA | onsemi Q1 FY2026 | NVIDIA never appears; "the GPU or XPU", "multiple XPU vendors" |
| 87 | onsemi → Vertiv | onsemi Q1 FY2026 | **signal says "including Vertiv" but Vertiv is nowhere in the call** — fabricated attribution |

Pattern: 15 of the 16 are "skeleton-edge prose" — the enrichment restated the curated relationship as a contract entry
("Process control for Micron's HBM/DRAM production", `value: no specific figure`) and stamped it with the call's label even
though the call names no customer. The curated edges themselves are untouched; only the unsupported contract entries go.

## Sets (11) — entries that misquote their source

| # | entry | label | change |
|---|---|---|---|
| 5 | Amkor Technology qd | Amkor Q2 FY2026 | $1.898B → $1.9B (call says "$1.9 billion"); dropped "Advanced products $1.557B = 82%" (not in call) |
| 6 | Amkor Technology qd | Amkor Q2 FY2026 | same; +12.6% QoQ → +13% (call wording); dropped $1.557B / 82% / mainstream $341M |
| 12 | CoreWeave qd | CoreWeave Q1 FY2026 | $2.08B → ~$2.1B ("Revenue was $2.1 billion") |
| 14 | Dell qd (nvda_b200) | Dell Q1 FY2027 | "Shipping PowerEdge XE9680 B200 servers" is not in the call (XE9680 absent; B200 only in an Arm-vs-x86 Q&A); reworded to the supported GB300-desktop / GB10 / 18th-gen PowerEdge statements |
| 16 | Doosan Enerbility qd | Doosan DART supply contract (08-21-2026) | figure trimmed: the "backlog KRW 29.68T at 06-30-2026" is from the half-year report, not this disclosure (already on Doosan's Q2 FY2026 entry) |
| 26 | Groq → Marvell contract | Marvell Q1 FY2027 | "Analyst confirmed" → analyst "seemed to recall"; CEO never confirmed the Groq design |
| 34 | Jabil qd | Jabil Q3 FY2026 | $8.75B → ~$8.8B ("approximately $8.8 billion, ... $250 million above the midpoint") |
| 36 | Jabil qd | Jabil Q3 FY2026 | "~$200-300M FY27" → the CEO's exact "a couple of $100 million range" (no range stated) |
| 45 | LS Electric qd | LS Electric DART supply contract (08-24-2026) | figure trimmed: "parent backlog KRW 6,999.8B" is from the half-year report (already on LS Electric's Q2 FY2026 entry); amount written as the exact KRW 230.85B |
| 64 | NVIDIA-node qd "Google Q2 FY2026" | Google Q2 FY2026 | dropped "H1 capex $80.6B" (needs Q1 $35.7B, not in doc) and "$49.6B equity raise" (10-Q fact, not in the call summary); added the stated FY26 capex guide $195-205B |
| 78 | Silicon Motion qd | Silicon Motion Q1 FY2026 | "$1.97 per diluted ADS, net income $66.8M" → "earnings per ADS $1.58" (the only EPS the call states) |

Pattern behind 5, 6, 12, 34, 78: **press-release precision inside a transcript-labelled entry** — the call says "$1.9 billion" /
"approximately $2.1 billion" / "approximately $8.8 billion" / "$1.58", the entry carries the 8-K number ($1.898B, $2.08B, $8.75B,
$1.97). Under the transcript-only rule these should read as the call states them.

## Systematic patterns in the auditor's false positives (with fixes for `verify_graph.py`)

Roughly 55 of the 91 flags were false positives. They cluster into six mechanical gaps:

1. **Rounding after unit rescale (Korean 백만원/천원/원 tables) — the single biggest source (~20 items).**
   `has_number` rescales by comparing digit *prefixes*, so a value that is rounded after rescaling never matches:
   `547.8` (KRW B) vs `547774` (백만원) — prefix `5478` ≠ `5477`; `251.2` vs `251163039356`; `88.6` vs `88575409916`;
   `1,235,185` vs `1235184725` (천원); `1,376.6` vs `1376552`; `484.1` vs `484052`; `12,420` vs `12419892211`.
   Fix: in the rescale branch, for each digit run of length ≥ len(digits)+1, round the run to `len(digits)` significant
   digits and compare (i.e. `round(run / 10**(len(run)-len(digits)))` == int(digits)), instead of `run.startswith(digits)`.

2. **Sums and ratios of stated figures (~18 items).** Every Mirae Industry contract total (e.g. `6,281,940,966 =
   3,575,806,836 + 2,706,134,130`), Doosan's `5,764,659` (four BNPP contracts), Gaonchips' `18,166 = 17,757 + 409`,
   and every margin/share (`51.9% = 130,347/251,163`, `83.7% = 203,442/242,959`, `+38% = 22B/16B`, `$4.32B = 40% x $10.8B`).
   Fix (cheap): when a number is missing, try pairwise sums and ratios of the *other* numbers in the same field that ARE in
   the document, and report `derived` instead of `fail`. Fix (cheaper): let enrichment mark computed values (`"derived": true`
   or a trailing `(= a + b)` in the figure, which the Mirae entries already do) and downgrade those to `warn`.

3. **Numbers written in words by the transcription (~5 items).** `1 thousandx` (Credo 1,000x), `surpassed 5 thousand`
   (Dell), `960 thousand Rubin GPUs`, `$3181.1 million` (Modine, matched only by luck), `¥106,396 million` (Sumitomo, 106.4B).
   Fix: in `normalize()` for documents, rewrite `(\d+(?:\.\d+)?) thousand` → `\1,000`, `... million/billion` → scaled digits,
   so `5 thousand` becomes `5000`.

4. **Counterparty aliases (~17 items) — the PARTY check only knows the KO_ALIASES table.** Missed forms:
   - Korean spellings not in the table: SK실트론 (SK Siltron), 에스케이엔펄스 (SK Enpulse), 샌디스크 (Sandisk), 시높시스
     (Synopsys — note the 높 spelling), 대한전선 (Taihan Cable), 시그네틱스 (Signetics), SFA반도체, LG이노텍, ASE코리아.
   - Acronyms in parentheses in the node name: `Korea AI Computing Center (KOACC)` → doc says `(KOACC)`;
     `Taiwan Union Technology (TUC)` → doc says `TUC`; `Powertech Technology` → doc says `PTI`.
   - Short names the ≥5-char fallback rejects: `Arm Holdings` → `Arm`/`ARM`; `ASE Group` → `ASE`.
   - Alias keyed under the wrong node: `AWS` is listed under `Amazon Web Services`, but the node is `Amazon` (3 items).
   - Transcription misspellings: `NVDIA` (Alphabet Q1), `Grok` (Groq, Marvell Q1 FY2027), `Raytek` (Raytec Semiconductor).
   Fix: (a) key aliases by the actual node ids and add the names above; (b) when the node name contains `(ABC)`, also try
   `ABC` alone; (c) allow a 3-4 letter first word when it is matched with word boundaries on the raw text (`\bArm\b`, `\bASE\b`)
   rather than on the compacted string; (d) an edit-distance-1 match for names ≥ 5 letters would catch NVDIA/Grok/Raytek.

5. **Label → file resolution picks the wrong or an incomplete document (20 items).**
   - `Applied Digital Q4 FY2026 (07-27-2026)` was resolved to `applied_digital_q3_2026.txt` (the Q3 call) because the loose
     matcher strips `q3` before comparing tokens. The real source, `transcripts/non_transcript_sources/apld_q4_fy2026_earnings_release.txt`,
     has every number but no `# source label:` header. Fix: never let strategy 3 accept a file whose `q<N>` token contradicts the
     label's quarter; index files by `CALL DATE:` + company when the `# source label:` header is missing.
   - `Samsung Electro-Mechanics Q1 FY2026 (04-30-2026)` was resolved to `memory/samsung_q1_2026.txt` (Samsung Electronics' call)
     because `same_company` accepts `samsung` as a full prefix of `samsungelectromechanics`. The real source,
     `transcripts/power/samsung_electro_q1_2026.txt` (SEMCO deck: `Sales 3,209.1 ... Component 1,408.5 ... Package 725.0 ... 45%`),
     has no header either. Fix: prefer the longest company-token match and reject a prefix match when a longer-token file for
     the same quarter exists; add `samsungelectro` → `Samsung Electro-Mechanics` to FILE_ALIASES.
   - Companion files sharing one label are ignored: `kla_q4_2026.txt` (pasted call summary, $3.66B only) vs
     `kla_q4_2026_earnings_release.txt` (segment table: Semiconductor Process Control 3,256,781; PCB 241,110 vs 154,106 = +56%);
     `onsemi_q2_2026.txt` ($1.6B) vs `onsemi_q2_2026_earnings_release.txt` ($1,604 million; GaN 40V-650V). Fix: when several
     files resolve to the same label (same company + date, or the NOTE line says "same source label"), check numbers against
     the union of their texts and report which file matched.

6. **Cross-document context inside DART supply-contract entries (2 items, both `set`).** Enrichment appended the half-year
   report's backlog to the supply-contract entry's figure (Doosan 29.68T, LS Electric 6,999.8B). Not an auditor bug — a real
   provenance smell; both backlogs live correctly on the Q2 FY2026 entries, so the figures were trimmed.

Two smaller observations: (i) `numbers_in` treats `06`/`30`/`01` from dates as numbers and then matches them as bare
substrings, which is noise both ways — skip tokens that are part of a `MM-DD-YYYY` / `YYYY-MM-DD` date; (ii) `apply_corrections.py`
rejects `signal_prefix` < 20 chars — fine, but two todo items (65/66, NVIDIA → Amazon) are the SAME entry copied into two chains, so
the auditor should de-duplicate flags by (company, target, label, signal) before counting.

## Judgment calls / items I could not decide cleanly

- **#53 Micron → NVIDIA and #71 SK Hynix → NVIDIA (NVIDIA Q2 FY2027)** — kept. The call never names either company, but says
  "all three major memory suppliers" — the complete DRAM/HBM set (Samsung, SK Hynix, Micron) — and the signal quotes that wording
  rather than claiming the company was named. I treated the complete enumeration as attributable, unlike "memory vendors" (#70,
  deleted) or "NAND makers" (#79/#80, deleted), which are open sets. Reverse to `delete` if the orchestrator wants strict naming.
- **#35 Jabil "$200M"** — kept: "about a couple hundred million" read as ~$200M (the signal itself says "roughly $200M"); the
  sibling #36 was rewritten to the CEO's exact phrase because it added an unstated "-300M" upper bound.
- **#64 (Google Q2 FY2026 entry sitting on the NVIDIA node, chain google_tpu_v7_ironwood)** — corrected in place, but the
  placement looks like an enrichment slip (Alphabet financials on NVIDIA's node); worth a look by the integrity agent.
- **Unverified numbers outside the audited fields.** Several `signal` strings I edited still carry press-release-level detail the
  auditor does not check (Amkor operating income $200M / EBITDA $400M / 66% top-ten; CoreWeave $589M net loss). I changed only
  the flagged tokens plus their direct companions; a signal-level number check would surface more of these.
- **Node naming: "Raytec Semiconductor" vs "Raytek".** The Fabrinet transcript and three existing signals say "Raytek"; the node
  and one earlier signal say "Raytec". One of them is a misspelling — not decided here (naming is the human's call).
