---
name: codex-handoff
description: Since 2026-09-12 the repo is shared with Codex — AGENTS.md (load order + rules), docs/HANDOFF.md (state, next up, session log) and docs/memory/ (snapshot of this memory dir) are the shared record; update HANDOFF.md at the end of every session
metadata:
  type: project
---

On 2026-09-12 the user said they will "plug in Codex" and asked for a record so Codex can read one file and
continue (progress, what was planned, the enrich pipelines). Created:
- `AGENTS.md` (repo root; Codex reads it automatically) — load order: CLAUDE.md → docs/HANDOFF.md →
  .claude/skills → docs/memory; short form of the hard rules; Windows python path; end-of-work sequence.
- `docs/HANDOFF.md` — pipelines table with queue status, current state, "Next up" (conference queue 84,
  EDGAR round 3b week of 2026-09-14, routine syncs, user curation items, rejected ideas), gotchas, commands,
  and an append-only **Session log**.
- `docs/memory/` — a COPY of this memory dir taken 2026-09-12 (snapshot, not a live link).

**Why:** both agents share one working tree; without a shared written state Codex cannot know what Claude
did or decided, and vice versa.
**How to apply:** at the end of every significant session, append a dated entry to the Session log in
`docs/HANDOFF.md` and refresh its "Current state" / "Next up" sections. When a memory file here changes in
a way Codex needs, re-copy it into `docs/memory/` (or tell the user the snapshot is stale). Codex is told (AGENTS.md → "Recording your progress") to append a session-log entry, refresh §3/§4, and write rule
changes into docs/memory/ — so at session start ALWAYS read the newest Session-log entries and diff docs/memory/
against this dir (copy back anything Codex added or changed). Read the
Session log at session start — Codex may have worked since the last Claude session. Never commit these
files on your own ([[feedback_no_auto_commit]]). Related: [[concurrent-job-race]], [[conference-enrichment]].
