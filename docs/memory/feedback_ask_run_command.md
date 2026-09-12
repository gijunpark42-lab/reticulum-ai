---
name: feedback-ask-run-command
description: "`ask 실행` / `ask up` = run `node local-ask/up.mjs` (runner + Cloudflare quick tunnel + Vercel LOCAL_ASK_URL + redeploy + live check); `ask 종료` = down.mjs. User wants the live site on Opus max via Claude Code (no API key), no Gemini verification, model+effort on every answer, KO/EN toggle, follow-up conversation (2026-09-07)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: def11fd6-fcc0-40a1-8d10-df4001124ba1
  modified: 2026-09-07T09:19:34.137Z
---

When the user says **`ask 실행`** (or `ask up`), run `node local-ask/up.mjs` from the repo root and
report its output: tunnel address, whether Vercel was redeployed, and the live-check line
(`<model> · effort <effort> · your machine · <s>`). **`ask 종료`** / `ask down` → `node local-ask/down.mjs`.
Never print `ASK_SHARED_SECRET` (in `local-ask/.env`, git-ignored, and on Vercel — the user set it there).

**Why:** the user (2026-09-07) said Gemini is not needed as a target ("제미나이는 걍 필요없고"); they want
the website to answer with Opus at max effort through their Claude Code subscription whenever they
open VS Code and say the phrase, without touching Vercel by hand. A quick tunnel's address changes on
every start, which is why `up.mjs` rewrites `LOCAL_ASK_URL` and redeploys (≈1 min); a Tailscale Funnel
would make the address stable (needs their login once) — offer it if the redeploy step annoys them.

**How to apply:** do not spend effort on Gemini-side verification unless asked; keep the fallback
working. Every answer must show model id + effort (runner reports `model_id` from the CLI's usage
report, e.g. `claude-opus-5`, plus `effort`); the Ask tab has an English / 한국어 toggle (`lang` in
the request) and sends the earlier turns (`history`, ≤4 turns, answers ≤2,000 chars) so follow-ups
work. The user plans to mix other models later — keep the badge and protocol model-agnostic.
Related: [[ask-v2-local-runner]], [[feedback_no_auto_commit]].
