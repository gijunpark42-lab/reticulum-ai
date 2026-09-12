---
name: feedback-report-recommend-next
description: "After finishing a report:<company>, always recommend one not-yet-reported company as a next pick"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 28d4252c-586e-4344-be4f-e57c5a028861
---

After completing each `report:<company>` task (the report is written, validated, and copied to `reports/`), ALWAYS end the turn by recommending ONE company that does not yet have a report in `reports/`. The user requested this standing behavior on 2026-06-14.

**Why:** The user is methodically building out the supply-chain coverage and wants a steady, guided path through the ~230 still-uncovered companies in `company_metadata.json` rather than choosing each next ticker cold.

**How to apply:**
- Compute the candidate pool = `company_metadata.json` keys minus existing `reports/*.json` filenames (skip `_`-prefixed files). A quick Python diff prints it.
- Pick ONE high-value, thematically adjacent node to what was just covered (e.g. after a memory/HBM report → test equipment like Teradyne; after power components → the Vertiv power/cooling systems capstone). Prefer nodes that (a) matter to the AI graph and (b) ideally already have a local source in `transcripts/` for easier sourcing.
- Give a one-line rationale for the pick; optionally name 1–2 alternatives across the live themes so the user can steer. Keep it to one PRIMARY recommendation (the user said "하나 추천" = recommend one).
- This is additive to the report workflow in [[feedback_report_command]]; it does not change how the report itself is produced.
