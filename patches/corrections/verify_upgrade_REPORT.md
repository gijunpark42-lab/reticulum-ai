# verify-upgrade — report (2026-09-06)

Scope: `verify_graph.py` (rewritten matcher / alias table / resolver), `supply_contracts/sanilelectric.txt`
(one header line), `utils/test_verify_graph.py` (new, 31 tests). `dart.py` needed no change (see §4).
`graph/merged_graph.json` was NOT rebuilt (orchestrator's job), so before/after compare the same graph —
entries the reviewers corrected (`67 deletes / 19 sets`) are still present in both runs.

## 1. Before / after (same graph, same corpus, 2,475 entries)

| | pass | unchecked | warn | fail | number_not_in_source | source_not_found | counterparty_not_in_source | number_derived | number_near_miss | runtime |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline (fresh run before any change) | 1,740 | 433 | 119 | 183 | 158 | 25 | 122 | – | – | 12 s |
| after | **1,782** | 472 | 97 | **124** | 99 | 25 | 77 | 21 | 1 | 20 s |

Entry-level transitions (2,475 keys, none new/lost):

| transition | n | what it is |
|---|---|---|
| fail → pass | 67 | rounding after unit rescale (KRW/JPY tables), companion documents, number words, Korean units, resolver fixes — 14 spot-checked below |
| fail → warn | 18 | 17 `number_derived` (transparent in-field arithmetic, see §2.4) + 1 `number_near_miss` (Keysight "$3.7" for $3.07) |
| warn → pass | 47 | counterparty now found through the alias table (솔브레인, 포스코, AWS, Atotech, STATS ChipPAC, ASE, Arm, Xcel, PSE, KOACC, 日本化学工業 …) |
| pass → unchecked | 38 | the entry's only "numbers" were date / year fragments ("06-30-2026", "FY27", "2026-28") — no longer counted as figures |
| pass → fail | 27 | **all genuine**: the old matcher accepted them by digit-substring coincidence ("38" inside "382", "165.5" inside a KRW provision `165,512,672,219`, "3.7" inside "13.7 billion"). 20 are growth/margin percentages the enricher computed (base figure not in the field), 7 are amounts absent from the document |
| pass → warn | 8 | 4 `number_derived` (margins previously passed by coincidence), 4 counterparty: SEMCO's own Q1 deck never names NVIDIA (the old resolver checked Samsung Electronics' call instead), the MPS Q1 call never says "AMD" (old rule matched "amd" inside a word), SEMCO's filing says only "MITSUBISHI" (which Mitsubishi?) |
| fail → unchecked | 1 | only date fragments |

No entry moved warn → fail or unchecked → fail. `unresolved labels` stays at 24 (all 24 have no document on disk — acc-src §2).

## 2. What changed in `verify_graph.py`

### 2.1 NUMBERS (`Doc.has_number`)
1. **Numbers must stand alone**: "38" no longer matches inside "382" / "1,138" / "1.38" (was a plain substring test).
2. **Rounding-aware rescale**: the document's raw amount ÷ 10^k must ROUND to the figure at the figure's own precision
   (bisect over the sorted document values, O(log n)). Only the unit changes a filing really makes are tried:
   the figure's own unit `e` (from its suffix: K/M/B/T/bn/thousand/million/billion/조/억/백만…), the 천원 / 백만원 /
   십억원 tables (`e-3`, `e-6`, `e-9`), and for KRW/JPY contexts the 억원 / 億円 tables (`e-8`). Unit-less figures try
   {-2,-1,1,2,3,6,9}. Percentages and multiples ("45%", "12.9x") are never rescaled (only the decimal spelling 0.209 ↔ 20.9%).
3. **Precision gate**: a figure with ≥3 significant digits gets the rounding window; a 1–2 digit figure ("220B yen",
   "KRW 2,500M", "500K") must appear with exactly the same digits at one of those powers of ten, printed with ≥4 digits
   ("220,000" million yen yes; `4,912,345,678` for "4.9B" no; a bare "67" for "6.7B" no). A zero after the decimal point
   counts as precision ("62.0" is a 3-digit figure).
4. **Korean units** pre-scanned into the value set (조/억/천만/백만/십만/만/천, composites "27조 8,000억"), **number words**
   ("6 thousand", "half a million", "a billion", "1 thousandx"), and figure-side suffixes incl. "1.2kV".
5. **Near miss** (`number_near_miss`, warn): a decimal-shift twin that stands alone in the text, only for money-style figures
   ("$3.07" ↔ "$3.7"); a percentage's twin ("10.06" for "-10.6%") does not count.
6. `numbers_in` now skips date pieces, year ranges ("26-27", "CY27-29", "2026-28", "'23") and digits glued to a word
   ("FY27", "XE9680", "Q2"). Signature and return shape unchanged (evidence.py already stripped dates itself).

Why the exponent set is small — measured false-hit rate of PERTURBED (wrong) numbers against the same documents
(`perturb ×1.37/×0.71/×1.93`, ~900 tests, mostly DART filings with tens of thousands of numbers):

| rule | 16 exponents (first draft) | final |
|---|---|---|
| ≥3-digit figure with unit, rescale | 45 % | 27 % |
| 2-digit figure with unit, rescale | 86 % | 56 % (9 tests; only same-digit tokens accepted) |
| percentage as decimal (0.209) | 39 % | 21 % |
| exact / rounding at k=0 | 0–33 % | 0–33 % |

i.e. a wrong 3-digit amount is still caught ~3 times out of 4 in a 1 MB DART filing; a wrong 2-digit amount is not
verifiable by magnitude at all — which is why 2-digit amounts are held to exact digits (see §6).

### 2.2 PARTY (`Doc.mentions`)
* `KO_ALIASES` extended to every Korean node (43) with Korean spellings, Japanese nodes with 日本語/Korean spellings, and
  English alternates/subsidiaries/brands (AWS/Trainium/Annapurna → Amazon, Atotech → MKS, STATS ChipPAC → JCET, EMC →
  Elite Material, PTI → Powertech, PSE → Puget Sound Energy, AEP, Hynix, Alphabet/GCP, Meta Platforms/Facebook, Azure,
  Taiwan Semiconductor, Samsung Electronics, Hyundai Electric, Hyosung Heavy/HICO, Mitsubishi Hitachi Power Systems → MHI,
  LITEON, Raytek, NVDIA, SanDisk …). Same `name -> [aliases]` shape; evidence.py reads it unchanged.
* Parenthesised acronyms in node names ("(KOACC)", "(TUC)", "(SKC)") and US 4–5 letter tickers (NASDAQ/NYSE) count.
* Names of ≤4 letters are whole-word and case-sensitive ("ASE" not "phase", "Arm"/"ARM" not "arm's length", "ISC" not
  "discount"); common English words (Intel, Cisco, Linde, Coherent, Micron, Together, Core, Onto …) must be written as a
  proper noun; first-word fallback is blocked for common words and for first words shared by several nodes
  (Samsung / SK / Sumitomo / Mitsubishi / Tokyo / Nippon / Taiyo / Doosan / Wonik / PSK / Siemens / Intel / Applied / Quanta …).
  The old rule matched "intel" inside "intelligence" and "together" anywhere.

### 2.3 SOURCE (`resolve_label_docs`, new; `resolve_label` unchanged in signature/return)
* Header labels: canonical `# source label:` plus the informal spellings (`Source label for enrichment:`, `SOURCE LABEL USED
  FOR ENRICHMENT:`, `Canonical source label used in chains/for enrichment:`, `Source label:`, and the back-ticked NOTE form
  ``same source label `X` ``). A legacy `DART 공급계약` header is read as `DART supply contract`. All of a file's declared
  labels are indexed in `by_label`.
* Filename join by `company_rank`: exact/alias (3) > file token is the leading part of the label's name (2: `hyosung_heavy`,
  `samsung_electro`) > label name is the leading part of the file token (1: `amazon_aws`), with two guards —
  a token that is itself another known company is rejected (`samsung` is not Samsung Electro-Mechanics, `nanya` is not
  Nan Ya PCB, `applied_digital` is not Applied Materials, `lumen` is not Lumentum) unless it is the parent
  (`SUBSIDIARY_OF`: Samsung Foundry → samsung, Intel Foundry → intel, Naver Cloud → naver). Aliases added:
  tel, mgc, gs, apld, semco/samsung_electro, hanmisemi, shinetsu (plus the existing stm/mks/tok/aehr).
* Quarter and date must agree: a file whose stem carries a different `q<N>` is never chosen (Applied Digital Q4 → the
  `apld_q4_fy2026_earnings_release`, not the Q3 call); a file that states a different date (`# source label`, `CALL DATE:`,
  `filed:`) is not a companion (the 08-07 잠정실적 and the 08-14 half-year report are different documents).
* `<company>_fy<year>[_briefing|_qa|_tanshin].txt` = Q4 FY<year> (tel_fy2026, sumitomo_bakelite_fy2026 resolve without a header).
* Companions: every file for the same company + quarter + date joins (call + 8-K release, deck + Q&A, slides + call,
  `_separate` prelim) and NUMBERS/PARTY run against the union; 24 labels have companions. The primary (first) doc is the
  header-declared one, else the bare full transcript — `resolve_label` returns it, so evidence.py keeps locating passages
  in a single file.
* Loose event match ignores month tokens (`apr2026`) and never picks an earnings-style file.
* A `… DART supply contract (MM-DD-YYYY)` label resolves ONLY through its block header — never to the 정기보고서.

### 2.4 Verdicts / output
* New warn issues: `number_near_miss`, `number_derived`. `number_derived` (in-field arithmetic on numbers the document
  does contain: sums of 2–n terms, a/b×100, growth, difference, ratio) is reported as a warn, never a pass — the figure is
  consistent with the source but not in it. 21 entries (e.g. Mirae contract totals `3,575,806,836 + 2,706,134,130`,
  HD Hyundai `67.6 + 79.0 + 88.3`, Soulbrain top-3 `40.91 + 14.90 + 13.08`, PSK `20.9 + 17.9 + 13.4`, margins `62.9 / 514.6`).
* `--fails` / `--company` / `--label` / the post-build gate print `doc: <path> (+N companions)` and
  `missing=[…] near_miss={…} derived={…}` per entry. `verification.json` entries carry `docs` (all companions) when >1.
* `summary.labels_with_companions` added.

## 3. Compatibility with evidence.py (verified)
`from verify_graph import load_documents, resolve_label, numbers_in, NUMBER, KO_ALIASES` works; `resolve_label(label,
by_label, all_docs, filename_docs, cache)` keeps its signature and returns one `Doc` (or None); `load_documents()` still returns
`(by_label dict, all_docs list)`; `Doc` keeps `.path / .text / .label` and stays hashable; `NUMBER` unchanged.
evidence.py's own fallback `by_label.get(lab.replace("DART supply contract", "DART 공급계약"))` is now a harmless no-op.

## 4. supply_contracts headers / dart.py
* `supply_contracts/sanilelectric.txt` line 5: `# source label: Sanil Electric DART 공급계약 (08-20-2026)` →
  `# source label: Sanil Electric DART supply contract (08-20-2026)` (byte replace, CRLF kept; filing text untouched).
  The other 6 blocks (doosanenerbility, hdhyundaielectric, lselectric, techwing ×3) were already English.
* `dart.py`: the Korean label was written by the first version (commit d05cc0f) and already changed to
  `f"{name} DART supply contract ({d:%m-%d-%Y})"` in commit 1aaa924 — no edit needed. Confirmed:
  `Sanil Electric DART supply contract (08-20-2026)` → `supply_contracts/sanilelectric.txt` (its numbers
  `51,197,779,428` / `36,284,748` now pass); `Sanil Electric DART supply contract (06-22-2026)` (no block on disk) → no
  document, never the half-year report.

## 5. Validation
* `python -X utf8 utils/test_verify_graph.py` — 31 tests, OK (~11 s). Matcher: rescale+rounding (won → M, million → B,
  백만원 table, 억원/億円 table), Korean units incl. composites, number words, kV, precision gate, percent never rescaled,
  token boundaries, near-miss only for money figures, `derived_from`, `numbers_in` skipping dates/years/glued digits;
  negatives: wrong numbers still fail (47,123 vs 45,945,836,761; 8.75 vs 8,965 million; 4.9 vs 4,912,345,678; 1,300 vs 13,100;
  "38" inside "382"; 12.2% vs 12,200,000). PARTY: Korean/English aliases, whole-word short names, common-word guards,
  absent counterparty → warn. Resolver: `company_rank` table, header spellings, filename facts, and integration tests on
  the real corpus (SEMCO vs Samsung, Applied Digital Q4, companions, fy files, prelim vs report, supply-contract labels, events).
* Full run before and after (table in §1); 14 fail→pass entries spot-checked by reading the matched document value:

| entry | figure | document value (file) | rule |
|---|---|---|---|
| Samsung Q2 FY2026 | Q2 rev KRW 171.5T | `171,499,470,000,000` won statement (samsung_q2_2026_dart) | ÷10^12, rounds |
| Samsung Q2 FY2026 | purchases KRW 9,996B | `소 계 99,963` 억원 table | ÷10 (e-8) |
| Daeduck Q2 FY2026 | KRW 172.1B | `172,092,805,493` (daeduckelectronics_q2_2026_dart) | ÷10^9 |
| Hanmi Q2 FY2026 | dividends KRW 75.9B | `배당금지급 75,882,401,600` | ÷10^9 |
| EO Technics Q2 | raw-material buys KRW 90.2B | `원재료 매입액 … 90,163,264,379` | ÷10^9 |
| PSK Holdings Q2 | PSK Inc. stake KRW 201.1B | `관계기업투자 201,071,413,527` | ÷10^9 |
| Isu Petasys Q2 | KRW 242.6B remaining capex | `352,300 / 109,712 / 242,588` 백만원 capex table | ÷10^3 |
| Jusung Q2 | KRW 40,890M | `408.9억원` (Korean unit) | 억 → 10^8 |
| KLA Q4 FY2026 | process control $3.257B | `3,256,781` $ thousands (kla_q4_2026_earnings_release, companion) | ÷10^6 |
| Texas Instruments Q2 | TTM FCF $6.53B | `free cash flow … 6,534` (release, companion) | ÷10^3 |
| Sandisk Q4 FY2026 | $8.97B | "$8,965 million" (words) | rounds |
| Mitsubishi Gas Chemical Q4 | OP 45.3B yen | `45,293` million yen (mgc_fy2026) | ÷10^3, rounds |
| Kioxia Q4 FY2026 | 1,002.9B yen | `10,029` 億円 (kioxia_fy2026_briefing) | ÷10 (e-8) |
| Applied Digital Q4 | $258.7M | "$258.7 million" — now the Q4 release, not the Q3 call | resolver |
| Veeco / Wolfspeed / Credo / ASML | $0.7B / 1.2kV / 1,000x / 500K | "$700 million" / "1,200 V" / "1 thousandx" / "half a million" | words / suffix |

Two coincidental matches were found during spot-checking and are now rejected: ISC "7.4B" landed on an unrelated
`7,407백만원` (2-digit window → strict digits), Google "+38%" matched inside "382" (substring → token boundary).
No spot-checked fail→pass entry is a false negative.

## 6. Remaining fails (124) by cause
| group | n | explanation |
|---|---|---|
| A. no source document on disk | 25 | the 24 labels acc-src listed as unverifiable (DigiTimes/Simply Wall St/PV Magazine notes, Accton, Disco, GlobalWafers, Inventec, Lite-On Q1, Mitsui, Nippon Steel, Phison, Sakai, Sumitomo Metal Mining, Taiyo Yuden, Toho, Wistron, Yageo, TDK-NCI press, Modine Fool note) — save the document with a header, or relabel |
| B. DART supply-contract entry citing half-year-report numbers | 4 | HD Hyundai `12.31`, LS `6,999.8`, Sanil `556.8 / 16.6`, Doosan `29.68` — cross-document (acc-1/acc-3 `set` these; graph not rebuilt yet) |
| C. growth / margin / multiple computed by the enricher, base not in the field | 59 | "+16.3% YoY", "(51.9% margin)", "4.1x YoY" where the prior-year / base figure is only in the statement's comparative column. Mechanically unverifiable; 20 of these passed before only by digit coincidence. Hyosung "88.9%" alone is 9 entries (HICO growth copied onto 8 edges) |
| D. amount not in the document as written | 36 | (i) press-release precision in transcript-labelled entries the reviewers already `set` (Jabil 8.75, CoreWeave 2.08, Silicon Motion 1.97, GlobalFoundries 27.6/0.12, TI 4.83, K&S 242.6, AD Tech 56,750) — gone after rebuild; (ii) sums/ratios of DOCUMENT numbers not in the field (Broadcom 4.32 = 40% × 10.8, Semtech 145, Mirae contract totals, Doosan BNPP 5,764,659, Gaonchips 18,166/4,116, AD Tech 27,089/12,260, PSK Inc. 4,395,534,940, Arista 6.87 = 5,100.7 + 1,765.2, Jusung 151,900 = eight in-field terms with one repeated); (iii) 2-digit amounts held to exact digits (ISC 5.8/7.8/4.4/7.4, Daeduck 9.5, PSK 8.4, Simmtech 0.96, Kioxia 870, Doosan 4.18); (iv) genuinely absent: Ibiden (PDF text lost), ASE "USD 3.7B" (doc gives TWD), Jabil "$200M" ("a couple hundred million"), STM ">$500M", Silicon Motion ">12" (spelled out), Eaton "15 years", Hyosung USD 165.5M, Daeduck customer shares |

Warns (97): 75 `counterparty_not_in_source` (most are the knowledge edges acc-2/acc-3 deleted — still in the un-rebuilt
graph — plus the 4 new ones in §1), 21 `number_derived`, 1 `number_near_miss`.

## 7. Deliberately not done / limits
* 2-digit amounts ("KRW 4.9B", "0.96B", "9.5B", "870B yen") are not accepted by rounding: the measured false-hit rate of a
  rounding window for such figures is 72–86 % in DART filings. Enrichment should write 3 significant digits (KRW 965M, 873.7B yen).
* Percentages/multiples whose base figure is not in the field (group C) are not searched for in the document; a proximity
  check (base figure in the same table row as the matched numerator) is the natural next step, not attempted.
* Sums of document numbers that are not in the field (group D ii) are not attempted (needs proximity too).
* Number words for small counts ("twelve"), "only"/"half" as 100 %/50 %, Japanese 億円 written with kanji units, and
  edit-distance name matching ("Grok" for Groq) are not handled; "Grok" was left out on purpose (it is also xAI's model).
* The 145 quarterly_data entries carrying a `counterparty` key are not PARTY-checked (not requested).
* Corroboration tiers moved (two_sided 70 → 62) because `mentions` no longer counts "intelligence" as Intel etc.
* `graph_build.py` shows as modified in the working tree — that is the orchestrator's evidence.py hook, not part of this work.
* `verify_graph.py` is saved with CRLF (the working-tree convention); the new test file uses LF like the other `utils/` scripts.
