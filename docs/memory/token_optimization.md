---
name: token-optimization
description: "Token-optimization agent role (2026-09-10) — what is already applied, what was measured, what was rejected, and the zero-accuracy rule"
metadata: 
  node_type: memory
  type: project
  originSessionId: f60baf64-4d9a-4525-9e3e-d54093989c24
  modified: 2026-09-11T02:08:00.670Z
---

User made Claude the **token-optimization agent** (2026-09-10): find savings, apply them, report the % saved.
**Scope = BOTH projects: earnings-ai AND Trading (`Desktop\Trading`).** Trading's record lives in `~/.claude/projects/C--Users-calif-Desktop-Trading/memory/token_optimization.md`.
Hard rules: **zero accuracy impact** and **never disturb enrich agents running in parallel**.

**Already applied (verified 2026-09-10):**
- 2026-09-09, session 3a8b1d3b (continued from 9900ec39, the "GitHub popular method" ask): CLAUDE.md 48,647 → ~21.5K bytes by moving workflows VERBATIM into `.claude/skills/` (progressive disclosure). Line-diff check: every old line still exists except 2 meta sentences. ≈7.3K tok per API call ≈ 3.3% of all input-side tokens.
- Same session: `graph_build.py` hub list → `graph/hubs.txt` + print only the diff (stdout −72.9%, ~3.8K tok/build).
- 2026-09-10 (this role): `.graphifyignore` + `graphify update . --force` (AST only, no LLM, no API key in env). Nodes 2,499→1,534, GRAPH_REPORT 58.9K→28.1K bytes, graph.json −30%. Lost only the 2 logo manifest.json files (1,002 noise nodes); all code/.md kept (docs inside data dirs re-included with `!` rules). Backup of the old graph: `graphify-out/2026-09-10/`.

**Measured, NOT worth it / rejected (don't re-propose without new data):**
- Transcript text = ~78% of text Reads; needed for accuracy. DART has 8.9% repeated lines but they are table headers/footnotes (real structure). av/investing/tw/edgar have ~0% redundancy.
- `project_state.md` memory (86KB) was never recalled in 12 days, so archiving it saves nothing.
- CLAUDE.md vs skills: 0 duplicate lines. The Read tool does NOT truncate 3K+ char transcript lines (tested).

- 2026-09-10 (user said "걍치워"): the orphan `.claude/worktrees/chain2d-vertical` (458 files byte-identical to branch `chain2d-vertical`, no session using it) was MOVED (not deleted) to `C:\Users\calif\worktree-backup\earnings-ai-chain2d-vertical`. The worktree copies no longer show up in Glob (they had been 13 of 64 `**/*.py` hits). The branch is intact.
- Lesson: Glob DOES walk hidden `.claude/worktrees/`, but Grep doesn't. Any future worktree left inside the repo pollutes Glob again.

**Vercel plugin: KEEP ON (user decision 2026-09-10, "VERCEL는 끄지마").** Turning it off would save ~2.9K tok/call (~1.3%), but the user refused. Don't propose it again.

**How to measure:** parse `~/.claude/projects/*earnings-ai*/**/*.jsonl` and dedupe usage by `message.id`. Over 12 days: 3,956 API calls, 868M input-side tokens, ~219K context per call.
