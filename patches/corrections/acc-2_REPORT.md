# acc-2 accuracy review — report

Worklist: `patches/corrections/todo_acc2.json` (91 entries, 33 companies, 39 source documents).
Proposals: `patches/corrections/acc-2_1.json` … `acc-2_4.json` (23 / 23 / 23 / 22 items; every one of the 91 todo
items appears exactly once). All four files pass `apply_corrections.py --check --file …` with 0 errors and contain no
Korean characters. No `move` was needed, so no `patches/acc-2_*.json` ADD-only patch was written.

## Counts by action

| action | count |
|---|---|
| keep | 56 |
| delete | 31 |
| set | 4 |
| relabel | 0 |
| **total** | **91** |

## Deletes (31) — all `counterparty_not_in_source`, all contracts

Every delete is a contract whose source document never names the edge's counterparty (0 grep hits in any spelling)
and whose content is a generic company- or industry-level statement that was fanned out onto one or more specific
edges. In every case I verified the same fact already lives on the source company's own node `quarterly_data`
under the same label, so nothing source-supported is lost.

| # | edge | label | why |
|---|---|---|---|
| 0, 1, 4 | AMD → TSMC (3 chains) | AMD Q1 FY2026 | transcript says "2-nanometer process technology" / "advanced packaging"; TSMC and CoWoS never named. 2nm Venice already on AMD node. |
| 2 | AMD → Microsoft | AMD Q1 FY2026 | ">1,600 instances … largest global cloud providers"; Microsoft/Azure never named. |
| 3 | AMD → Amazon | AMD Q1 FY2026 | same sentence, Amazon/AWS never named. |
| 6, 7, 8 | ASML → SK Hynix / Samsung / Micron | ASML Q1 FY2026 | "advanced DRAM and Logic customers continue to further adopt EUV" — no customer named anywhere in the prepared remarks; identical text on three edges. |
| 9 | ASML → TSMC | ASML Q1 FY2026 | "our customers … continuing to ramp the 2 nm node"; TSMC never named. |
| 10 | ASML → SK Hynix | SK Hynix Q1 FY2026 | "key equipment such as EUV tools" — ASML never named. **Borderline** (see below). Fact is on SK Hynix node. |
| 14 | Analog Devices → NVIDIA | ADI Q2 FY2026 | NVIDIA never named ("the XPU, the GPU, the CPU"). |
| 15 | Analog Devices → NVIDIA | ADI Q3 FY2026 | NVIDIA never named (800V / 20 kW / 2.5 kW per cubic inch is ADI product talk). |
| 50, 51, 52 | Lam Research → SK Hynix / Samsung / Micron | Lam Q3 FY2026 | "Stryker … tools of record at all leading memory makers" — no maker named; "Hynix" appears once in an analyst's HBF question unrelated to the claim. Universal statement is on Lam node. |
| 53–56 | Lam Research → Samsung / SK Hynix / Micron / Kioxia | Lam Q3 FY2026 | "as the industry converts to 256 layer and above", "$40 billion in conversion spending" — industry-level, no customer named; four identical copies. |
| 57 | Lam Research → TSMC | Lam Q3 FY2026 | "dielectric etch wins at a key founder [foundry] logic manufacturer"; TSMC never named. |
| 60, 61, 62 | Linde → Samsung / Micron / SK Hynix | Linde Q1 FY2026 | "Electronics increased the most at 10%" — no customer named; three identical copies. |
| 65 | Murata → NVIDIA | Murata Q4 FY2025 | MLCC demand attributed to "hyperscaler customers in the AI-server area"; NVIDIA never named. |
| 66 | Murata → NVIDIA | Murata Q4 FY2025 | "power modules for hyperscalers … plus JPY25 billion" — NVIDIA never named; the +¥25B fact is already on Murata node (mlcc.json). |
| 67 | Power Integrations → Delta Electronics | PI Q1 FY2026 | "two new designs … at Taiwan customers serving U.S. equipment makers"; Delta never named. |
| 69 | Soitec → STMicroelectronics | STM Q2 FY2026 | Soitec never named (only "FD-SOI" as a technology); the entry calls itself a "pull-through signal", i.e. an inference. |
| 82 | Texas Instruments → NVIDIA | TI Q1 FY2026 | NVIDIA never named; data-center commentary generic. |
| 84 | Texas Instruments → NVIDIA | TI Q2 FY2026 (release) | NVIDIA never named; "data center" only as an end market. |
| 85 | Vishay → NVIDIA | Vishay Q1 FY2026 | NVIDIA never named ("800V power management for data centers"). |
| 86 | Wolfspeed → Delta Electronics | Wolfspeed Q3 FY2026 | Delta never named ("power supplies in the data center"). |

Pattern behind all 31: **knowledge edges** — the enricher knew (correctly, in the real world) that AMD fabs at TSMC,
that NVIDIA is the GPU customer behind "AI processors", that Samsung/SK Hynix/Micron are "the leading memory makers"
— and wrote that knowledge onto edges as if the transcript had said it. The user reverted the knowledge-edge program;
these are its residue. Twelve of them are one generic sentence copied verbatim onto 3–4 edges (ASML ×3, Lam ×3 + ×4,
Linde ×3, AMD cloud ×2).

## Sets (4)

| # | entry | change | why |
|---|---|---|---|
| 17 | Arista qd (cpu_datacenter.json), Arista Q2 FY2026 | signal: "(from ~$5.37B a year earlier)" → "(from ~$5.37B at 2025 year-end)" | 6.87 itself is supported (release balance sheet 5,100.7 + 1,765.2), but the 5,372 comparison column is Dec 31, 2025 — prior year-end, not a year earlier. |
| 40 | Isu Petasys qd (packaging_substrate.json), Q2 FY2026 | signal + figure: "+8.5% QoQ" → "+8.4% QoQ" | 622,180 / 573,743 (Q1 report backlog at 2026-03-31) = +8.44%. Arithmetic slip. |
| 49 | Kulicke & Soffa qd (packaging_substrate.json), Q2 FY2026 | signal + figure rewritten to the call's own numbers | "$242.6M revenue", "$191M consensus", "$0.67" are not in the transcript; it states +21.5% QoQ, GM 49.3%, GAAP $0.66 / non-GAAP $0.79, Q3 guide +28% to $310M at 48% GM. |
| 81 | Texas Instruments qd (power_semiconductor.json), Q1 FY2026 | "$4.83B" → "$4.8B", "net income $1.55B" → "$1.5B" (signal + figure) | Call says "$4.8 billion" and "$1.5 billion"; the extra digit is release precision and no Q1 release is on disk. |

## Keeps (56) — what actually supported them

- **Rounded KRW figures (24 items)** — e.g. Daeduck OP 51,298,108,850 won → "KRW 51.3B"; Jusung Q2 revenue 59,881,817,078 → "59,882M";
  Isu Petasys DNP outsourcing 15,788,952 thousand won → "15,789M"; Soulbrain CB repayment 63,595,963,589 → "63,596M".
- **Transparent arithmetic from stated figures (9)** — ISC +6.8% QoQ (72,929 vs 141,201−72,929); Soulbrain top-3 68.9% = 40.91+14.90+13.08;
  EO Technics 30.6% margin and 54.8% export share; Daeduck CCL price +6.8% (107,731/100,872); Isu Petasys remaining capex 242.6 (400,000−157,412, stated in the table itself).
- **Numbers in words / other units (6)** — ASML "half a million wafers" = 500K; IREN "600 thousand GPUs"; Fluence "only non-Chinese inverters" = 100%;
  Wolfspeed "1,200 V" = 1.2kV; Jusung "408.9 eok won" = KRW 40,890M and eight SK Hynix contracts in eok-won summing to 151,900M.
- **Companion document under the same label (8)** — Amazon TTM capex $173.0B, Arista $3.036B / deferred 5,100.7+1,765.2, Meta $31.08B, Microsoft FY26 additions 115,948,
  Lam Q4 128→500+ layers / +$213M / 510×515 / 310×310: all in the 8-K release or `_call.txt` sibling saved for the same event; the auditor opened only the other file.
- **Counterparty named in another form (13)** — Korean names (두산전자 = Doosan Electronics for Doosan Corporation; 솔브레인 = Soulbrain; 에스케이트리켐 = SK Trichem;
  앰코테크놀러지 = Amkor), subsidiaries/abbreviations (STATS ChipPAC Korea = JCET; "EMC" = Elite Material; "ASE" 3 letters), brands (Trainium 3 = Amazon).
- **Judgment calls (2)** — Keysight "$3.7" EPS and NVIDIA "StacyX AI" are speech-to-text slips (details below).

## Systematic patterns in the auditor (verify_graph.py) and concrete suggestions

1. **Rounding across a unit rescale is missed.** `has_number` rounds the document's numbers to the figure's decimals *without* rescaling, and the digit-prefix
   rescale requires the raw digits to agree — so 51,298,108,850 won never matches "51.3" (B), 747,289 백만원 never matches "747.3", 15,788,952 천원 never matches "15,789".
   This produced 24 of my 91 items, all false positives. Suggestion: in `has_number`, for every document number `v` and every power-of-ten scale `s` in 10^0…10^12,
   test `round(v / s, decimals) == value`.
2. **Korean unit words (억원 / 백만원 / 천원) are not scaled.** "408.9억원" vs figure "40,890"; "16,975억원" vs "1,697.5B"; Jusung's "130.3억원" vs "13.03B".
   Suggestion: compare digit strings with dots and trailing zeros stripped (`40890`→`4089`, `408.9`→`4089`; `13.03`→`1303`, `130.3`→`1303`) in addition to the
   \d{3,} run index, and pre-scan Korean docs for `(\d[\d,\.]*)\s*(억|백만|천)` to add the scaled values to `_values()`.
3. **One label, several files.** Companion 8-K releases (`transcripts/non_transcript_sources/*_earnings_release.txt`) and `_call.txt` siblings carry the same event
   label but `resolve_label` returns the first filename match. 8 false positives (Amazon $173B, Arista $3.036B/6.87, Meta $31.08B, Microsoft $115.9B, Lam Q4 ×2).
   Suggestion: resolve a label to the *set* of documents for the same (company, quarter) and pass the union of their text to the NUMBERS/PARTY checks.
4. **Alias table gaps for Korean/abbreviated names.** Not found: Doosan Corporation (두산전자/두산), Soulbrain (솔브레인), SK Trichem (에스케이트리켐/SK트리켐),
   Amkor (앰코테크놀로지/앰코테크놀러지/앰코), Amazon (AWS/Trainium/Annapurna — the table only has "Amazon Web Services"), JCET (STATS ChipPAC/스태츠칩팩),
   Elite Material (EMC), ASE Group (ASE/SPIL — rejected because `compact("ASE")` is 3 chars and the first-word fallback needs ≥5). Suggestion: add these to
   `KO_ALIASES`, allow an explicit whitelist of 3-letter aliases, and add a "Hynix" → SK Hynix token.
5. **Numbers written in words.** "half a million", "600 thousand", "only" (=100%), "1,200 V" vs "1.2kV". Suggestion: a small word-number normaliser
   (`half a million`→500,000, `N thousand/million/billion`→digits) before number extraction; treat `kV`/`k` suffixes by scaling ×1,000.
6. **Cross-document arithmetic is invisible to the auditor** (Isu Petasys +8.5% QoQ used the Q1 filing's backlog). Not fixable mechanically; note that the one
   such case I found was actually wrong (+8.4%), so this class deserves human review rather than auto-pass.
7. **Speech-to-text artefacts in Motley Fool transcripts** ("$3.7" for $3.07, "StacyX AI" for SpaceX AI, "founder logic" for foundry/logic). Suggestion: when a
   number is missing, also try dropping/adding a zero after the decimal point and report it as `warn` ("$3.7 ≈ $3.07?") instead of `fail`.

## Items decided on judgment (flagged for the orchestrator)

- **#10 ASML → SK Hynix (SK Hynix Q1 FY2026) — delete.** SK Hynix said its capex goes to "key equipment such as EUV tools". ASML is the only EUV vendor on earth,
  but the transcript does not say "ASML". I applied the rule literally (counterparty not named → delete); the fact is preserved on SK Hynix's own node. If the
  orchestrator treats "EUV tools" as an ASML brand-equivalent, flip this one to keep.
- **#48 Keysight EPS $3.07 — keep.** The transcript literally says "earnings per share of $3.7". $531M net income / ~172M diluted shares (both stated) = $3.09 and
  +79% growth lands at ~$3.07; $3.70 is impossible. The entry's signal already documents the discrepancy (citing the press release, which is *not* on disk).
- **#78 SpaceX → Anthropic (NVIDIA Q1 FY2027) — keep.** The transcript renders the name "StacyX AI" (and "StacyX xAI" a sentence later); NVIDIA's Q2 FY2027 call
  names "SpaceXAI" as a Vera lead partner. I read it as a transcription of "SpaceX AI". If the orchestrator wants literal-text purity, this is the one keep that
  rests on decoding an ASR error.
- **#40 Isu Petasys +8.4% QoQ — set.** The corrected percentage depends on the Q1 filing (`isu_petasys_q1_2026_dart.txt`, backlog 573,743), not on the Q2 document
  the label points to. I kept the cross-document comparison (the signal names the Q1 date and figure explicitly) and only fixed the arithmetic.

## Follow-ups outside my remit (no file touched)

- The four `set` items and 31 deletes are ready for `apply_corrections.py`; the deletes leave the affected edges' `contracts` lists shorter (some empty) but never
  remove an edge.
- Consider a housekeeping pass on the Motley Fool era files: `arista_q2_2026.txt`, `amazon_q2_2026.txt`, `meta_q2_2026.txt`, `microsoft_q4_fy2026.txt` are condensed
  "user-pasted FULL transcript" summaries (7–10 KB), so precise figures in the graph will keep resolving to the release files; pattern 3 above fixes the audit side.
