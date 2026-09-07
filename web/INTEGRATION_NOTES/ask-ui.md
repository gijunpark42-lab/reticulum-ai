# Ask the Graph — browser side of the two-step flow (agent: ask-ui)

## Files touched (nothing else)

| File | Change |
|---|---|
| `web/src/components/AskGraph.tsx` | New `ask()` flow (rewrite → union retrieval → answer), phase line with counter, footer badge, match-row query line, renderer additions, setup-notice line. |
| `web/src/components/AskGraph.css` | +34 lines. New classes (all `.ask-`): `.ask-match .ask-queries`, `.ask-phase` + `@keyframes ask-pulse`, `.ask-hint`, `.ask-a ol`, `.ask-section`, `.ask-setup p`. Tokens only; no existing rule changed. |
| `web/src/lib/retrieval.ts` | Append-only (+80 lines): `retrieveUnion` plus a private `unionOf` and three constants. No existing function, constant, scoring rule or comment changed — the header's "Public API" list therefore does not mention `retrieveUnion` yet. |
| `web/INTEGRATION_NOTES/ask-ui.md` | This file. |

Imports from the frozen module: `guessIntent`, `normalizeIntent`, `LOCAL_MODEL_ID` from `@/lib/askPrompt.mjs`. `Intent` is declared locally (`"lookup" | "compare" | "rank" | "timeline"`) because the `.mjs` only has a JSDoc typedef.

## `retrieveUnion`

```ts
export function retrieveUnion(queries: string[], nodes: VizNode[], links: VizLink[])
  : RetrievalResult & { queries: string[] }
```
* `queries[0]` = the original question, run with `DEFAULT_K` (40); every other entry runs with `UNION_K = 15`.
* Order: all of the original's snippets first (their order kept), then each rewrite's new ones in query order.
* Dedupe key: `` `${kind}|${company}|${target ?? ""}|${label}|${text}` ``.
* Caps: `UNION_MAX_SNIPPETS = 50`, `UNION_MAX_CHARS = 18_000` of `text` (route accepts 60 / 20,000). A snippet that no longer fits is skipped and the next tried (same idiom as `retrieveWithMeta`).
* `companies` / `chains` / `topics` / `terms`: unique unions, original's first. `queries`: the strings actually searched — blank rewrites and case-insensitive repeats (incl. a repeat of the original) are dropped.
* Pure; the only state it touches is `retrieveWithMeta`'s existing index cache.

## `ask()` flow

1. Turn created immediately: `status "loading"`, `phase "rewriting"`, `meta = retrieveWithMeta(question)` so the match row shows at once; history capped at 5; `busy = true`; one fresh `AbortController` per turn.
2. `POST /api/ask/rewrite {question}` with `AbortSignal.any([turnSignal, AbortSignal.timeout(8000)])` (timeout alone where `AbortSignal.any` is missing). `rewriteQuestion()` never throws: any non-200, network error, timeout, abort or malformed body → `{ queries: [], intent: guessIntent(question) }`. A 200 body is validated (strings only, ≤ 4, `normalizeIntent`). After it returns, `ctrl.signal.aborted` is checked so a cancelled turn stops here.
3. `meta = retrieveUnion([question, ...queries])`; turn patched with `meta`, `intent`, `queries` (rewrites actually searched), `phase "reading"`.
4. Zero snippets → the existing local no-match message; no request to `/api/ask`.
5. `phase "thinking"` (+ `thinkingSince`), `POST /api/ask {question, snippets, intent}`, NDJSON consumed as before; `done` now also stores `engine`, `latency_ms → latencyMs`, `citations`.

`finally` clears the controller ref and `busy` on every path (abort during rewrite, no-match return, HTTP error, AbortError, success). Leaving the tab still aborts via the existing unmount effect; Clear aborts and drops the turns.

## How each HTTP / NDJSON case is treated

| Case | UI |
|---|---|
| rewrite: non-200 (400 / 429 / 503 no_api_key), network error, > 8 s, bad JSON | silently continue with the original question + guessed intent; no error shown, no setup notice |
| `/api/ask` 503 `{code:"no_api_key"}` | setup notice (now with the local-runner line) + the `error` text on the turn |
| `/api/ask` 503 `{code:"busy"}`, 400, 413, 429, 502, 504 | `error` text on the turn (`Request failed (N)` if the body has none) |
| `{"type":"text"}` | appended; status `streaming` (one big line from the local engine works the same) |
| `{"type":"done"}` | status `done`; `model`, `engine`, `latency_ms`, `citations`, `usage`, `stop_reason` stored |
| `{"type":"error"}` | keeps any text already shown; hard error only if none arrived |
| unknown `type` | ignored (a keep-alive line such as `{"type":"ping"}` would be safe) |
| stream ends without `done` | counted as finished (no badge) |

## What the user sees

* Phase line: "Rewriting the question…" → "Reading the graph…" → "Thinking… 12 s" (1 s interval, cleared on done / error / unmount; the seconds are `aria-hidden` so the `aria-live` thread announces the phase once, not every second). After 15 s of thinking: "The local engine (Opus, max effort) can take up to a minute." Send button still says "Thinking…".
* Match row, second line when rewrites exist: `intent: rank · searched: <q1> · <q2>`.
* Footer: `claude-code-local (your machine)` when `engine === "local"` (model falls back to `LOCAL_MODEL_ID`), else `<model> (Gemini | Groq | Anthropic | OpenAI-compatible | <raw engine>)`; `· 23.4 s` from `latency_ms`; token counts only when > 0; max_tokens / refusal notes kept.
* Answer: consecutive `1.` / `2)` lines → one `<ol start=n>`; `Best answer:` / `Evidence:` / `Gaps:` (plain, `**Label:**` or `**Label**:`) at the start of a paragraph or list item → `<b class="ask-section">`; bullets, bold and `[n]` chips unchanged and still work inside list items. "1.6T …" and "100. …" stay paragraphs.

## Verified

* `cd web && npx tsc --noEmit --incremental false` → 0 errors, run twice: right after my edits and again against the tree with the other agents' new route files present (baseline before my edits was also 0).
* `retrieveUnion` compiled with `ts.transpileModule` and run on the real `graph/merged_graph.json` (312 nodes, 1,258 edges): "Who supplies HBM4 for NVIDIA Vera Rubin?" + 2 rewrites → 36 → 46 snippets, 17,542 chars, original's snippets first and identical, no duplicate keys, added snippets all come from the k=15 runs, blank / repeated queries dropped, meta unions keep the original's order; `[q]` alone equals `retrieveWithMeta(q)`; `[]` → empty result. Capex question: 21 → 30 snippets.
* `AnswerBody` rendered with `react-dom/server`: section labels in `<p>` and inside `<ol>` items, `start` attribute, two-digit numbers, look-alikes left as paragraphs, alternating ul/ol, chips inside list items (9 of 9), headings stripped, invalid `[42]` left as text, streaming caret.
* `rewriteQuestion` with mocked `fetch`: 503, 429, network throw, invalid JSON, good body, odd body (→ `lookup`), missing intent (→ guess), turn abort mid-call (immediate fallback), and the timeout (fallback after 8,000 ms). It never threw.

## Not verified (needs the integrator's end-to-end run)

* No `next dev` / `next build`: real streaming from either engine, the phase counter hook (needs a live DOM), and webpack bundling of the `.mjs` import in a client component (`tsc` resolves it; webpack should too).
* Browsers without `AbortSignal.any` (Safari < 17.4): reasoned, not run. There, Clear during the rewrite step keeps `busy` until the rewrite returns or times out (≤ 8 s); the turn itself is still dropped correctly.
* `next lint` was not run.

## Wishes for the routes / shared module

* `/api/ask`: send `engine` and `latency_ms` on every `done` line — without them the badge degrades to the bare model name. Zero `usage` is fine.
* `/api/ask/rewrite`: a fast 200 with `queries: []` when its model is unavailable is equivalent to a 503 for the UI; either is fine, but keep it under 8 s or the step is skipped.
* Local engine: a periodic `{"type":"ping"}` line during the long silence would defeat proxy idle timeouts; the UI already ignores unknown types.
* `askPrompt.mjs`: a `.d.ts` (or a TS twin) exporting `Intent` would let the UI drop its local copy of the union.
* `retrieval.ts`: add `retrieveUnion` to the header's "Public API" comment when the freeze lifts.
* `citations` from `done` are stored on the turn but not rendered — could drive a "cited 4 of 46" note on the context summary.
* The "reading" phase is on screen for ~0 ms (retrieval is synchronous, React batches the two patches); harmless, kept for fidelity to the spec.
