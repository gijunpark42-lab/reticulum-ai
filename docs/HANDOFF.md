# HANDOFF — where the project stands and what to do next

Shared progress record for every agent working in this repo (Claude Code, Codex, ...).
Read `AGENTS.md` first for the load order and the hard rules. This file answers three questions:
**what is done, what is in flight, what comes next.** Append to the session log at the end of every
session; edit the "Current state" and "Next up" sections in place so they stay true.

Last full update: **2026-09-12** (Codex UI session; original Claude handoff history preserved below).

---

## 1. What this project is (one paragraph)

A graph of the AI / semiconductor supply chain. 25 chain files under `chains/{accelerators,components,
manufacturing}/` (one per investment-significant product GENERATION, e.g. `nvidia_vera_rubin`, `nvda_b200`,
`tpu_v8t`), merged by exact company name into `graph/merged_graph.json` (352 nodes / 1,359 edges on
2026-09-12). Every node carries `quarterly_data` and every edge carries `contracts`, each entry sourced to a
transcript or filing saved under `transcripts/` with a canonical label like `NVIDIA Q2 FY2027 (08-27-2026)`.
The user curates the STRUCTURE (companies, layers, edges); agents do ADD-only ENRICHMENT from transcripts.
A Next.js app in `web/` (live on Vercel, project `reticulum-ai`, domain gijun42.com) renders it: Graph,
Chain 2D, Generations, Timelines, Screener, Capex, Coverage, Exposure, Ask, Semi Bot tabs.

## 2. The pipelines (how transcripts get in)

| Command | Script | Region / source | Queue file | Status 2026-09-12 |
|---|---|---|---|---|
| `enrich us` | `av.py sync / pending / done` | US calls via Alpha Vantage (25 req/day). Fallback: `utils/defeatbeta_fetch.py "<Name>" <TICKER>` (no quota) | `av/pending.json` | empty |
| `enrich dart` | `dart.py sync / pending / done` | Korean 정기보고서 / 잠정실적 / 공급계약 via DART | `dart/pending.json` | empty |
| `enrich intl` | `investing.py sync / pending / done` | Taiwan/Japan/Europe/HK English calls via Investing.com | `investing/pending.json` (kind=transcript) | empty |
| `enrich tw` | `tw.py sync / fetch / transcribe / done` | Taiwan Chinese-language 法說會 → yt-dlp → faster-whisper | `tw/pending.json` | empty |
| `enrich edgar` | `edgar_pull.py [--tickers A,B] [--force]` (pull) / `queue` / `done [--with-dropped]` | SEC 8-K / 10-K / 10-Q whole filings | `edgar/pending.json` | empty (round 3b pending, see §4) |
| `enrich conference` | `investing.py conferences / done --kind conference` | Investor-conference fireside chats, all listed names | `investing/pending.json` (kind=conference) | **84 rows waiting, none enriched** |
| `Transcript:<company>` / pasted text / URL | manual | user-supplied full transcript | — | — |

Each pipeline's procedure is in `.claude/skills/enrich/references/<pipeline>.md`. The shared patch format,
JOB 1–5, the label format and the build+verify step are in `.claude/skills/enrich/SKILL.md`.

Per-pipeline health (last sync, source date range, pending, files with no data) is regenerated into
`graph/enrich_status.json` by `enrich_status.py` on every build and shown on the Coverage tab. The
append-only history is `enrich_log.json` (commit it).

## 3. Current state (edit in place)

- **Git:** `main`, UI refresh prepared on top of `0993d57` on 2026-09-12. User explicitly authorized immediate
  deployment in this session, including the necessary commit/push. See the newest session entries for
  the deployment result. The standing no-auto-commit preference still applies to future sessions.
- **Graph:** 352 nodes, 1,359 edges, 25 chains, 799 applied patches in `patches/applied/`.
- **Coverage by pipeline (from `enrich_log.json`, 2026-09-11):** edgar 1,012 files / 432 in graph;
  dart 48/48; intl 30/29; tw 17/17; conference 84/0; manual 244/244.
- **Web app:** live; 2026-09-12 UI refresh in `web/src/app/{page.tsx,workspace.css}` and
  `web/src/components/{Sidebar.tsx,SearchBox.tsx}`: research-view headings, graph summary, scrollable
  keyboard-operated tab strip, mobile filter focus management, accessible sidebar sections/search clear,
  loading retry and empty-filter recovery. Connection count now reads immutable source edges instead of
  the force renderer's mutated links. Deploy = push to main, Vercel Root Dir = `web`.
  Verification artifacts: `C:\Users\calif\Documents\Codex\2026-09-12\earnings-ui-review\`.
- **Ask tab:** answered by a LOCAL Claude runner (`local-ask/`) behind a Cloudflare tunnel. `ask 실행` starts it
  (`node local-ask/up.mjs`), `ask 종료` stops it. No Gemini, no Anthropic API (removed in 3bfb0dc).
  If the runner is down the tab falls back after ~3 min. Codex cannot run this engine (it shells out to `claude -p`).
- **Memory snapshot:** `docs/memory/` = copy of Claude's memory dir taken 2026-09-12. `docs/memory/MEMORY.md`
  is the index. `project_state.md` there is an 86 KB enrichment history; open it only when you need a
  specific company's past enrichment.

## 4. Next up (ordered; edit in place)

0. **UI release (2026-09-12):** implementation and local browser verification complete; finish the authorized
   main push, verify https://gijun42.com, and append the resulting commit/deployment status below.
   No enrichment queue or data-rebuild step is part of this UI session.
1. **`enrich conference` — 84 fireside chats, 40 companies, 2026-08-10 → 09-10.** Nothing enriched yet.
   Procedure: `.claude/skills/enrich/references/conferences.md`. Depth rule: add ONLY what the company's
   latest earnings call (its existing node entries) did not already say. Multi-agent (≤8 enrichers + a
   verifier each) writing `patches/` only, ONE `graph_build.py --sync`, verify loop to 0 fail, then
   `python investing.py done --kind conference`, then update `docs/memory/conference_enrichment.md` +
   this file. Run history lives in `investing/conferences_state.json → runs[]`. A later
   `python investing.py conferences` continues past listing page 130 (June conferences not yet reached).
2. **EDGAR round 3b — "read ALL recovered tables", user scheduled it for the week of 2026-09-14.**
   Prep is finished: `transcripts/edgar/` was re-pulled 137/137 tickers (2026-09-11 night), the 5 old
   verify fails pass again. Durable archive: `C:\Users\calif\edgar_round3b\` (ledger `R3_PROGRESS.md`,
   briefs `AGENT_BRIEF_R3B.md` + `VERIFIER_BRIEF.md`, `delta_rows_r3b.json` = 437 files / 9.7 MB of unread
   delta text, `r3b_image_pages.json`, `r3b_inscope_loss.json`).
   Resume: `python -X utf8 utils/edgar_batches.py 26 <archive>/delta_rows_r3b.json`
   → enricher + verifier per batch (patches named `edgar_<stem>_r3b.json`) → one `graph_build.py --sync`
   → full `verify_graph.py`. Option A was chosen: read every table, do NOT narrow to "in-scope" tables.
   Before batching, consider adding "bookings" / region words to `TABLE_KEEP_RE` in `edgar_pull.py` and a
   no-token re-pull (Kulicke & Soffa bookings table, TE Connectivity region×segment table were still dropped).
   Full context: `docs/memory/edgar_enrichment_2026_09_10.md` and `.claude/skills/enrich/references/edgar.md`.
3. **Routine syncs** whenever the user says `enrich` / `enrich us` / `enrich dart` / `enrich intl` / `enrich tw`:
   sync → pending → enrich → build → done. Bare `enrich` means "use the API pipelines"; do not ask which source.
4. **Open curation items for the USER (do not do these unprompted):** logos for the 38 US nodes added
   2026-09-10 (`docs/memory/logo_fetching.md`); Carrier could also sit in Heat Exchanger / CDU; GE Vernova has no
   gas-turbine node (Power-segment facts were dropped); pre-existing GE Vernova → AEP edge; Eaton / Eversource
   call-label dates differ from the real call dates.
5. **Rejected / do not re-propose:** news pipelines or knowledge-based edges (`feedback_transcript_only.md`),
   a Quant tab in the web app, turning off the Vercel plugin, adding Core42 / AES / Nanjing Casela as nodes,
   auto-committing, GitHub Actions scheduler (not until the core loop is declared solid by the user).

## 5. Standing decisions and gotchas (the ones that bite)

- **Lost-update race:** several agents enrich in parallel and many companies share one chain file. Never
  read-modify-write `chains/`. Patches only. A structural edit (move/rename/delete) that must touch `chains/`
  needs a HEAD-vs-worktree audit right after (`docs/memory/concurrent_job_race.md`).
- **Label prefix == node name.** `av.py` / `investing.py` decide "already enriched?" by matching the label's
  company prefix to the node name. A mismatch (`Arm` vs `Arm Holdings`) re-pulls the company every sync.
- **Alpha Vantage keys transcripts by FISCAL quarter** and its calendar returns only future dates. Never fall
  back to a calendar-quarter guess when the graph already has history for that company (Flex, Arm traps).
- **Call transcripts drop the zero in "$X.0Y"** (Vicor "$1.4" = filed $1.04). Cross-check per-share figures
  against the same company's 8-K when both exist.
- **Multi-node companies in one chain** (NVIDIA in two sectors of `foundry.json`): write a signal to ONE
  placement, not every player matching the name, or the merged node shows it twice.
- **Edge rule for new edges:** the counterparty must be NAMED by management (not an analyst) AND already be
  a node in that chain file. "Collaboration" partnerships are not edges.
- **Contract placement:** a contract goes on an existing edge only if the fact matches that edge's relationship
  AND direction. Company-wide facts go on the placement that holds the company's call entries.
- **verify_graph false alarms:** numbers spelled in words ("two and a half gigawatts"), sums/deltas you
  computed. Say so in the report instead of "fixing" them.
- **Renames** are an 8-step structural procedure (chains + labels + metadata + transcript headers + logos +
  edgar rows + rebuild + verify). `docs/memory/naming_rules.md` has the checklist and a worked example.
- **Skeleton builds** (new chain file) write `chains/` directly (new file, no collision) and must be checked
  against `docs/memory/common_fixes.md` (fake sub-brands, "AWS" → "Amazon", "Meta AI" → "Meta", ...).
- **The user's style:** Korean, short, casual; answers like "어", "어 그러자" mean yes. Report the call date
  before enriching. End reports with the commit command, never run it.

## 6. Useful commands

```powershell
# PowerShell (python is not on PATH)
cd "C:\Users\calif\Desktop\earnings-ai"
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" graph_build.py --sync
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" -X utf8 verify_graph.py --label "NVIDIA Q2 FY2027 (08-27-2026)"
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" av.py sync          # then pending / done
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" investing.py conferences
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" -X utf8 utils/show_filing.py transcripts/edgar/<file> 1   # page number is positional
& "C:\Users\calif\AppData\Local\Python\bin\python.exe" -X utf8 utils/check_edgar_patch.py patches/<patch>.json
cat graph/hubs.txt        # full hub list (the build prints only what changed)
```

Suggested commit after an enrichment run (only when the user says commit):

```
git add chains patches graph web/public transcripts enrich_log.json <queue files> docs/HANDOFF.md
git commit -m "<what was enriched>"
```

---

## 7. Session log (append-only, newest at the bottom)

Every session ends with one entry here, whichever agent worked (Claude or Codex). Format and the
full recording rules are in `AGENTS.md` → "Recording your progress". Short version:
`- **YYYY-MM-DD (Agent)** — asked / done (counts, verify result) / decisions / left open (exact resume point) / uncommitted yes-no`.
Also refresh §3 and §4 above, and `docs/memory/` if a rule or preference changed.

- **2026-09-12 (Claude)** — Handoff created for Codex: `AGENTS.md`, this file, `docs/memory/` snapshot of
  Claude's memory dir. No data changed. Working tree otherwise clean at c504d27. Open work unchanged:
  conference queue (84), EDGAR round 3b (next week), routine syncs.

- **2026-09-12 (Codex, Astra xhigh)** — Asked: improve the Earnings AI website UI with a dedicated agent,
  then deploy immediately and record everything so Claude can resume. Done: refreshed research navigation,
  graph overview, native keyboard-accessible filter sections, mobile drawer focus trap/Escape/return focus,
  search shortcut and keyboard clear, load retry, and empty-filter recovery in the four frontend files above.
  Fixed the displayed connection count falling to zero after toggling filters: the 3D library mutates
  visual-link endpoints into objects, so the UI now counts the unchanged `graph.edges` source IDs.
  Validation: TypeScript `--noEmit --incremental false` passes; headless browser verification passes all
  12 check groups with 0 client exceptions, including all nine research views, 1440px desktop and 390px
  phone screenshots, count recovery, keyboard navigation and simulated load failure/retry. Scripts and
  screenshots are saved in the artifact folder above. No chains, graph, web/public data, transcripts,
  pipeline queues, analytics or external service settings were changed. Local builds invoke the Next.js
  binary directly to avoid `prebuild` data sync. Decisions: user required Astra + extra-high effort and
  explicitly authorized immediate deployment; preserve the standing no-auto-commit rule for later work.
  Left open at this checkpoint: finish production build, commit/push the UI release, verify live site,
  and append completion here. Uncommitted: yes (this release only; checkout was clean at start).
