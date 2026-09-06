# Ask the Graph — integration notes (agent: ask-graph)

## Status

**DONE (complete, type-checked, unit-tested where runnable):**
* `web/src/lib/retrieval.ts` — index + BM25 ranking + boosts + `suggestQuestions`; tested on the real graph.
* `web/src/app/api/ask/route.ts` — POST route, validation, rate limit, 503 without key, streaming NDJSON; SSE parser / validator / prompt builder unit-tested.
* `web/src/components/AskGraph.tsx` + `AskGraph.css` — full UI (input, chips, streamed answer, `[n]` citation chips, context list, setup notice, last-5 history).
* `cd web && npx tsc --noEmit --incremental false` → 0 errors for the whole project.
* No dependency added; no shared file edited.

**NOT DONE (by design / needs the integrator):**
* The tab is **not mounted** — apply the three `page.tsx` edits below (shared file).
* `ANTHROPIC_API_KEY` is not set anywhere — add it in Vercel (steps below).
* The dev server was never started (forbidden for this agent): the first live
  smoke test (open Ask → click a chip) is still to be done after mounting.
* Follow-up questions do not carry conversation history to the model (see Caveats).

A new **Ask** tab: type a question in plain English → the browser picks the best
stored signals / contracts from the graph it already holds → a server route asks
Claude to answer **only from those snippets**, citing each fact as `[n]` with its
source label, and saying plainly when the graph does not contain the answer.
No outside knowledge is used; the API key never reaches the browser; every other
tab keeps working when no key is configured.

## Files (all NEW — nothing else in the repo was touched)

| File | Role |
|---|---|
| `web/src/lib/retrieval.ts` | Client-side search (BM25 + company / chain / topic / recency boosts). `retrieve()`, `retrieveWithMeta()`, `suggestQuestions()`, `tokenize()`. |
| `web/src/app/api/ask/route.ts` | `POST /api/ask` (Node runtime). Validates, rate-limits, calls the Anthropic Messages API with plain `fetch`, streams the answer back as NDJSON. |
| `web/src/components/AskGraph.tsx` | The tab: input, suggested-question chips, streamed answer with `[n]` citation chips, "Context used", setup notice, last-5 history (component state only). |
| `web/src/components/AskGraph.css` | Styles, all `.ask-*`, `--ap-*` tokens only, responsive at 860px / 400px. Imported by the component. |
| `web/INTEGRATION_NOTES/ask-graph.md` | This file. |

**No new dependency.** `package.json` / `package-lock.json` are untouched — the
Messages API is called with the built-in `fetch`, exactly the raw-HTTP shape from
the `claude-api` skill (`POST https://api.anthropic.com/v1/messages`, headers
`x-api-key` + `anthropic-version: 2023-06-01`, `"stream": true`).

## Mount it in `web/src/app/page.tsx` (three exact edits)

1. Add the import next to the other components:
   ```tsx
   import AskGraph from "@/components/AskGraph";
   ```
2. Add the tab name (last, so the existing order is unchanged):
   ```tsx
   const TABS = ["Graph", "Chain 2D", "Generations", "Timelines", "Screener", "Capex", "Coverage", "Ask"] as const;
   ```
3. Render it after the Coverage line (inside `<main>`, same pattern as the other tabs):
   ```tsx
   {viz && tab === "Ask" && (
     <AskGraph nodes={viz.nodes} links={viz.links} onOpen={openNode} />
   )}
   ```

That is all. `openNode` already exists in page.tsx (it opens the NodePanel by
company id). No changes are needed to `globals.css`, `types.ts`, `data.ts`,
`next.config.mjs` or `vercel.json`. The mobile tab strip already scrolls, so an
8th tab fits.

## Server-side API key (Vercel)

1. Create a key at console.anthropic.com → API Keys.
2. Vercel → the project → **Settings → Environment Variables** → add
   `ANTHROPIC_API_KEY` = `sk-ant-…` for **Production** and **Preview**
   (Development too if you use `vercel env pull`).
3. **Deployments → Redeploy** the latest deployment (env vars are baked in at
   deploy time).
4. Locally: `web/.env` with `ANTHROPIC_API_KEY=sk-ant-…`, then restart
   `npm run dev`. `web/.env` is already git-ignored (root `.gitignore` rule
   `.env`; verified with `git check-ignore`). **`web/.env.local` is NOT ignored
   today** — if you prefer the `.env.local` convention, first add `.env*.local`
   to `web/.gitignore` (shared file, deliberately not edited by this agent).

Without the key the route answers `503 {"error":"ANTHROPIC_API_KEY not configured","code":"no_api_key"}`
and the tab shows a friendly setup notice with these same steps. Nothing else
in the app depends on the key.

Optional: set a monthly spend limit on the Anthropic Console for the key — that
is the real cost cap (the route's rate limit is per serverless instance, see caveats).

## Model and cost

* **Model:** `claude-sonnet-5` (Sonnet-class as requested; the `claude-api` skill
  maps "sonnet" to this current-generation id). `max_tokens: 1000`, adaptive
  thinking at `effort: "low"` (a brief check of the snippets, cheap), no
  `temperature` (sampling params are rejected on this model family).
* **Pricing** (skill table): $2 / $10 per million input / output tokens.
* **Per question:** system prompt ≈ 2.0k chars (~0.5k tokens) + up to 12k chars
  of snippets and their headers (~3.5–4k tokens) + the question → **≈ 4.5k input
  tokens ≈ $0.009**; answer + brief thinking 300–800 output tokens → **$0.003–0.008**.
  **≈ 1–2 cents per question; ~$12–17 per 1,000 questions.**
* Worst case under the route's rate limit (20 / 10 min / IP): ≈ $0.03–0.04 per
  minute per abusive IP per instance.
* Prompt caching is not used: the system prompt is below the minimum cacheable
  prefix and the snippets change with every question.

## How it works

**Retrieval (browser, `lib/retrieval.ts`).** Every `quarterly_data` entry
("signal") and every edge `contract` becomes one document (~1,990 + ~480 in the
current graph; duplicate contracts stored in two chain files are collapsed).
Contracts are read from `node.outgoing` — `buildViz()` truncates
`VizLink.contracts` to 3 per edge, `outgoing` has them all. Index build ≈ 110 ms,
memoised by the identity of the `nodes`/`links` arrays (page.tsx memoises `viz`,
so it happens once). A question is tokenised (keeps `1.6T`, `HBM4`, `NVL72`),
stop-worded and lightly stemmed, then scored with BM25 (k1 1.2, b 0.75) plus:

* named company (full name, distinctive word such as "Hynix", alias such as
  "AWS", parenthesised name such as "Showa Denko", or an UPPERCASE ticker) →
  its own facts ×3 (+ a floor so "what did X say recently" works with no word
  overlap), deals where it is the counterparty ×2, and its best 6 facts (3 for
  who-supplies-whom questions) are always reserved in the context;
* generation / chain words (Rubin, Blackwell, Helios, Trainium3, TPU v8, …) →
  facts from that chain ×1.5; topic words (HBM, CoWoS, CPO, optical, power,
  transformer, NAND, foundry, sold out, capex, guidance, backlog …) → tagged
  facts ×1.5; a period in the question (`Q2 FY2026`) matching the source label ×1.5;
* mild recency bump (newest label ×1.2 → ×1.0 at 18 months, measured from the
  newest label in the graph, not today);
* diversity: one company holds at most 8 slots (4 for relationship questions).

Output: top 40 max, hard cap 12,000 characters of snippet text (typically 16–37
snippets), each `{kind, company, target?, chain, label, date, text, topics}`.
`suggestQuestions(nodes)` builds 8 chips from the data and keeps only questions
the graph can actually answer (currently: HBM4 for Vera Rubin, sold out /
allocation, TSMC on advanced packaging, NVIDIA on supply tightness, hyperscaler
capex, CPO timing, 1.6T optics, power/cooling backlog).

**Route (`/api/ask`).** Order of checks: rate limit (20 per 10 min per IP,
in-memory) → body size (96 KB) → JSON shape (question ≤ 500 chars, ≤ 60
snippets, ≤ 2,000 chars each, ≤ 20,000 total, typed fields) → key present →
Messages API with `stream: true` and a 50 s `AbortSignal.timeout`
(`maxDuration = 60`). Upstream non-2xx becomes clean JSON: 401/403 → 502 "check
ANTHROPIC_API_KEY", 429 → 429, 5xx/529 → 503, 404 → 502 "update MODEL in
route.ts". The SSE events are re-emitted as NDJSON lines: `{"type":"text"}`
fragments, one `{"type":"done", usage, stop_reason, model}`, or
`{"type":"error"}`. The system prompt forbids outside knowledge, requires `[n]`
citations plus the source label, asks for exact figures, tells the model to say
"The graph does not contain…" and suggest what to enrich, and treats snippet
text as data (prompt-injection guard).

**Component.** Newest answer on top, max 5 turns kept in state (nothing
persisted, nothing sent but question + snippets). `[n]` renders as a chip; click
→ the snippet card (kind, company → NodePanel via `onOpen`, target, chain,
label, date, text). "Context used" lists every snippet sent. A question that
matches nothing is answered locally (no API call). Errors: 503 no-key → setup
notice; 429 → limit message; stream interruption keeps the partial text.

## How it was verified

* `cd web && npx tsc --noEmit --incremental false` → **0 errors** (baseline was
  also 0, so nothing of mine regressed the project).
* Retrieval was compiled on its own and run against the real
  `graph/merged_graph.json` (read-only; 312 nodes, 1,250 edges) with ~25
  questions. Spot results: "Who supplies HBM4 for NVIDIA Vera Rubin?" → Micron
  → NVIDIA HBM4 contracts, Samsung → NVIDIA HBM4, SK Hynix HBM4 signals, NVIDIA
  capped at 4 of 37 snippets; "What's the latest on Vertiv backlog?" → 6 Vertiv
  facts incl. the raised-guidance / backlog entry; "What did Hynix report in Q2
  FY2026?" → SK Hynix entries labelled `Q2 FY2026 (08-14-2026)` first; "MU HBM
  share" resolves the ticker; "AT&S substrate", "Showa Denko", "AWS" resolve;
  "asdfgh" → 0 snippets (answered locally); "Trainium3 suppliers" → Amazon and
  Arm → Amazon facts from the `aws_trainium3` chain first. Queries take 2–12 ms.
* The route's pure functions were extracted from the compiled JS and unit-tested:
  the SSE → NDJSON parser at 100 KB / 5-byte / **1-byte** chunking (a multibyte
  character split across chunks included), CRLF line endings, an upstream
  `error` event, and a socket that dies mid-stream; `parseBody` with 11 valid /
  invalid bodies (all limits enforced); the numbered prompt layout.
* **Not run: the dev server** (shared `.next`, forbidden for this task). First
  live check after mounting: `npm run dev`, open **Ask**, click a chip — without
  a key the setup notice must appear; with a key, text should stream in with
  `[n]` chips that open snippet cards, and the company names should open the
  NodePanel.

## Caveats

* The rate limit is in-memory: per warm serverless instance, reset on cold
  start. It stops runaway scripts, not a determined abuser — the Anthropic
  spend limit is the real cap.
* Each question is independent: the last-5 history is UI only and is **not**
  sent to the model, so follow-ups must be self-contained ("and Samsung?" will
  not work). Sending the previous Q&A would be a small change in
  `AskGraph.tsx` + `route.ts` if wanted.
* Retrieval is keyword-based. Paraphrases that share no word with the stored
  text can miss ("memory chips" vs "HBM"); the `VOCAB` and `EXPAND` tables in
  `retrieval.ts` are the place to add synonyms. Company detection needs the
  node's name, a distinctive word of it, an entry in `ALIASES`, or an UPPERCASE
  ticker (`NVDA`, `MU`) — lower-case tickers are ignored on purpose ("on", "arm").
* By the owner's rule only transcript-grounded entries are searchable; edges
  that carry **zero contracts** (curated structure) are not in the index, so
  "who supplies X" is answered from contracts and signals only. If curated
  structure should count, add a third document kind in `buildIndex()` and label
  it clearly as structure, not a source.
* `retrieval.ts` relies on `node.outgoing` carrying full contract lists (it
  falls back to `links` only if `outgoing` is missing). Keep that in mind if
  `data.ts` changes.
* The model id is one constant (`MODEL` in `route.ts`); a 404 from the API is
  reported with that hint.
* Streaming is NDJSON over a plain `Response`; if a proxy buffers, the answer
  arrives in one piece but still works. `maxDuration = 60` is within every
  Vercel plan.
* `next lint` was not run (the project ignores lint during builds); no new
  lint-sensitive patterns were introduced.
