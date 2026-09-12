---
name: feedback_transcript_sourcing
description: Transcript sources by region since 2026-08-31 — US: Alpha Vantage (av.py, `enrich us`); Korea: DART (dart.py); Taiwan/Japan/Europe/HK: Investing.com via curl_cffi (investing.py, `enrich intl`, English-language calls only); Motley Fool only as same-day fallback
metadata:
  type: feedback
---

**Decision (2026-08-31):** the user chose Alpha Vantage `EARNINGS_CALL_TRANSCRIPT` as the US transcript
source — "alpha vantage로 하자, 이제는 Motley Fool 노가다가 아니라". `av.py sync / pending / done`
(trigger `enrich us`) replaces hand-finding Motley Fool URLs. Verified: the endpoint returns the
WHOLE call (IBM 2024Q1 = 37 speaker turns, 51k chars, prepared remarks + full analyst Q&A), not a summary.

**Why:** the user wants the pipeline to run without manual URL hunting; free key (25 req/day) is
enough for the ~100 US names; transcripts appear within ~1 day of the call.

**Default since 2026-08-31 (user):** the bare word **`enrich`** now means USE THE API PIPELINE
automatically — `enrich` / `enrich us` / `enrich dart` / `enrich intl` all run sync → pending → enrich →
`graph_build.py --sync` → done. The user only pastes full transcript text when they deliberately want a
call the API does not have; a pasted transcript or an explicit different instruction overrides the API.
Do not ask which source to use.

**How to apply:**
- `enrich us` → `python av.py sync` → enrich every `pending` row → `graph_build.py --sync` → `av.py done`.
- Motley Fool paste (Workflow 2) only when a call is `waiting` on Alpha Vantage and the user needs it today — same label.
- Always the latest FULL transcript; report the call date before enriching; labels come from the file header.
- Needs `ALPHAVANTAGE_API_KEY` in `.env` (user must claim it; not present as of 2026-08-31).
- Non-US/non-Korea (88 names): `investing.py sync` (`enrich intl`) — Investing.com transcribes English calls
  (Alchip, MediaTek, ASMPT, Nanya Tech, Tokyo Electron, Advantest, SUMCO, Infineon). NOT Quanta/Wiwynn/
  Wistron/Unimicron/Foxconn/Lasertec (Chinese/Japanese calls). User asked "can you pull the full text
  from Investing.com despite the firewall?" → yes, curl_cffi Chrome impersonation; verified Alchip Q2 2026.
- defeatbeta (HF mirror of Yahoo transcripts) = US only, free, no quota, ~1-2 day lag, labels match ours.
  Zero .TW/.HK/.KS coverage (queried 2026-08-31). **USED IN ANGER 2026-09-07**: `av.py sync` died at
  `QUOTA daily limit reached` after only 4 of 12 gap companies (the key IS on the 25/day standard tier
  after all — the 2026-08-31 note below is wrong). `defeatbeta_api` 0.0.60 is already installed. Recipe
  that worked (one-off script in the job tmp dir, NOT repo code): `Ticker(sym).earning_call_transcripts()`
  -> `.get_transcripts_list()` (cols symbol/fiscal_year/fiscal_quarter/report_date, OLDEST first, so take
  `.tail()`) -> `.get_transcript(fy, q)` -> DataFrame (paragraph_number/speaker/content). Write it in
  av.py's exact header format (`SOURCE:` / `CALL DATE:` / `QUARTER:` / `# source label:`) into
  `transcripts/av/<slug>_q<N>_<fy>.txt`; the corpus join, verify_graph and evidence.py then treat it
  identically to an Alpha Vantage file. **Its fiscal_year/fiscal_quarter keys matched the graph-derived
  'latest label + 1' on all 6 companies tried**, including the March-FY traps Flex and Modine — so it is
  a safe independent cross-check on a label. Importing it prints an ASCII banner: redirect stdout.
  Wiring it into av.py as an automatic fallback is still an OPEN question the user has not been asked.
- Taiwan Chinese-call names (Quanta, Wiwynn, Foxconn, Wistron, Unimicron, GUC, Elite Material, ...):
  CONFIRMED pipeline (user, 2026-08-31) = `tw.py` (`enrich tw`) — MOPS conference list → YouTube full-call
  video (非凡 etc.) → yt-dlp audio → local faster-whisper verbatim Chinese transcript → enrich translating
  to English (DART pattern). ~30 min CPU per 1-hour call. RESOLVED the earlier open question: monthly
  revenue / MOPS decks are NOT enrichment sources — the transcribed call is. `no_media` calls (webex-only,
  e.g. Quanta broker-hosted) need a hand-found replay URL via `tw.py fetch`.
- The Alpha Vantage key IS present as of 2026-08-31 and is NOT limited to 25 req/day — an 18-transcript
  backfill (36+ requests) ran without a quota message.
- av.py gotchas found and fixed 2026-08-31 (see [[common_fixes]]): EARNINGS_CALENDAR returns only FUTURE
  dates so it can never find who already reported (use EARNINGS per company for past `reportedDate`);
  Alpha Vantage keys transcripts by FISCAL quarter, so a calendar-quarter fallback silently returns an
  OLDER call under a new label (Flex, Arm) — never fall back when the graph already has history.
- Related: [[feedback_transcript_command]], [[feedback_transcript_only]]
