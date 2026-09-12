---
name: project-location
description: ALL code projects live under C:\Projects (moved out of OneDrive 2026-09-10); never create or copy projects into OneDrive
metadata:
  type: project
---

On 2026-09-10 the whole repo was moved from `C:\Users\calif\Desktop\earnings-ai` to
`C:\Users\calif\Desktop\earnings-ai` (OneDrive storage was full). The OneDrive copy was deleted.

**Why:** OneDrive quota; also gigabyte audio/video files should never live in the repo (see tw.py AUDIO_DIR = ~/tw_audio).
**How to apply:** always work in `C:\Users\calif\Desktop\earnings-ai`. A stale June-2026 clone sits at `C:\Users\calif\Desktop\earnings-ai_old-2026-06`
(kept only as a fallback; safe to delete). A leftover 2.5GB partial download `guc_full.mp4` was parked in `~/tw_audio/holding/`.
Related: [[python-runtime]], [[transcript-sourcing]].

Also moved out of OneDrive the same day: Bioinformatics, EECS 126, SKHYNIX, Spactrum42, Trading -> `C:\Projects\<name>`.
**Rule (user request 2026-09-10):** anything new that gets worked on must NOT sync to OneDrive. Put every new project, clone, download
or scratch folder under `C:\Projects\` (or `~/tw_audio` for media), never under `C:\Users\calif\OneDrive\...` (Desktop/Documents are OneDrive-backed).
