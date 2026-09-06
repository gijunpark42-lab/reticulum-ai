# acc-1 accuracy review — report

Worklist: `patches/corrections/todo_acc1.json` (92 entries, 33 companies, flagged by `verify_graph.py` as
`number_not_in_source` / `counterparty_not_in_source`). Every item was checked against its source file
(and, where one exists, the companion `*_earnings_release.txt` saved under the same label).

Proposal files (all validated with `apply_corrections.py --check --file ...` → **0 errors each**):

| file | items | keep | set | delete |
|---|---|---|---|---|
| `patches/corrections/acc-1_1.json` | 23 (todo 1–23) | 17 | 3 | 3 |
| `patches/corrections/acc-1_2.json` | 23 (todo 24–46) | 18 | 0 | 5 |
| `patches/corrections/acc-1_3.json` | 22 (todo 47–69 minus 65/66) | 11 | 0 | 11 |
| `patches/corrections/acc-1_4.json` | 21 (todo 70–92, 91+92 merged) | 19 | 1 | 1 |
| **total** | **89 proposal items = 92 todo items** | **65** | **4** | **20** |

Coverage of the 92 todo items: 89 proposal items + todo 92 (same entry as todo 91, mirrored in a second chain
file — one locator corrects both) + todo 65/66 (verified KEEP but not fileable, see "Blocked" below). Every
proposal item carries `todo_item` so the mapping is auditable. No `relabel`, no `move`, no ADD-only patch was needed.

## Deletes (20) — entries the source does not support

All are contracts whose counterparty is **never named** in the labelled document (grep of the English name,
Korean aliases, tickers and brand names: 0 hits). In every case the underlying facts already sit on the source
company's own node under the same label, so no information is lost — only the unattributable edge attribution goes.

| todo | edge | label | why |
|---|---|---|---|
| 5 | Apple → TSMC | Apple Q3 FY2026 (07-30-2026) | Cook says "that fab" in Arizona / "advanced nodes"; TSMC not named in call or 8-K. |
| 7 | Celestica → Google | Celestica Q2 FY2026 (07-27-2026) | "an AI ML compute program with a hyperscaler customer" — Google/TPU never named. |
| 16 | GlobalFoundries → Fabrinet | GlobalFoundries Q1 FY2026 (05-05-2026) | "3 of the top 4 pluggable optical transceiver companies" — Fabrinet never named. |
| 37 | Intel Foundry → Microsoft | Intel Q1 FY2026 (04-23-2026) | "multiple customers actively evaluating" 14A; Intel says it will not name customers. |
| 43, 44, 45 | Monolithic Power Systems → NVIDIA | MPS Q1 FY2026 (04-30-2026) | Full Motley Fool call: NVIDIA/Rubin never mentioned; "VRM for NVIDIA Vera Rubin" is the enricher's attribution. |
| 46, 47, 48 | Monolithic Power Systems → NVIDIA | MPS Q2 FY2026 (07-30-2026) | 48V vertical modules ship to "more than a couple of customers" — unnamed. |
| 56, 57 | Rambus → Samsung / SK Hynix | Rambus Q1 FY2026 (04-27-2026) | DDR5 RCD/MRDIMM chipsets discussed generically; no module maker named. |
| 58, 59 | Rambus → Samsung / SK Hynix | Rambus Q2 FY2026 (07-27-2026) | DDR5 9600 chipset launch; Samsung/Hynix in neither call summary nor press release. |
| 62 | STMicroelectronics → Amazon | STMicroelectronics Q2 FY2026 (07-23-2026) | Data-center ambition tied to unnamed "engagements"; Amazon/AWS never appears. |
| 63 | Samsung → AMD | AMD Q1 FY2026 (05-05-2026) | AMD: "very happy with our partnerships with the memory vendors" — Samsung never named. |
| 64 | Samsung → AMD | Samsung Q1 FY2026 (04-30-2026) | HBM4 sold-out statements name no customer; AMD never appears. |
| 67 | Sandisk → Meta | Sandisk Q3 FY2026 (04-30-2026) | Ultrastar / +233% data-center facts attributed to no customer; Meta never named. |
| 70 | Sandisk → Kioxia | Sandisk Q4 FY2026 (08-05-2026) | Only "our JV partner"; "(Kioxia)" is the enricher's identification. Q3-label entries on the same edge DO name Kioxia, so the edge stays sourced. |
| 91 (+92) | Vicor → NVIDIA | Vicor Q1 FY2026 (04-21-2026) | "different GPU companies or even hyperscalers" and an unnamed "lead customer"; NVIDIA never named. One entry mirrored in power_cooling.json and power_semiconductor.json. |

Borderline call worth a human glance: todo 5 (Apple → TSMC). The attribution is almost certainly true in the real world,
but the document never says it, and the project rule is "only what the source says". The same facts live on Apple's
node ("CALL-ONLY: THE JUNE-QUARTER SHORTFALL WAS A LEADING-EDGE NODE SHORTAGE …").

## Sets (4) — entries that misquote the source

| todo | entry | what was wrong → what it now says |
|---|---|---|
| 2 | AD Technology Q2 FY2026 (08-14-2026), order-book entry | Four >10% customers sum to 23,205,218+12,089,399+10,910,563+10,543,898 = 56,749,078 thousand KRW → **KRW 56,749M**, not 56,750M (figure + signal). |
| 15 | GlobalFoundries Q1 FY2026 (05-05-2026), results entry (optical_networking.json) | Only $1.634B and "+50% design wins" matched the call. The call states ~29% gross margin ($474M GP, +510bps), 16.6% operating margin ($271M), net income ~$227M, diluted EPS $0.40, CFO $542M, capex $309M, adj. FCF $233M, CID +32% / auto +24% YoY. The entry had GM 27.6%, op margin 11.0%, NI $104M, EPS $0.18, "EBITDA $561M" (561 is the diluted share count in the call) and a "$0.12 first dividend" that is nowhere in the transcript. Rewritten to the call's figures. |
| 17 | HD Hyundai Electric DART supply contract (08-27-2026) | The 08-27 filing is only the amendment (KRW 64.4B, 3.06%, end date 2026-08-31 → 2027-05-31). The KRW 12,310,500M backlog, "58.5B supplied / 52.7B collected" and the "raised from 58.5B / first extension" history come from the half-year report (a different labelled source). Stripped to what this filing states. |
| 71 | Sanil Electric DART supply contract (08-20-2026), backlog-slot entry | The 08-20 block states only the TMEIC USA order (KRW 51,197,779,428 / USD 36,284,748, 10.20% of revenue). The "backlog KRW 556.8B (+16.6% QoQ)" clause comes from the half-year report — stripped from figure and signal. |

## Keeps (65 + 2 blocked) — why the auditor was wrong, by pattern

Roughly 45 of the 68 keeps are the same mechanical gap: the entry rounds a statement figure to the nearest
million/billion and `Doc.has_number()` only tries an exact digit-prefix rescale.

| pattern | examples (todo) | what the doc has vs. what the entry wrote |
|---|---|---|
| **Rounding to the nearest M/B/T after unit rescale** | 1, 4, 10, 11, 18, 19, 23, 24, 38, 39, 53, 65, 66, 68, 69, 73, 74, 77, 78, 80–83 | `45,945,836,761` → "45,946M"; `151,196,513,099` → "151,197M"; `139,882,641,673` → "139.9B"; `$8,965 million` → "$8.97B"; `164,179` → "164.2B"; `392,355 (천USD)` → "USD 392.4M"; `44,644,659,857` → "44,645M". The digit-run prefix test (`"556788".startswith("5568")`) fails whenever rounding carries a digit. |
| **Transparent arithmetic on stated figures** | 3, 9, 20, 21, 25–34, 52, 54, 75, 76, 79, 88, 89 | IP 27,089 = 1,415 + 25,674; SEC contracts 676+790+883억 = 234.9B; 88.9% = 725,480/384,060 (both rows in the filing); 52.2% = 0.209+0.179+0.134; PSK Inc. 4,395,534,940 = 2,599,528,000+904,601,400+891,405,540; Sanil 89.5% = 32.1+19.9+19.0+18.5; Simmtech net debt 633.2B = 478,559+73,197+142,912+29,549−91,056; Teradyne $1,329M = 843+212+67+107+100; Semtech $145M = $100M × 1.45. |
| **Counterparty named in Korean, no alias in `KO_ALIASES`** | 8, 12, 13, 49, 50, 51, 54, 60, 61, 87 | 시스코시스템즈캐피탈 (Cisco), 동우화인켐㈜ (Dongwoo Fine-Chem), (주)포스코 (POSCO, three filings), 피에스케이㈜ (PSK Inc.), 에스케이에어플러스㈜ (SK Airplus), SK스페셜티㈜ (SK Specialty), 다이요잉크프로덕츠㈜ (Taiyo Ink Products = Taiyo Holdings). |
| **Counterparty named via subsidiary / brand / abbreviation** | 40, 41, 42, 29 | AWS (Amazon), ATOTECH / Atotech Korea Co., Ltd (MKS Instruments), PSE (Puget Sound Energy, the filing's own abbreviation). |
| **Short names defeated by the ≥5-letter first-word fallback** | 22, 84 | "Xcel" (4 letters) is in the doc as "HD Hyundai Electric America (미국 Xcel)"; "ASE" in "Big5 패키징전문 기업(ASE, Amkor, SPIL, JCET, PTI)". |
| **Companion earnings-release file under the same label** | 6, 14, 35, 36, 55, 88, 89 | Astera "Taurus 1.6T … AMD Advancing AI" (release line 70); FormFactor "+31.9% from $195.8 million"; Intel "Intel Foundry 5.8 billion up 31%", High NA EUV HVM, €5B Intel 3; Qualcomm "Handsets $5,086 $6,328 (20%)"; Teradyne "$1,329 million … $1,122 million". The auditor resolves each label to ONE file (the call), never the `*_earnings_release.txt` companion. |
| **Numbers in words / ratios as decimals / sub-3-digit rescale** | 85, 86, 52, 90 | "more than 6 thousand … racks per month"; "0.209" for 20.9%; "$700 million" for "$0.7B" (rescale requires ≥3 digits). |
| **Wrong file resolved (Korean header label)** | 71, 72 | `supply_contracts/sanilelectric.txt` block header reads `# source label: Sanil Electric DART 공급계약 (08-20-2026)`; the chain (correctly, English-only rule) says `DART supply contract`. `by_label` misses, strategy 3 matches the `dart` token and lands on the half-year report, where 51,197,779,428 / 36,284,748 do not exist. The numbers are verbatim in the supply-contract block. |

Two counterparty keeps deserve a structural glance by the human owner (they are supported by the source, so they were kept):
- todo 8, Cisco → Naver Cloud: the "deal" is an asset-lease **financing facility** (KRW 80,695M limit) with "Cisco Systems Capital and others" — a lessor relationship, not a stated equipment purchase.
- todo 29, Hyosung → Puget Sound Energy: "PSE" is only an abbreviation in the filing's customer list; the expansion to Puget Sound Energy is the enricher's (standard in US-utility context).

## Blocked / undecided

- **todo 65 and 66 (Samsung Q2 FY2026 (08-14-2026), H1-report results and capacity entries): verdict KEEP** —
  Q2 revenue 171,499,470M → 171.5T, Q2 OP 89,492,412M → 89.5T, DS segment OP 142,859,293M → 142.9T, PP&E 224,371,952M → 224.4T
  are all statement figures rounded. **They could not be filed**: `chains/components/nand_flash.json` contains **two separate
  "Samsung" player entries in the same sector (memory / NAND Flash — one with 5 quarterly_data, one with 9)**, each holding a
  byte-identical copy of these entries, so the (company, label, prefix) locator matches two entries in one chain and
  `apply_corrections.py` refuses as ambiguous (by design). Fix first: de-duplicate the Samsung node in `nand_flash.json`
  (merge the two players; integrity-agent job), then these two keeps need no action anyway.
- todo 91 / 92 are one entry mirrored in two chain files; filed once (see acc-1_4.json, `todo_item: "91+92"`).

## Systematic findings & concrete suggestions for `verify_graph.py` (not edited)

1. **Rounding-aware rescale** (biggest single source of false fails, ~45/92 here). In `Doc.has_number`, after the exact
   checks, test `any(round(v * 10**k, decimals) == value for v in self._values() for k in range(-12, 13))` — i.e. rescale the
   document's numbers by powers of ten and round to the figure's own precision. This alone clears 45,945,836,761 → 45,946M,
   8,965 → 8.97B, 392,355 → 392.4M, 0.209 → 20.9 (k = 2), 700 → 0.7 (k = −3).
2. **Resolve a label to the SET of source files, not one.** `by_label.setdefault` keeps only the first file, and
   `*_earnings_release.txt` companions never carry a `# source label:` header at all. Collect every file whose header label
   matches OR whose filename joins to the label (including the `_earnings_release` suffix) and pass a number if **any** of
   them contains it. Seven keeps here (Astera, FormFactor, Intel ×2, Qualcomm, Teradyne ×2) were failed by this alone.
3. **Aliases from metadata, not a hard-coded table.** Add an `aliases` list to `company_metadata.json` (Korean legal names,
   subsidiaries, brands, tickers) and build `KO_ALIASES` from it. Missing today: Cisco/시스코, POSCO/포스코, Dongwoo
   Fine-Chem/동우화인켐, SK Airplus/에스케이에어플러스, SK Specialty/SK스페셜티, PSK Inc./피에스케이, Taiyo Holdings/다이요잉크프로덕츠,
   MKS Instruments/Atotech, Amazon/AWS, Puget Sound Energy/PSE. Lower the first-word fallback from ≥5 to ≥3 letters when the
   token is upper-case or the full company name is ≤ 2 words (Xcel, ASE).
4. **Normalise Korean header labels** when indexing: map `DART 공급계약` → `DART supply contract` (and `잠정실적` → `preliminary
   results`) so `supply_contracts/*.txt` blocks written by `dart.py` join to the English chain labels. Better still, have
   `dart.py` write the English header (the chain label is the canonical one under the English-only rule). Until then, strategy 3's
   `dart` token match sends every supply-contract label to the wrong file.
5. **Number-in-words and word-scale units**: parse "6 thousand", "1.3 billion", "700 million" into numbers before matching.
6. **Right number, wrong role — the check that does not exist yet.** GlobalFoundries (todo 15) passed "561", "0.18" and "104"
   because those digit strings occur elsewhere in the call (561 = diluted share count), and Qualcomm (todo 55) passed "20"
   through an unrelated "20%". A proximity test — the figure's neighbouring keyword ("EBITDA", "dividend", "gross margin")
   must appear within ~100 characters of the matched number — would catch the mis-transcribed entry the number check cannot.
7. **Derived figures**: an entry that states a sum/ratio (13 keeps here) will always fail a literal matcher. Either allow a
   `derived: true` flag on quarterly_data/contract entries that downgrades `number_not_in_source` to `warn`, or try
   two-term sums/ratios of document numbers before failing.
8. **Duplicate-node detection** belongs in the audit: the same company appearing twice in one sector of one chain
   (Samsung in `nand_flash.json` memory/NAND Flash) silently doubles every derived view and blocks correction tooling.

## Housekeeping notes
- The per-session scratchpad directory is shared by all ~11 agents; my helper scripts are prefixed `acc1_` after an
  earlier unprefixed helper was overwritten by another agent's file of the same name.
- Nothing outside `patches/corrections/acc-1_*.json` and this report was created or modified; no build/apply/git-state
  command was run.
