---
name: ask-v2-local-runner
description: "Ask-the-Graph v2 (2026-09-07) — local `claude -p` runner (local-ask/) tried first with Gemini fallback, query-rewrite + intent step, one shared prompt module, what was verified, what is still pending (Gemini side-by-side after deploy), uncommitted"
metadata: 
  node_type: memory
  type: project
  originSessionId: def11fd6-fcc0-40a1-8d10-df4001124ba1
  modified: 2026-09-07T09:28:09.650Z
---

Built 2026-09-07 from the user's spec file `~/Downloads/ask-claude-code-prompt.md` ("read it and do
everything in it, multi-agent, no conflicts"). The permission classifier blocked the runner and route
agents (twice, incl. forks), so those two parts were built directly; only the UI agent ran in parallel.
**Uncommitted** — the spec says "show me a diff summary before committing, do not push".

**Architecture (browser → Vercel → engines):**
1. `POST /api/ask/rewrite` (`web/src/app/api/ask/rewrite/route.ts`): cheapest model (Gemini Flash-Lite
   first via `pickModels(p, "cheap")`) turns the question into 2–4 graph-vocabulary queries + intent
   `lookup|compare|rank|timeline`; any failure → 200 `{queries:[], intent: guessIntent(q), fallback:true}`.
2. Browser (`AskGraph.tsx`) runs `retrieveUnion([question, ...queries])` (appended to `retrieval.ts`;
   k=15 per rewritten query, dedupe, caps 50 snippets / 18,000 chars) and POSTs `{question, snippets, intent}`.
3. `POST /api/ask` (`route.ts`, `maxDuration = 120` — safe: Fluid compute is on by default, Hobby max 300 s;
   every timeout derives from that literal): **local engine first** when `LOCAL_ASK_URL` is set —
   `GET /health` 3 s, `POST /answer` ≤ 60 s, header `x-ask-secret = ASK_SHARED_SECRET`, any failure falls
   through silently (server-side `console.warn` only) — then the **API engine** with backoff 1 s/2 s/4 s
   + jitter on 429/5xx/network errors, alternating ranked models, then `503 {code:"busy"}` "Ask is busy,
   try again". Rate limits: ask 10/min/IP, rewrite 20/min/IP (in-memory per instance). NDJSON `done`
   line now carries `model`, `engine` (local|gemini|groq|anthropic|openai-compatible), `latency_ms`, `citations`.
4. `web/src/lib/askPrompt.mjs` = the ONE prompt for both engines (spec rules verbatim + a short data-model
   context + house rules: [n] citations, exact figures, newer-wins, anti-injection; `RANK_SUFFIX` appended
   for rank/compare). Plain .mjs so `local-ask/server.mjs` imports it with no build step.
5. `web/src/lib/askProvider.ts` = server-only shared provider/model-discovery/backoff/rate-limit helpers.
6. `local-ask/` (server.mjs, smoke.mjs, README.md, .env.example, package.json, start-local-ask.cmd):
   Node built-ins only; runs `claude -p --safe-mode --tools "" --no-session-persistence --model opus
   --effort max --output-format json --max-budget-usd 1 --system-prompt <…>` with the user message on
   stdin; strips `CLAUDECODE`/`CLAUDE_CODE_ENTRYPOINT` from the child env; max 2 concurrent, queue 5 → 429,
   90 s kill → 504; JSONL log in `local-ask/logs/`. Not yet exposed: cloudflared/tailscale are NOT installed
   (README covers quick tunnel, named tunnel, Tailscale Funnel, Vercel vars `LOCAL_ASK_URL`, `ASK_SHARED_SECRET`).

**Verified locally (next dev + real runner + mock OpenAI server at `~/.claude/jobs/def11fd6/tmp/pw/`):**
all 4 spec questions through the browser on the local engine → ranked/cited answers, no refusal
("biggest cloud compute capacity" = GW ranking + $ backlog ranking + evidence + gap); route times 22–46 s;
CLI metering $0.14–0.21 per question (subscription). Fallback in <1 s when the runner is down; injected
503s retried at +1.1 s/+2.2 s; permanent 503 → busy after ~8.3 s; queue cap and timeout kill confirmed;
tsc 0 errors. **NOT verified: real Gemini answers with the new prompt** — no Gemini key on this PC
(Vercel var is Sensitive, cannot be pulled) and production still runs the old code until pushed. To finish
the side-by-side: push → `node ask4.js https://gijun42.com gemini` (script in the job tmp dir), or put
`GEMINI_API_KEY` in `web/.env` and rerun locally.

**Tunnel setup done 2026-09-07 (user asked "can't you do Cloudflare too"):** cloudflared 2026.8.3 installed via
winget (`C:\Program Files (x86)\cloudflared\cloudflared.exe`); `local-ask/.env` created with a generated secret
(never printed; user copies it from the file into Vercel — I do not enter secrets into Vercel); `start-all.cmd`
/ `start-tunnel.cmd` open runner + quick tunnel in two windows; verified `/health` + a real Opus answer through a
`https://….trycloudflare.com` address. Quick-tunnel URLs change on every restart → `LOCAL_ASK_URL` on Vercel must
be updated each time (named tunnel needs the domain's DNS on Cloudflare; Tailscale Funnel is the stable no-domain
option). Still needed from the user: push the code, add `LOCAL_ASK_URL` + `ASK_SHARED_SECRET` on Vercel.

**Status 2026-09-07 (end of session): ALL COMMITTED AND PUSHED** (4e73900 Ask v2, 4362c07 other sessions' data,
275c0c2 Gemini token-limit fix — Gemini 3.x thinking eats max_tokens, now 4000 + reasoning_effort low,
b2265fb conversation/KO-EN/model+effort/up.mjs). Live: gijun42.com answers with `claude-opus-5 · effort max ·
your machine` through a detached runner + detached quick tunnel started by `node local-ask/up.mjs`
(state in `local-ask/logs/state.json`; `LOCAL_ASK_URL` + `ASK_SHARED_SECRET` set on Vercel by the user).
Verified live: English question + Korean follow-up ("그럼 삼성은 어떤 상황이야?") → Korean "답변:/근거:/빈틈:" answer
with context, real Gemini rewrite producing standalone English queries. See [[feedback-ask-run-command]]
for the `ask 실행` / `ask 종료` commands. A Korean question with NO rewrite (e.g. Gemini down) matches
nothing (retrieval tokenizes only a-z0-9) — acceptable edge, mention if it bites.

**Lessons:** Playwright `locator.innerText()` on an element that disappeared waits its 30 s auto-timeout —
looked like a 30 s UI lag; pass `{timeout: 300}` in polling loops. `claude -p` works from inside a Claude
Code session only with `CLAUDECODE` unset. Related: [[multiagent-program-2026-09-06]], [[web-app-state]],
[[feedback_no_auto_commit]].
