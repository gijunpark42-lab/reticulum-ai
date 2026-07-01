# AI Supply Chain — Web (Next.js / Vercel)

A Next.js rewrite of the Streamlit app in the repo root, built to deploy on Vercel.
It reads the same curated JSON (`graph/`, `chains/`, `reports/`, `timelines/`,
`company_metrics.json`, `static/logos/`) — nothing in the Python project is modified.

## How data flows

`scripts/sync-data.mjs` runs automatically before `dev` and `build` (npm `predev`/`prebuild`
hooks). It copies + bundles the repo-root JSON and logos into `public/data` and `public/logos`
so the app can serve them statically. Those synced folders are gitignored and regenerated on
every build.

## Local development

```bash
cd web
npm install
npm run dev      # http://localhost:3000  (runs the data sync first)
```

## Deploy on Vercel

1. Import the GitHub repo into Vercel.
2. Set **Root Directory** = `web`.
3. Framework preset: **Next.js** (build `npm run build`, output auto-detected).
   The `prebuild` hook syncs data from the repo root (which is present in the Vercel checkout).
4. Deploy.

## Status of the port

- ✅ 3D force graph (react-force-graph-3d) with logo overlays, filters, search-to-focus
- ✅ Node detail panel: meta, badges, layers/domains/chains, products, timeline, signals, deal board
- ✅ Stock report renderer (structured reports/*.json)
- ✅ US live price chart via TradingView widget (client-side)
- ✅ Screener (sortable, filterable) and Timelines (category tabs)
- 🚧 Chain 2D SVG layer map — interim selector in place, full SVG port next
- 🚧 Non-US live quotes — needs `/api/quote` serverless route (Yahoo proxy); US works today
- 🚧 Quant tab (only if `quant/results.json` exists)
