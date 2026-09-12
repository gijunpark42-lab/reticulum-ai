---
name: multiagent-program-2026-09-06
description: "2026-09-05/06 eleven-agent UI/accuracy/features program (Exposure tab, Ask-the-Graph, evidence buttons, table/map/panel upgrades, 274-entry accuracy review) — what was built, the conflict rules that worked, and QA lessons (hidden Chrome tab ≠ frozen app; ResizeObserver+padding loop; flex stretch on the phone sheet)"
metadata: 
  node_type: memory
  type: project
  originSessionId: def11fd6-fcc0-40a1-8d10-df4001124ba1
  modified: 2026-09-06T09:43:36.798Z
---

User authorized multi-agent work ("you can use multi agent … enhance UI, practicality, accuracy and
different ideas … don't let them crash each other … full authority, use a lot of tokens"). Ran 11
parallel general-purpose agents + 1 verifier agent, integrated serially. Uncommitted (user commits).

**Built (web/):** SearchBox typeahead (name/ticker/product), NodePanel v2 (Latest-by-slot strip,
topic chips, pagination, "Customers & suppliers on file" from `counterparty` entries, TradingView /
Yahoo / copy-ticker / Transcript buttons, per-entry **EvidenceButton** = verbatim excerpt from the
source file via `evidence.py` → `graph/evidence.json`), Sidebar counts/reset/legend, Screener
(sort/filter/freshness/columns/CSV/ticker export; Exchange column off by default), Timelines (topic
pills, since-filter, group-by-company, curated vs auto badges, inline expand), Capex tooltips/sort/
CSV, Chain 2D path highlight/pin/collapse/tooltips, Graph 3D focus mode (1/2-hop) + legend + fit,
**Exposure tab** (`derive_exposure` in derive.py → `graph/exposure.json`: per-chain "who benefits"
score, concentration facts, generation delta, basket export incl. TradingView symbols), **Ask tab**
(`/api/ask`, client-side BM25 retrieval in `lib/retrieval.ts`, plain fetch; provider chosen by env
var, first match wins: `ASK_BASE_URL`+`ASK_API_KEY` (any OpenAI-compatible) → `GEMINI_API_KEY`
(gemini-2.5-flash, FREE tier ~15 RPM / 1,500 RPD, user's preferred zero-cost option) → `GROQ_API_KEY`
(llama-3.3-70b, free but 8–12K TPM) → `ANTHROPIC_API_KEY` (claude-sonnet-5); `ASK_MODEL` overrides.
503 notice when none is set. The Anthropic key in the repo's `.env` was INVALID on 2026-09-06.
**LIVE with Gemini since 2026-09-06:** user added `GEMINI_API_KEY` (Production) on Vercel project
reticulum-ai (team gijun42); `gemini-2.5-flash` 404s on a fresh key, so the route now lists
`GET {baseUrl}/models` and picks the newest stable Flash (was gemini-3.8-flash) — verified on
gijun42.com with a cited answer. Vercel notes: the `*.vercel.app` deployment/branch URLs are behind
Vercel login protection — test on the production domain **gijun42.com**; `web/` is linked to the
project via the Vercel CLI (logged in as gijunpark42-lab; `vercel env ls --scope gijun42` lists
variable NAMES only); redeploy = push to main (empty commit is fine); a transient Gemini 5xx right
after a deploy is normal — retry once). page.tsx now has 9 tabs
(tab strip wraps). `signals.ts` freshness now counts only the node's OWN labels (`labelIsOwnSource`),
same rule in derive.py's stale check. `graph_build.py` runs `evidence.py` after derive.

**Accuracy:** 274 verifier flags reviewed by 3 agents → 185 keep / 19 set / 67 delete, applied with
the new serial `apply_corrections.py` (locator = company, target, label, signal prefix; proposals in
`patches/corrections/`, receipts in `applied/`). 8 transcripts got `# source label:` headers (77 more
entries resolve); 24 labels have no document on disk (DigiTimes notes, JP IR decks). Within-chain
duplicate entries across same-company cards deduped (20 qd + 1 contract, nand_flash stage-split cards).
verify_graph.py upgraded by a dedicated agent (rounding-aware rescale, Korean units, aliases, companion
docs, English DART supply-contract headers; tests in `utils/test_verify_graph.py`). **Post-rebuild
baseline (2026-09-06): 2,406 entries — 1,791 pass / 471 unchecked / 31 warn / 113 fail** (was 258 fail /
118 warn under the old lenient matcher). Remaining fails: 25 no document on disk, ~59 enricher-computed
growth/margin % (base only in the statement), the rest amounts absent from the doc — next accuracy pass
should start from `python -X utf8 verify_graph.py --fails`.

**Conflict rules that worked (reuse):** disjoint file ownership per agent; shared files frozen
(page.tsx, globals.css, types.ts, data.ts, derive.py, verify_graph.py, package.json) with wishes
written to `web/INTEGRATION_NOTES/<agent>.md`; own CSS file + class prefix per component; nobody
writes chains/ graph/ web/public/; no builds/dev servers/npm install/git state changes for agents;
verification = `npx tsc --noEmit --incremental false`; data edits only via the serial appliers.

**QA lessons:** (1) A Chrome tab that is hidden/minimized stops rAF and CDP screenshots time out —
looks exactly like a frozen renderer; check `document.visibilityState` before debugging. Headless
Playwright (`~/.claude/jobs/<job>/tmp/pw/qa.js`, chromium installed under ms-playwright) is the
reliable way to screenshot every tab at 1400px and 390px. (2) `.cell.clipped { padding-right }` made
CellText's ResizeObserver oscillate — never let a measured class change the box; the padding is now
constant and the measurer is rAF-coalesced with a loop breaker. (3) The phone node-panel sheet used
`align-items: stretch`, which pinned the panel to viewport height so long cards overflowed their
opaque box; now `flex-start` + opaque background, no backdrop blur on ≤860px.
Related: [[graph-cleanup-2026-09-05]], [[web-app-state]], [[feedback_no_auto_commit]].
