# ui-tables — integration notes

Agent: `ui-tables` (Screener / Timelines / Capex & Backlog tables). Date: 2026-09-05.

## Files

Created
- `web/src/lib/table.ts` — shared helpers, plain TS (one small React hook at the bottom):
  `parseLabelDate`, `parseIsoDate`, `parseDate`, `isoDate`, `daysSince`,
  `freshnessBucket` (+ `FRESH_DAYS = 45`, `AGING_DAYS = 120`, `FRESHNESS_LABEL`), `formatAge`,
  `compareCells`, `sortRows` (blanks always last, stable), `matchesQuery` (AND over words),
  `toCsv` / `csvField` (RFC 4180, CRLF), `csvFilename`, `copyToClipboard` (navigator.clipboard
  with textarea/execCommand fallback), `downloadCsv` (Blob + `<a download>`, UTF-8 BOM for
  Excel), `readStorage` / `writeStorage` (try/catch localStorage), `useFlash` (momentary
  "Copied ✓" button feedback).
- `web/src/components/Tables.css` — every new style, all classes prefixed `.tb-`. Imported by the
  three components (`import "./Tables.css"`). Uses only `--ap-*` / `--fs-*` tokens plus the
  green/amber/red already used by `lib/signals.ts` badges. Contains its own ≤860 / ≤700 / ≤400px
  rules; the ≤700px block only adapts the NEW pieces (group rows, clamped cells) inside the
  existing card-stack — the card-stack itself in `globals.css` is untouched and still keyed on
  `data-label`, which every cell keeps.
- `web/INTEGRATION_NOTES/ui-tables.md` — this file.

Edited (my files only)
- `web/src/components/Screener.tsx`
- `web/src/components/Timelines.tsx`
- `web/src/components/CapexBacklog.tsx`
- `web/src/components/CellText.tsx`

Not touched: `page.tsx`, `globals.css`, `lib/*` other than the new `table.ts`, all data files,
all Python. No new dependencies.

## page.tsx prop changes needed

**None.** Component signatures are unchanged:
- `<Screener byId={viz.byId} onOpen={openNode} />`
- `<Timelines resolve={resolveCompany} onOpen={openNode} />`
- `<CapexBacklog resolve={resolveCompany} onOpen={openNode} />`

## Changes to shared files requested

**None required.** One thing to be aware of (decision for the owner, not a request):
`lib/signals.ts` marks a graph node `stale` after 180 days (drives the 3D graph dimming), while the
Screener now uses the brief's 45 / 120-day buckets for the "As of" column. Both are documented in
their own file; if you want one number, change `FRESH_DAYS` / `AGING_DAYS` in `lib/table.ts` (the
Screener caption and legend read from those constants).

## What each view now does

### Screener
- Sortable columns (click or Enter/Space on a header; ▲/▼ indicator, `aria-sort`), blanks always
  sort last. Default: As of, newest first.
- Filters: Layer/Domain, Sector, Chain (as before) + text search (matches company, ticker,
  exchange, layer and all five slots; all words must match) + **Hide stale** toggle.
- Freshness from `asof`: fresh ≤45d (green), aging ≤120d (amber), stale >120d (red). The "As of"
  cell shows a colour dot, the date and "22d ago"; the summary line shows counts per bucket for
  the filtered set and how many stale rows are hidden.
- Sticky header (existing `globals.css` rule, kept).
- Column show/hide (`Columns ▾` popover, closes on outside click) with a "Reset to default"; the
  Company column is always on. New optional columns: **Exchange** (on by default) and **Layer**
  (off by default, primary layer/domain display name). Column choices + Hide-stale are remembered
  in `localStorage` under `tb.screener.v1` (loaded after mount → no hydration mismatch).
- Export of the VISIBLE rows, fixed shape regardless of hidden columns: Company, Ticker, Exchange,
  Revenue growth, Guidance, Backlog / B2B, Supply status, Next catalyst, As of.
  `Copy CSV`, `Download CSV` (`screener_YYYY-MM-DD.csv`) and `Copy tickers (n)` (comma list,
  nulls skipped, de-duplicated). Buttons flash "Copied ✓" / "Copy failed".
- Row count summary ("Showing 87 of 187 companies · 12 stale hidden").
- Company cell opens the node (as before); companies with no graph node now render as plain text
  instead of a dead button.
- Widths: `colgroup` re-normalises the relative widths over the visible columns so the fixed-layout
  table always fills 100%.

### Timelines
- Navigation changed from category tabs to **topic pills** (13 topics, grouped under small
  category labels in the old category order), each pill showing its total row count (tooltip:
  curated vs auto-derived split). One topic is shown at a time; default = Generation transitions.
- Search box across every row of every table in the selected topic (curated and auto-derived).
- "Auto-derived rows since" segmented control: 30d / 90d / 180d / All (default All), applied only
  to the generated table's `Date` column (YYYY-MM-DD).
- Generated table: sorted newest-first by default; Date / Company / Source headers are sortable;
  **Group by company** toggle (groups keep first-appearance order of the current sort, so with the
  default sort the most recently active company is first; header row shows "n signals · latest
  date" with a clickable company).
- Every table heading carries a provenance badge: `Curated` vs `Auto-derived from graph`, plus
  "n of m rows".
- `Copy CSV` / `Download CSV` of the selected topic's generated table, visible rows only
  (`timeline_<topic>_signals_YYYY-MM-DD.csv`).
- Company cells stay clickable via `resolve` + `onOpen` (CompanyLink) in both table kinds.
- Long Signal / Figure cells clamp to 3 lines (`tb-clamp`, fixed-layout table with a `colgroup`)
  and expand **in place** on click / Enter / Space (Escape or a second click collapses) via
  CellText's new `inline` mode. On ≤700px cards the clamp is off, as for every other cell.

### Capex & Backlog
- Both bar charts kept. Each chart header now has a **Sort: Value | Name** toggle and a
  `Copy CSV` (Company, Chart value ($B), Reported, Basis, Growth, Detail, Source).
- Hover / focus tooltip per bar (CSS-only, `role="tooltip"`, row is focusable) with the exact
  chart value (`busd` + unit), the reported figure, basis, growth **only if the JSON has
  `growth`**, detail and source. No growth numbers are computed anywhere.
- Every bar row shows its source label as small muted text under the bar; every summary tile
  shows its source line too. The group tables keep their visible Source column.
- `Copy table as CSV` / `Download CSV` for all group tables at once (with a Group column).

### CellText
- New optional prop `inline?: boolean`: expand in place instead of opening the dialog. Keyboard:
  Enter / Space toggles, Escape collapses; `aria-expanded` set; an expanded cell stays
  interactive even though it no longer measures as clipped. Default (dialog) behaviour unchanged.

## How I verified
- `cd web && npx tsc --noEmit --incremental false` → 0 errors in my files. (At the time of the
  last run the only error reported was in `src/components/AskGraph.tsx`, another agent's
  in-progress file that did not exist at my baseline — not mine to touch.)
- `lib/table.ts` executed for real: transpiled the actual file with the project's `typescript`
  package in Node and ran assertions for date parsing (label + ISO, `2022-03` correctly rejected),
  the 45/120-day bucket edges, blanks-last / stable / numeric-aware sorting, AND-word search,
  RFC 4180 quoting, and file names. All pass. (Script in the session scratchpad, not in the repo.)
- Static checks: no Korean characters in any of my files; every `tb-*` class used in TSX has a
  rule in `Tables.css`; no `pages/` directory (App Router only, so component-level CSS import is
  allowed — `next.config.mjs` has `reactStrictMode: false`).

## Could not do / please check visually (no dev server allowed for me)
1. Screener toolbar wrapping around 1000–1200px main width (three selects + search + five
   action buttons wrap to two lines by design).
2. The "As of" column: dot + date + "22d ago" at narrow desktop widths (I widened the column and
   let that cell overflow into its own padding rather than clip).
3. Timelines: 3-line clamp + "⋯" mark + click-to-expand on Signal / Figure cells; the group header
   rows in the ≤700px card-stack (styled as dividers, `::before` label suppressed).
4. Capex tooltip position for the LAST bar of the second chart (it opens below the row; page
   scrolls if needed). `pointer-events: none` so it never traps the mouse.
5. The `Columns ▾` popover on phones (it flips to `left: 0` under 860px).
6. Downloads on Vercel: `<a download>` + Blob, standard behaviour; nothing to configure.
