# AI Supply Chain — Web (Next.js / Vercel)

A Next.js rewrite of the Streamlit app in the repo root, built to deploy on Vercel.
It reads the same curated JSON (`graph/`, `chains/`, `reports/`, `timelines/`,
`company_metrics.json`, `static/logos/`) — nothing in the Python project is modified.

## How data flows

`scripts/sync-data.mjs` runs automatically before `dev` and `build` (npm `predev`/`prebuild`
hooks). It copies + bundles the repo-root JSON and logos into `public/data` and `public/logos`
so the app can serve them statically.

Those synced folders ARE committed to git (not ignored) so the Vercel deploy is
**self-contained**: Vercel's build root is `web/` and does not include the repo-root data
files, so the app ships its own copy under `public/`. The sync step is tolerant — if the
repo-root sources aren't present (as on Vercel), it leaves the committed snapshot in place.
**After editing the curated data at the repo root, run `npm run sync` and commit `web/public`.**

## Local development

```bash
cd web
npm install
npm run dev      # http://localhost:3000  (runs the data sync first)
```

## Deploy on Vercel

1. Import the GitHub repo into Vercel.
2. **Set Root Directory = `web`** (critical — otherwise Vercel sees the repo-root `main.py`
   and tries to build it as a Python project, which fails).
3. Framework preset auto-detects as **Next.js** once the root directory is `web`.
4. Make sure Vercel's **Production Branch** is the branch that contains `web/` (this app lives
   on `main` once merged; otherwise point it at the feature branch).
5. Deploy. Data ships inside `web/public` (self-contained), so no repo-root access is needed.

## Status of the port

- ✅ 3D force graph (react-force-graph-3d) with logo overlays, filters, search-to-focus
- ✅ Node detail panel: meta, badges, layers/domains/chains, products, timeline, signals, deal board
- ✅ Stock report renderer (structured reports/*.json)
- ✅ US live price chart via TradingView widget (client-side)
- ✅ Screener (sortable, filterable) and Timelines (category tabs)
- 🚧 Chain 2D SVG layer map — interim selector in place, full SVG port next
- 🚧 Non-US live quotes — needs `/api/quote` serverless route (Yahoo proxy); US works today
- 🚧 Quant tab (only if `quant/results.json` exists)
