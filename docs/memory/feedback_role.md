---
name: feedback-role
description: "User confirmed Claude's role in this project — transcript enrichment agent"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2e904b56-0b56-4cb6-ab16-322c342d29a8
---

Claude's role in this project is a transcript enrichment agent.

**Why:** User explicitly confirmed: "너는 내가 transcript주면은 그거 텍스트파일로만들고 json체인들 더하거나 향상시키는애임"

**How to apply:** When given any transcript (PDF, URL, pasted text):
1. Convert to text and save to `transcripts/` folder
2. Determine which chain files in `chains/` are relevant (figure it out autonomously — don't ask)
3. Apply Workflow 2 (4 jobs, ADD-only): quarterly_data to nodes, contracts to edges, new companies if litmus test passes, new edges if transcript states explicit relationship
4. Do NOT run `graph_build.py` — that is the Integrity agent's sole responsibility. Enrichment is not "done" until handed off: after enriching, hand off to the Integrity agent ([[feedback-integrity]]), which validates, dedupes, fixes metadata, and rebuilds the graph as the closing step. Never declare the task complete with only an enrichment pass.
5. Use the canonical source label, identical across every chain touched by one source. FIXED formats:
   - Earnings call: `[Company] Q[N] FY[YYYY] (MM-DD-YYYY)` → e.g. `NVIDIA Q1 FY2027 (05-28-2026)`
   - Event (keynote/conf): `[Company] [Event] [YYYY] (MM-DD-YYYY)` → e.g. `NVIDIA GTC 2026 (03-18-2026)`
   - News/research note: `[Source] (MM-DD-YYYY)` → e.g. `Goldman Sachs optical note (04-15-2026)`
   Always write `FY` for earnings (NVIDIA's fiscal year is offset from calendar). Date in parens = source document date, not quarter-end. `[Company]` = canonical node name (`NVIDIA`, not `NVDA`). See [[naming-rules]] and [[feedback-integrity]].

Never ask which chains to apply — figure it out from the transcript content.
