---
name: ask-server
description: Start or stop the local Opus engine behind the live Ask tab. Use when the user says "ask 실행", "ask up", "ask 종료" or "ask down". Runs local-ask/up.mjs or down.mjs (runner + Cloudflare tunnel + Vercel LOCAL_ASK_URL redeploy + live verification).
---

### Workflow 3 — `ask 실행` (put the local Opus engine behind the live site)

**Trigger: the user says `ask 실행` or `ask up`** (typically right after opening VS Code). Run
`node local-ask/up.mjs` from the repo root and report what it printed: the tunnel address, whether
Vercel was redeployed, and the verification line (model · effort · latency from the live site).
The script starts `local-ask/server.mjs` (the Claude Code CLI: Opus, max effort, no tools — the
user's subscription, no API key) and a Cloudflare quick tunnel, points Vercel's `LOCAL_ASK_URL` at
the tunnel and redeploys the current production build (env vars are baked in at deploy time, ≈1 min),
then asks the live site one question and checks that the answer came from the local engine.
Every step is skipped when already done, so re-running is cheap. **`ask 종료` / `ask down`** →
`node local-ask/down.mjs` (stops runner + tunnel; the site falls back to Gemini by itself).
Details in `local-ask/README.md`. Never print or paste `ASK_SHARED_SECRET` — it lives in
`local-ask/.env` (git-ignored) and on Vercel. The Ask tab: answers carry model + effort, a
Korean/English toggle picks the answer language, follow-up questions send the earlier turns.
