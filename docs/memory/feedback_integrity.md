---
name: feedback-integrity
description: "Integrity agent rules — what to preserve, what can be deleted"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 754574da-aef2-487a-aed3-12e7e3328d19
---

Claude's integrity role: validate chains, maintain metadata, run graph_build.py after updates.

**SOLE OWNER of `graph_build.py`.** No other agent rebuilds the graph. The Enrichment agent ([[feedback-role]]) only edits chain files and hands off; Integrity is the gatekeeper that closes every pipeline: validate → dedupe → fix metadata → `graph_build.py`. This guarantees `merged_graph.json` only ever reflects validated data. The graph is "stale" until Integrity runs — so an enrichment session is not complete until Integrity has closed it.

**Rule: Duplicates CAN be deleted.**
ADD-only principle applies to unique data only. If a node, edge, or quarterly_data entry is a duplicate of one already in the same file, it can and should be removed.

**Why:** User explicitly said "기존노드/엣지/데이터 겹치면은 삭제해도돼" (if existing nodes/edges/data overlap/duplicate, it's okay to delete them).

**How to apply:**
- Duplicate quarterly_data entries (same quarter + same signal in same node) → remove the duplicate
- Duplicate connects_to edges (same source→target with identical relationship) → merge or remove duplicate
- Duplicate company nodes within the same tier → merge data into one, remove the other
- Non-duplicate existing data → never remove (ADD-only still applies)

**Integrity checklist (run on every chain update):**
1. Self-referential edges (company → itself) → remove
2. Duplicate signals in quarterly_data → remove duplicates
3. Duplicate edges in connects_to → remove duplicates
4. Source label must match the canonical format (shared with [[feedback-role]]):
   - Earnings: `[Company] Q[N] FY[YYYY] (MM-DD-YYYY)` (always `FY`, e.g. `NVIDIA Q1 FY2027 (05-28-2026)`)
   - Event: `[Company] [Event] [YYYY] (MM-DD-YYYY)` (e.g. `NVIDIA GTC 2026 (03-18-2026)`)
   - News/research: `[Source] (MM-DD-YYYY)`
   Date = source document date; `[Company]` = canonical node name. Flag any label missing `FY` on an earnings entry.
5. Company names must match canonical names in company_metadata.json
6. All players must have `quarterly_data: []` field
7. Run graph_build.py after all fixes
8. Add missing companies to company_metadata.json
