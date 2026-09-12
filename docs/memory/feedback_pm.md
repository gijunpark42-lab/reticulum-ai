---
name: feedback-pm
description: Third agent role — project manager / planner for the Reticulum supply-chain graph
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8057d507-c93b-45cc-8380-a2bea3189aa6
---

**As of 2026-06-08 the user CONSOLIDATED to a SINGLE agent.** One Claude session now performs all work end-to-end: enrichment + integrity + PM. Reason (user): "그냥 에이전트 하나로 니만 쓰자 귀찮다 차피 직렬인데 사공이많으니 산으로간다" — the workflow is serial anyway, so multiple agents + hand-offs were pure overhead.

The three role definitions below are RETIRED as separate agents, but all their RULES still apply — one operator just does them all in sequence:

1. **Enrichment** ([[feedback-role]]) — transcript → text file → ADD-only chain enrichment.
2. **Integrity** ([[feedback-integrity]]) — validate, dedupe, maintain metadata, run `graph_build.py`.
3. **PM / Planner** (this file) — prioritize and track state.

So a normal session: enrich → validate/dedupe/metadata → graph_build, all by you, no hand-off. PM altitude (status, planning) is still useful but you also do the hands-on work now.

**Do NOT commit, and do NOT keep offering to commit.** User handles all git commits themselves ("커밋은 내가 컴 글 때만 할거임"). Already told before: don't push either. Just do the work and leave the working tree changed; the user reviews and commits on their own machine/time.

**A company appearing in only ONE chain is EXPECTED, not a defect.** It just means few transcripts have been given for that domain yet ("체인 하나에만 뜨는 건 transcript 많이 안 줘서 그래"). Do not flag single-chain companies as "weak hubs" needing fixing. Cross-chain hubs grow naturally as more transcripts arrive.

**PM role:** track overall project state, decide what to do next, prioritize, and delegate to the other two agents. The PM does NOT edit chain data or run enrichment/build directly — it owns governance, prioritization, and clear task hand-off briefs.

**PM does NOT inspect or run files either** (no reading chains, no python scripts, no git poking to "ground" an answer). User correction: "너는 매니져야 enrich하는전문으로 하는 애한테 뭐시킬지 프롬프트만주면돼" — the PM's deliverable is the *delegation prompt* the user pastes to the Enrichment or Integrity agent, not hands-on work or file inspection. Keep recommendations at the planning altitude; produce ready-to-paste prompts.

**Why:** User explicitly thinks of the system as "3 agents" and asked that a new session/account know all three. Previously only agents 1 and 2 were in memory; the PM role was only defined at session launch and would be lost.

**How to apply:**
- When launched as PM, give status reports, surface enrichment gaps (unprocessed transcripts), flag data-quality issues, and define what each other agent should do — but don't do their hands-on work.
- Pipeline the PM enforces: **enrich (agent 1) → validate/dedupe/metadata/build (agent 2)**. Enrichment is never "done" until Integrity closes it.
- Open priorities the PM tracks: 12 unprocessed transcripts (biggest value gap), old-format labels needing cleanup to the FIXED standard, and Phase 4 web app (the next agent to add, when the time comes). See [[project-state]].
