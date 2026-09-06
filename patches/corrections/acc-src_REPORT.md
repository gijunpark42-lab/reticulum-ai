# acc-src — source-file resolution report (2026-09-05)

Scope: the 31 labels / 102 graph entries in `patches/corrections/todo_acc_src.json` for which
`verify_graph.py` found no source file on disk.

Outcome
- 7 labels / 77 entries RESOLVED by inserting one `# source label: <label>` line at the top of the
  matching file (8 files; `git diff --numstat` = 8 insertions, 0 deletions, no other byte changed;
  all 8 files are CRLF with no BOM, the new line is CRLF too).
- 24 labels / 25 entries UNVERIFIABLE — no document on disk anywhere under `transcripts/**` or
  `supply_contracts/` (searched by company name, Japanese name, date and distinctive words from the signals).
- 0 relabel proposals — no file carried a different canonical header for one of these documents.
  (The only near-case, Modine, is explained below; no `acc-src_<n>.json` file was written.)
- Nothing in `chains/`, `graph/`, `verify_graph.py`, `agent/corpus.py` or the todo file was touched by acc-src.
  (The `M chains/*.json` / `M graph/*.json` lines in `git status` belong to other agents.)

## 1. Resolved — header added (verified with `python -X utf8 verify_graph.py --label "<label>"`)

| Label | Entries | Outcome | verify --label after the fix |
|---|---|---|---|
| Goldman Sachs optical note (04-17-2026) | 51 | header added to `transcripts/optical/gs_optical_networking_apr2026.txt` | 36 pass / 15 unchecked / 0 fail |
| Ibiden Q4 FY2026 (05-12-2026) | 4 | header added to `transcripts/non_transcript_sources/ibiden_fy2026.txt` (results deck; sorts first, so the resolver uses it) AND to `transcripts/non_transcript_sources/ibiden_fy2026_qa.txt` (same-day Q&A companion; entries 2 and 4 draw on it) | 3 pass / 1 fail — `number_not_in_source` 416.2, 12.7, 30.3: the deck's PDF-to-text lost the chart figures (pages 3-4 "Results of FY2025" are blank text). The file IS the document; the numbers are simply not in its text. Owner / number reviewers decide. |
| Kioxia Q4 FY2026 (05-15-2026) | 5 | header added to `transcripts/non_transcript_sources/kioxia_fy2026_briefing.txt` | 5 pass |
| Mitsubishi Gas Chemical Q4 FY2026 (05-13-2026) | 2 | header added to `transcripts/non_transcript_sources/mgc_fy2026.txt` | 1 unchecked / 1 fail — `number_not_in_source` 45.3: the tanshin prints operating profit `45,293` (million yen) and `45.2` in its billions table (rounded down). 45.3B is the correct rounding — a checker artifact, not a data error. |
| Shin-Etsu Chemical Q4 FY2026 (04-28-2026) | 4 | header added to `transcripts/non_transcript_sources/shinetsu_fy2026.txt` | 4 pass |
| TDK Q4 FY2026 (04-28-2026) | 5 | header added to `transcripts/non_transcript_sources/tdk_fy2026_briefing.txt` | 4 pass / 1 warn — `counterparty_not_in_source` on the Nippon Chemical Industrial -> TDK contract: the briefing is Japanese and names the partner 日本化学工業 (line 1322, "JV設立を4月2日に発表"); verify has no Japanese alias table. |
| Tokyo Electron Q4 FY2026 (04-30-2026) | 6 | header added to `transcripts/equipment/tel_fy2026.txt` | 6 pass |

Evidence that each file is that document (rule 4):
- gs_optical_networking_apr2026.txt — lines 2-4: "Goldman Sachs Global Tech Research / Optical Networking: The next mega trend in AI infrastructure / Published: April 17, 2026"; contains MITA-T Minerva, 1:8, Oracle 800G -> 1.6T 2027, OCP OCS + iPronics, Robotechnik EUR 7.7M, VPEC 60 -> 64, YJ Semi, Landmark, Prysmian EUR 121.45.
- ibiden_fy2026.txt — "Financial Results of FY2025 / IBIDEN CO., LTD.(4062) / May 12th, 2026" (Ibiden's FY2025 = year ended March 2026 = the graph's Q4 FY2026, consistent with `Ibiden Q1 FY2027 (08-05-2026)`); has SAP demand "exceed", "x 1.8 x 2.5", "500 billion", Cell6 220, reticle 3.5/5.0/7.5/9, substrate 80x80 ... 130x130.
  ibiden_fy2026_qa.txt — "Financial Presentation for the Year Ended March 31, 2026 / May 12, 2026"; has "share close to 100%", customer-funded advances, "orders for switch substrates from a major GPU customer".
- kioxia_fy2026_briefing.txt — "2026年3月期決算説明会 ... 2026年5月15日"; 10,029 (億円 = 1,002.9B yen), 84.5, 188.9, 17,500, 13,000, 74.3.
- mgc_fy2026.txt — "May 13, 2026 / Summary of Consolidated Financial Results for the Fiscal Year Ended March 31, 2026 / Mitsubishi Gas Chemical Company, Inc."; 738,243 / (4.6) / 45,293 (10.9) / (40,318).
- shinetsu_fy2026.txt — "Consolidated Financial Results for the Fiscal Year Ended March 31, 2026 / Shin-Etsu Chemical Co., Ltd. / April 28, 2026"; 2,573.9 / 635.2 / 474.4 / 1,015.7 / 344.5 / Isesaki.
- tdk_fy2026_briefing.txt — line 2 note + "2026年3月期 通期決算説明会 / TDK株式会社 / 2026年4月28日"; 25,048 (億円 = 2,504.8B), 2,724, 13.6, 21.5, 10.9, 25,800, 40円.
- tel_fy2026.txt — "April 30, 2026 ... FY2026 (April 2025-March 2026) Financial Announcement" (Tokyo Electron IR deck); 2,443.5 / 574.4 / 550 / 31% / 10%.

## 2. UNVERIFIABLE — no document on disk (owner decides; nothing was changed)

| Label | Entries | Companies | What was checked / false leads |
|---|---|---|---|
| Accton Technology Q1 FY2026 (05-08-2026) | 1 | Accton Technology | "Accton" / "Edgecore" appear in no file. The todo's candidates are AD Technology (Korean, unrelated). |
| DigiTimes ABF substrate note (04-20-2026) | 2 | Kinsus, Nan Ya PCB | "DigiTimes", "Kinsus", "Nan Ya" appear in no file. |
| DigiTimes Nan Ya PCB note (05-14-2026) | 1 | Nan Ya PCB | `transcripts/memory/nanya_q2_2026.txt` is Nanya Technology (DRAM, label "Nanya Q2 FY2026 (07-10-2026)") — a different company; not the note. |
| DigiTimes Unimicron note (05-29-2026) | 1 | Unimicron | `non_transcript_sources/unimicron_q1_2026.txt` is Unimicron's own Q1 Financial Review deck dated Apr 28, 2026 and contains no "2022" / "record" / "peak" claim — a different document. |
| DigiTimes Wistron note (05-09-2026) | 1 | Wistron | "Wistron" appears in no file. |
| DigiTimes Zhen Ding note (06-05-2026) | 1 | Zhen Ding | "Zhen Ding" / "ZDT" appear in no file (the todo candidates are PSK / Panasonic / SCREEN "holdings" false hits). |
| Disco Corporation Q4 FY2026 (04-22-2026) | 1 | Disco Corporation | Case-sensitive "DISCO" / "Disco Corp" / "ディスコ" appear in no file (the case-insensitive hits are "discount" / "disclosure"). |
| GlobalWafers Q1 FY2026 (05-05-2026) | 1 | GlobalWafers | Only a passing mention inside `investing/soitec_q1_2027.txt`; no GlobalWafers document. |
| Inventec Q1 FY2026 (05-12-2026) | 1 | Inventec | No file. |
| Lite-On Q1 FY2026 (04-29-2026) | 1 | Lite-On | Only the Q2 call `investing/liteon_q2_2026.txt` ("Lite-On Q2 FY2026 (07-31-2026)") exists — a different document. |
| Mitsui Mining & Smelting Q4 FY2026 (05-13-2026) | 1 | Mitsui Mining & Smelting | "Mitsui Mining" / "Mitsui Kinzoku" / "三井金属" appear in no file. |
| Motley Fool Modine note (05-26-2026) | 1 | Modine | `power/modine_q4_2026.txt` (informal label "Modine Q4 FY2026 (05-27-2026)") covers the same LTA ($4 billion, CY2027-2029, $165M upfront) but its own header says "Motley Fool had not published ...", it never says Airedale or hyperscale, and it says "no more than $2 billion a year" where the entry says "~$1.3B/yr". Not that document -> no relabel. OWNER OPTION: relabel to `Modine Q4 FY2026 (05-27-2026)` and fix the figure, or save the Fool article. |
| Nippon Steel Q4 FY2026 (05-13-2026) | 1 | Nippon Steel | "Nippon Steel" / "日本製鉄" appear in no file. |
| PV Magazine USA transformer note (05-11-2026) | 1 | Nippon Steel | "PV Magazine", "grain-oriented", "electrical steel" appear in no file (the todo candidates are Kokusai Electric false hits). |
| Phison Q1 FY2026 (05-08-2026) | 1 | Phison | No file. |
| Sakai Chemical Industry Q4 FY2026 (05-13-2026) | 1 | Sakai Chemical Industry | "Sakai" / "堺化学" appear in no file (the todo candidate Mirae Industry is unrelated). |
| Semiconductor Today AIXTRON note (05-04-2026) | 1 | AIXTRON | Only the Q2 call `investing/aixtron_q2_2026.txt` (07-30-2026) exists; the note is about Q1 results — a different document. |
| Simply Wall St NCI note (05-20-2026) | 1 | Nippon Chemical Industrial | "Simply Wall", "Nippon Chem" appear in no file. |
| Sumitomo Metal Mining Q4 FY2026 (05-11-2026) | 1 | Sumitomo Metal Mining | Only `sumitomo_bakelite_fy2026.txt` (a different company) exists; "Sumitomo Metal" / "住友金属鉱山" in no file. |
| TDK-NCI JV press (04-02-2026) | 1 | Nippon Chemical Industrial | The 04-02 press release is not on disk. (`tdk_fy2026_briefing.txt` line 1322 corroborates the JV announcement date in passing — a different document.) |
| Taiyo Yuden Q4 FY2026 (05-11-2026) | 1 | Taiyo Yuden | "Taiyo Yuden" / "太陽誘電" appear in no file. |
| Toho Titanium Q4 FY2026 (05-08-2026) | 1 | Toho Titanium | The only "Toho" hit is "Tohoku Production and Logistics Center" in tel_fy2026.txt — false lead. |
| Wistron Q1 FY2026 (05-08-2026) | 1 | Wistron | No file. |
| Yageo Q1 FY2026 (04-15-2026) | 1 | Yageo | No file. |

Pattern: all 24 are Taiwan / Japan / Europe names or press / research notes enriched from IR
releases / news that were never saved. The fix is procedural — save the document under
`transcripts/non_transcript_sources/` (or the sector folder) WITH a `# source label:` header at the
time of enrichment — not a data edit. Do not delete these entries on the strength of this report.

Totals: resolved 77 entries (7 labels) + unverifiable 25 entries (24 labels) = 102.

## 3. Suggestions for verify_graph.py's resolver (NOT edited by acc-src)

1. Accept the informal header variants that already exist in hand-saved files:
   `Source label for enrichment: ...` (micron_q3_2026, nanya_q2_2026, modine_q4_2026, lasertec_q3_fy2026_tanshin),
   `Source label: ...` (iqe_q4_2025), `SOURCE LABEL USED FOR ENRICHMENT: ...` (keysight_q3_2026, supermicro_q4_2026),
   `Canonical source label used in chains: ...` (nvda_q2_2027), `Canonical source label used for enrichment: ...` (aaoi_q2_2026),
   and the NOTE-line form "same source label `X`" (the amd / intel / alphabet / meta / microsoft / kla / lam / teradyne / rambus /
   amphenol / corning / navitas / onsemi / arista / astera Q2-wave files).
   One regex covers the colon forms:
   `(?im)^(?:#\s*)?(?:canonical\s+)?source label(?:\s+used)?(?:\s+for enrichment|\s+used in chains)?\s*:\s*(.+?)\s*$`
   plus a second pattern for the back-ticked form. 239 files outside av/dart/investing have no `# source label:` line today.
2. Filename join for fiscal-year files: treat `<company>_fy<year>[_briefing|_qa|_tanshin|_deck].txt` as `Q4 FY<year>`
   (this graph's March-FY convention) — that alone would have caught tel_fy2026, shinetsu_fy2026, kioxia_fy2026_briefing,
   tdk_fy2026_briefing, ibiden_fy2026 and mgc_fy2026 without any header.
3. Extend `FILE_ALIASES` (or corpus `COMPANY_ALIASES`): `tel` -> `tokyoelectron`, `mgc` -> `mitsubishigaschemical`,
   `gs` -> `goldmansachs`, `apld` -> `applieddigital`. `same_company()` rejects tokens shorter than 5 chars, so 2-3 letter
   file stems can never match without an alias.
4. Strategy 3 (loose event match) requires ALL non-year filename tokens to appear in the label; `gs_optical_networking_apr2026`
   fails on `networking` and `apr2026`. Suggest dropping month tokens (`(jan|feb|...|dec)20\d\d`) and requiring a majority, not all.
5. One label -> several documents. `by_label.setdefault` keeps only the first file in sort order; companion files
   (deck + Q&A: ibiden_fy2026 / ibiden_fy2026_qa; slides + call: lam_research_q4_2026 / _call; 8-K + transcript pairs)
   should be checked as a UNION for NUMBERS and PARTY. Today the Ibiden Q&A header is inert for resolution.
6. The PARTY check needs a Japanese alias table like `KO_ALIASES` (Nippon Chemical Industrial -> 日本化学工業,
   Sandisk -> サンディスク, Kioxia -> キオクシア, Samsung -> サムスン ...) — the TDK warn above is exactly this.
7. NUMBERS: add a million -> billion rescale WITH rounding (`45,293` million should match `45.3` billion). The digit-run
   check only matches an identical digit prefix (`45293` vs `453` misses), so correctly rounded figures taken from
   Japanese tanshin tables fail today (the MGC case).
8. Optional: when a label is unresolved, print the best filename candidate by company token + year, so the owner
   sees "Disco: no file at all" vs "Ibiden: file exists, header missing" at a glance.
