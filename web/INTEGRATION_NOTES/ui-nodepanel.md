# ui-nodepanel — integration notes

Agent: `ui-nodepanel` (node panel · company search · sidebar). Date: 2026-09-05.

## Files

Created
- `web/src/lib/search.ts` — typeahead index + ranking (`normalize`, `buildSearchIndex`, `searchNodes`) and the recent-picks helpers (`loadRecent`, `pushRecent`, localStorage key `aisc.recent`, max 8, try/catch guarded).
- `web/src/components/SearchBox.tsx` — reusable typeahead. Props `{ nodes: VizNode[]; onPick: (id) => void; onClear?: () => void; placeholder?: string }`.
- `web/src/components/NodePanel.css` — all new panel styles, prefixed `.np-`.
- `web/src/components/Sidebar.css` — new sidebar styles (`.sbx-`) **and** the SearchBox styles (`.srch-`). The SearchBox styles live here because this agent may only create these two CSS files; `SearchBox.tsx` imports `./Sidebar.css`. Feel free to split them into `SearchBox.css` later — pure move, no selector changes needed.
- `web/INTEGRATION_NOTES/ui-nodepanel.md` — this file.

Edited
- `web/src/components/NodePanel.tsx` — rewritten (same props `{node, glass, onClose, onNavigate}`; ReportView / TradingViewChart / LiveQuote / generation exposure untouched).
- `web/src/components/Sidebar.tsx` — new optional prop `visibleCounts`, Reset-filters button, compact legend.

Not touched: `CompanyLink.tsx`, `lib/company.ts` (no change was needed), everything outside my file list.

## What the NodePanel now shows (top → bottom)

1. Header: logo + name; meta row = `ticker · exchange` tag, `🇺🇸 US` (flag + ISO code), status pill (`public` green / `subsidiary` amber / `private` grey), `last data … · stale`.
2. Action buttons (`.np-actions`, reuse the global `.copy-btn` look of the Coverage tab):
   - `📋 <ticker>` copies the ticker (→ `✓ copied` for 1.4 s, same mechanic as Coverage).
   - `↗ TradingView` — US: `https://www.tradingview.com/symbols/{EXCHANGE}-{TICKER}/`; non-US best effort via a small exchange map (TSE, TWSE, KOSPI/KRX/KOSDAQ→KRX, SZSE, SSE, XETRA→XETR, Euronext, MIL, OMXSTO, OSL, SIX, HKEX (leading zeros stripped), VIE, LSE, IDX). Yahoo suffix (`2382.TW`) is stripped. Unknown exchange → no button.
   - `↗ Yahoo Finance` — `https://finance.yahoo.com/quote/{yahooSymbol(ticker, exchange)}/` using `lib/yahoo.ts`.
   - `📋 Transcript` — copies `Transcript:<company>` (mirrors Coverage's button exactly).
3. Chart (TradingViewChart for US, LiveQuote otherwise) — unchanged.
4. Stock Report / Download PDF buttons + report box — unchanged.
5. **Latest by slot** strip (`.np-slots`): one card per screener slot (`revenue_growth`, `guidance`, `backlog_or_b2b`, `supply_status`, `next_catalyst`) showing the latest-dated tagged entry (figure if it has one, else the signal, clamped to 3 lines; date + label underneath; full text in the tooltip). Only slots that exist render.
6. Badges, layer/domain pills, chain pills, product cards, generation exposure — unchanged.
7. Left column: Product/Capacity timeline (unchanged) + **Signals**:
   - counterparty entries (`quarterly_data[].counterparty`) are EXCLUDED here — they get their own section (8).
   - newest first (by the `(MM-DD-YYYY)` in the label, via `sigDate`).
   - free-text filter box (matches label + signal + figure; Esc clears the box first, second Esc closes the panel).
   - topic chips built from `topics` with counts (single-select toggle, `All` resets).
   - pagination: 8 rows, `Show 12 more (N hidden)` / `Show less`; resets when the filter changes or the node changes.
   - each row: `label text` + **date chip** (`.np-date`) + chain tag on the right, signal, figure, then tiny tags (slot in blue, topics grey).
   - the insertion point for the evidence button is inside the row header:
     `{/* EVIDENCE_SLOT: orchestrator inserts <EvidenceButton .../> here */}` (in `SigRow`, `NodePanel.tsx`). Nothing is imported for it.
8. Right column: **Customers →** / **← Suppliers** edge groups. Per counterpart: `N deals · latest MM-DD-YYYY` (date = newest contract's source label), sorted by latest date, then deal count, then name; contracts newest-first, 3 shown + `+N more deals` toggle; company name still navigates (`onNavigate`). Suppliers without deals stay a comma list (18 + `+N more`).
9. **Customers & suppliers on file** (full width, only when the node has counterparty entries; 22 nodes today, e.g. HD Hyundai Electric 29 entries): grouped per counterparty, split Customers / Suppliers, each row = name, `not a graph node` marker (plain text, no navigation), `N entries · latest date`, latest figure; click → every entry (label + date chip, signal with the redundant `Customer X:` prefix removed, figure). Role = `counterparty_role`, falling back to the `Supplier ` signal prefix.
10. Keyboard: **Esc closes the panel** (window listener; uses a ref so it never re-subscribes when page.tsx passes a fresh `onClose` arrow). SearchBox / signal-filter consume Esc first when they have something to close/clear.

Memoised: `SigRow`, `EdgeGroupCard`, `OnFileRow` (`React.memo`); all lists via `useMemo`.

## Integration the orchestrator must do in `page.tsx`

### 1. Replace the Graph tab `<select>` with SearchBox

```tsx
import SearchBox from "@/components/SearchBox";

// replace the `searchNames` memo (no longer needed) with the visible VizNode list:
const searchNodes = useMemo(
  () => (viz ? viz.nodes.filter((n) => visibleIds.has(n.id)) : []),
  [viz, visibleIds]
);
```

```tsx
<div className="grow" style={{ maxWidth: 420 }}>
  <label className="field-label">Search company</label>
  <SearchBox
    nodes={searchNodes}
    onPick={(id) => setFocusId(id)}
    onClear={() => setFocusId(null)}
  />
</div>
```

What `focusId` should do: nothing new is required — `Graph3D` already flies the camera to `focusId` (`cameraPosition(...)`, 1.5 s) and uses it as `emphasisId` (particles/arrows only on that node's links). Optional, if you want a pick to also open the card: `onPick={(id) => { setFocusId(id); openNode(id); }}`. Passing `viz.nodes` instead of the visible subset also works, but a hidden node would then be "focused" without being drawn.

The SearchBox can be reused anywhere a company picker is needed (e.g. Screener / Timelines headers): `<SearchBox nodes={viz.nodes} onPick={openNode} placeholder="Open a company…" />`.

### 2. (Optional) visible-node counts in the Sidebar

`Sidebar` accepts an optional `visibleCounts?: { chains; layers; domains }` (each `Record<slug, number>`). Without it the rows show no counts (current behaviour). To enable:

```tsx
const visibleCounts = useMemo(() => {
  const chains: Record<string, number> = {};
  const layers: Record<string, number> = {};
  const domains: Record<string, number> = {};
  if (viz)
    for (const n of viz.nodes) {
      if (!visibleIds.has(n.id)) continue;
      for (const c of n.chains) chains[c] = (chains[c] || 0) + 1;
      for (const l of n.layers) layers[l] = (layers[l] || 0) + 1;
      for (const d of n.domains) domains[d] = (domains[d] || 0) + 1;
    }
  return { chains, layers, domains };
}, [viz, visibleIds]);

<Sidebar … visibleCounts={visibleCounts} />
```

(The type is exported: `import type { VisibleCounts } from "@/components/Sidebar"`.)

### 3. Nothing else

No changes needed in `globals.css`, `types.ts`, `data.ts`, `taxonomy.ts`, `signals.ts`, `yahoo.ts`, `derive.py`. `Sidebar`'s existing props are unchanged, so page.tsx compiles as-is even before steps 1–2.

## Sidebar changes

- `↺ Reset filters` button under the filter box (calls `bulk("chain"|"layer"|"domain", true)` and clears the sidebar's text filter); disabled when nothing is off; shows `N filters off` next to it.
- Per-row visible-node count when `visibleCounts` is passed (see above); `0` is dimmed.
- Collapsible **Legend** (persisted in `localStorage` `sb.legend`, default closed): 13 layers in stack order + 4 domains with their node colours.
- All / None per section already existed — kept. Mobile drawer (`open` / `onClose`, `.sb-close`) untouched.

## How I verified

- `cd web && npx tsc --noEmit --incremental false` → exit 0, zero errors (run after every edit, final run after the last change).
- Data shapes checked against the live `web/public/data/merged_graph.json` (read-only Python): 312 nodes / 1250 edges; 145 counterparty entries on 22 nodes (91 customer / 54 supplier), all signals start with `Customer X:` / `Supplier X:`; slot and topic tag counts; every exchange string present in the data is covered by the TradingView / Yahoo maps (unknown → button simply omitted).
- No visual test possible here (no dev server allowed) — please eyeball: NVIDIA (92 signals → pagination + chips), HD Hyundai Electric (on-file section), Lumentum (many contract groups), a private node (no ticker → only the Transcript button), and the ≤860 px sheet layout.

## Known limits / not done

- CSS is conservative and only adds `.np-` / `.sbx-` / `.srch-` rules; it relies on `.copy-btn`, `.btn`, `.pgrid`, `.pcol-head`, `.sig-*`, `.deal-*`, `.sb-caret/.sb-title/.sb-count`, `.dot` from globals.css. If another agent renames those, these components will look unstyled but still work.
- The `.srch-*` styles are in `Sidebar.css` (file-ownership constraint) — see Files.
- Search does not highlight the matched substring inside the name (kept the row simple); product/sector matches show the matching product text in blue instead.
- TradingView links for non-US exchanges are best effort (exchange code map); a wrong code lands on TradingView's search page rather than 404.
- Status pill replaces the old `Private` tag in the meta row (same information, now for all three statuses).
