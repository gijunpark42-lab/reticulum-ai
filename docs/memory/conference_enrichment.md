---
name: conference-enrichment
description: "`enrich conference` pipeline (added 2026-09-10): investing.py conferences → transcripts/conferences/ → depth-rule enrich (multi-agent + verify loop) → memory; progress log of which companies/conferences were pulled and enriched"
metadata:
  type: project
---

Added 2026-09-10 at the user's request ("investing.py에 conferences 붙여봐"): `python investing.py conferences`
walks Investing.com's /news/transcripts listing pages, saves the verbatim fireside-chat part of every
"<Company> at <Conference> YYYY: …" article for ANY company in company_metadata.json (US included),
into `transcripts/conferences/`, queue rows `kind: "conference"` in investing/pending.json.
Rules live in `.claude/skills/enrich/references/conferences.md` (trigger `enrich conference`):
depth rule (only what the latest earnings call did not say), ≤8 enricher + verifier agents writing
patches only, ONE `graph_build.py --sync`, verify loop to 0 fail, `investing.py done --kind conference`,
then update THIS memory. Run history (when, pages, oldest date, saved) is in
`investing/conferences_state.json` → `runs[]`; that file is the authoritative "how far did we get".

**Progress log**
- 2026-09-10 19:46–~20:10 — pull complete: 130 listing pages walked back to **2026-08-06**, then the site
  answered 403 (bot cool-off; `get()` now waits 60 s and retries). **84 files saved, dated 2026-08-10 → 09-10,
  40 companies**, all in the queue, **none enriched yet**. 1 fail (STMicro at Citi TMT, 403) — retried next run.
  Companies (count): Seagate 3, Arista 3, Dell 3, Applied Materials 3, AMD 3, Equinix 3; Penguin Solutions,
  TE Connectivity, Lam Research, NVIDIA, Sandisk, Microsoft, Lumentum, Cadence, Nebius, Marvell, NetApp,
  Qualcomm, Micron, onsemi, Intel, Oracle 2 each; SpaceX, Credo, Uber, Supermicro, HPE, Advanced Energy,
  Teradyne, SiTime, Digital Realty, Flex, Onto Innovation, FormFactor, TTM, MaxLinear, Amphenol, KLA,
  Astera Labs, Western Digital 1 each. Conferences: Goldman Sachs (Communacopia) ~24, Citi Global TMT 15,
  Deutsche Bank Technology 7, Six Five Summit 9, Rosenblatt AI summit 2, KeyBanc Technology Leadership Forum 4, Jefferies 1.
- Window still short of 180 days (June conferences: BofA, Mizuho, Nasdaq, Stifel not reached). A later
  `python investing.py conferences` continues past page 130 automatically.
- Enrichment: none yet. Next `enrich conference` = read `runs[]`, then the 84-row queue, multi-agent per the reference.

**Why:** conference talk is management speech between calls (mid-quarter guidance, new customers) and
no other pipeline carries it; user chose this over YouTube captions / GDELT (2026-09-10).
**How to apply:** never commit ([[feedback_no_auto_commit]]); patches only ([[concurrent_job_race]]);
transcript-grounded only ([[feedback_transcript_only]]) — a fireside chat is a transcript, not news.
Related: [[feedback_transcript_sourcing]], [[edgar_enrichment_2026_09_10]] (the multi-agent recipe reused).
