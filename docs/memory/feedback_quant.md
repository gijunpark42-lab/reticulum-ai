---
name: feedback-quant-rules
description: "Quant research layer rules — read-only on chains/graph/timelines, Word log per step, earnings calls only"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8057d507-c93b-45cc-8380-a2bea3189aa6
---

Rules for the quant layer (quant/ directory, established 2026-06-09):

1. **Read-only**: quant scripts READ chains/, graph/merged_graph.json, timelines/, company_metadata.json but NEVER modify them. Quant outputs live in quant/ + RESEARCH_LOG.docx only.
2. **Word log per step**: after every quant step, regenerate RESEARCH_LOG.docx (`quant/write_research_log.py` reads quant/results.json). The docx is the living research record (SOXX & SPY tables side by side).
3. **Earnings calls only**: events come only from sources whose label matches `Q\d FY\d{4}` — GTC keynotes and news notes (Goldman, Motley Fool articles) are excluded from the event study (their dates aren't the company's quarterly information moment). They stay in the graph/web. Also OWN calls only — a label on a node counts only if it's that company's own call (label company prefix matches node name).
4. **Methodology ownership**: classification is BINARY and owner-approved per company. Current signal: full_capacity (quant/signal_full_capacity.csv, 17 of 71 flagged, with evidence quotes + owner rulings). v1 keyword taxonomy (7 types) was REJECTED (no SOXX edge, tail-driven) and its files deleted. Entry = t+1 close (user's decision); windows +5/+10/+20 trading days (partial allowed); benchmarks SOXX/SPY/QQQ; p-values not t-stats.
5. **Chains only, never transcripts**: quant classification reads ONLY chain signals (graph/merged_graph.json quarterly_data), never raw transcripts/. Candidates are reviewed in batches of 10 chain files; ambiguous cases get individual allow/deny rulings from the user.
6. **Do nothing unasked**: in quant work, execute only what the user explicitly ordered; propose and ask before anything else.

**GOAL CHANGED 2026-09-09:** the user stated plainly "스터디하는게 아니라 나는 트레이딩 및 투자를 할거야, 스터디는 필요없어" — the quant layer now exists to TRADE and INVEST real money, not to produce a research/portfolio piece. Do not frame work as event studies / p-values for a paper; frame everything as: what signal to trade, when to enter/exit, position size, did it make money. Historical checks are due diligence before betting, not academic output. KIS (한투) API is the planned execution layer (later, user's call on timing).

**Why (original, 2026-06):** the project was positioned as a quant-research internship portfolio piece — the user must own and be able to defend every methodology decision; the chains remain the curated moat, untouched by analysis code. Rules 1-6 above still apply (read-only on chains, user owns methodology, do nothing unasked).

**How to apply:** when extending quant/, never write to chains/ or graph/; always re-run write_research_log.py after results change; consult the user (with proposals) before changing signal_rules.json.

Related: [[project-state]], [[feedback-role]]
