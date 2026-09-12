---
name: concurrent-job-race
description: "Enrichment must write patches/, never chains/ directly; structural edits that DO touch chains/ need a move-aware HEAD audit right after"
metadata:
  node_type: memory
  type: feedback
---

Several Claude background jobs enrich `earnings-ai` in parallel and many companies share one
chain file, so "read chain -> think -> write whole chain back" silently drops whatever another
job added in between (a lost update: no error, valid JSON, data just gone).

**The rule (CLAUDE.md, Workflow 2):** an enrichment job writes its additions to
`patches/<company>_<quarter>.json` and NEVER to `chains/` directly. `apply_patches.py` — run
automatically by `graph_build.py --sync` — is the single writer; it re-reads each live chain,
finds-or-creates players/edges by name, appends, and moves the patch to `patches/applied/` as a
receipt. It is ADD-only and idempotent, so patch order does not matter.

**Structural edits still touch chains/ directly.** Patches are ADD-only, so a MOVE (wrong sector),
a rename, or a delete has to be a direct read-modify-write. Those are exactly the risky writes, so
after any of them run a HEAD-vs-worktree audit and re-add anything missing. Observed 2026-08-27:
moving the Keysight node between sectors clobbered an `Analog Devices Q3 FY2026` entry another job
had just committed to `optical_networking.json`.

**How to audit (script: `~/.claude/jobs/<job>/tmp/repair_merge.py`):** diff the set of
`(company, quarter, signal)` quarterly_data keys and `(company, target, source, signal)` contract
keys between `git show HEAD:<path>` and the working tree; re-ADD only what is missing. Two traps
that both produced bad data before the script was fixed:
- match players **by company across the whole chain**, not per-sector, or a deliberately MOVED
  node gets re-created in its old sector (duplicate Keysight);
- but accept a cross-sector match ONLY when the company has exactly one node in HEAD and one now.
  Companies legitimately placed in several sectors (MediaTek, TSMC, NVIDIA) otherwise get one
  node's data copied onto another.

Never trust the session-start `git status` snapshot — HEAD moves mid-session when another job
commits. See [[feedback_transcript_command]], [[feedback_no_auto_commit]].
