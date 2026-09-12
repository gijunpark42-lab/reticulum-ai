---
name: feedback_transcript_command
description: "\"Transcript: <company>\" standing command — the enrichment pipeline; since 2026-08-27 timelines/screener/capex are DERIVED from graph tags by graph_build.py, not hand-edited"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1e03fa9c-c20d-4641-8ef4-3df9d4fb8404
  modified: 2026-08-27T08:52:18.379Z
---

`Transcript: <company name>` triggers a fixed pipeline (user defined 2026-06-26; steps 5–6 automated 2026-08-27). Run in order:

1. **Get the new transcript** — fetch the LATEST full earnings transcript. US co: Motley Fool first; if not yet published, fall back to the official IR prepared-remarks / press release (the user may also drop the PDF into Downloads — read it directly). Report the call date BEFORE enriching. Save to `transcripts/<sector>/<co>_<quarter>.txt` with a header noting the source and whether live Q&A is included. (see [[feedback_transcript_sourcing]], [[feedback_transcript_only]])
2. **Enrich + TAG** — ADD-only `quarterly_data` + edge `contracts` to every chain where the company is a node, using the canonical source label `[Co] Q[N] FY[YYYY] (MM-DD-YYYY)`. Never invent edges/customers not named in the transcript. (see [[feedback_role]]) **Every new entry gets the derived-view tags** (CLAUDE.md Workflow 2, JOB 5): `topics: [...]` (timeline ids; `[]` for pure financials), `slot` on the ONE best entry per screener column (`revenue_growth` / `guidance` / `backlog_or_b2b` / `supply_status` / `next_catalyst`), and `capex: {field, busd, display, ...}` on hyperscaler/neocloud capex-backlog entries. Untagged entries only reach timelines via a keyword fallback (capped 6 rows/company) and never reach the screener/capex.
3. **Verify** — `python -c "import json; json.load(...)"` on each edited chain; internal-consistency cross-check of headline figures (segments sum to total, EPS ≈ net income / shares, etc.). Then the HEAD-vs-worktree audit from [[concurrent_job_race]].
4. **Build everything** — `python graph_build.py --sync`. This rebuilds `graph/merged_graph.json` (Graph / Chain 2D / Coverage / Generations) AND runs `derive.py`, which regenerates `graph/timelines.bundle.json`, `graph/company_metrics.json`, `graph/capex_backlog.json` from the tags, then `npm run sync` copies all of it into `web/public/data`. Read the build log: it prints "stale curated rows" (screener rows older than the graph with no `slot` tags yet — the backfill queue) and "supersede candidates" (curated timeline rows that now have newer graph data — prune by hand only if wanted).
5. ~~Update timeline by hand~~ — **NO LONGER DONE.** `timelines/*.json` are a frozen curated BASELINE (input to derive.py, never auto-written). Each timeline gets a generated "Latest graph signals (auto-derived)" table appended at build time = latest source per company. Only edit a curated file for a genuinely new hand-researched milestone.
6. ~~Update screener by hand~~ — **NO LONGER DONE.** `company_metrics.json` at the root is the frozen curated baseline / fallback; the served file is `graph/company_metrics.json` (curated row + tagged slots, latest wins). Same for `capex_backlog.json` → `graph/capex_backlog.json`.

**Why:** timeline + screener + capex were separate hand-maintained files that went stale silently (19 screener rows were older than the graph on 2026-08-27). The user's principle (2026-08-27): the graph is the freshest and richest data — everything else must be a projection of it, built conservatively: curated files never auto-written, nothing dropped, generated tables appended.

**How to apply — REPLACE everywhere EXCEPT the graph (explicit user rule, 2026-06-26, now enforced by `derive.py`):** ONLY `chains/` (and therefore `graph/merged_graph.json`) keep full multi-quarter history — ADD-only, never drop. Every derived view shows only each company's LATEST source; a tagged entry overrides a curated slot/field only when it is at least as new as the curated snapshot. Never hand-edit anything under `graph/`. Reports (`reports/`) are a separate pipeline — see [[feedback_report_command]]. Design decision "freeze curated rows + append generated table (no auto-supersede)" was chosen by the user on 2026-08-27 over auto-dropping superseded curated rows.
