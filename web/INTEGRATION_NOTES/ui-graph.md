# ui-graph agent — integration notes

Scope: the two map views (Chain 2D and Graph 3D). No shared file was edited; no
dependency was added or changed; nothing under `chains/`, `graph/`, `web/public/`,
`patches/`, `transcripts/` was touched; no build/dev server was started.

## Files

| File | Status | What |
|---|---|---|
| `web/src/lib/chain2d.ts` | edited | builders unchanged; renderer gains full-path hover, pin API (`C2DHandle`), collapsed-layer bars, richer tooltips, External note, memoised reachability |
| `web/src/components/Chain2D.tsx` | edited | localStorage chain memory, per-chain model cache, collapse state + Collapse all / Expand all, Esc handling, legend additions, load-error message |
| `web/src/components/Graph3D.tsx` | edited | focus mode (1 / 2 hops) with dimming + name labels, edge width by contract count, layer legend, Fit view / Reset, richer hover tooltip, Esc, optional props |
| `web/src/components/Graph.css` | **new** | all new styles, every class prefixed `gx-`; imported by both components |
| `web/INTEGRATION_NOTES/ui-graph.md` | **new** | this file |

## Changes needed in shared files (orchestrator applies)

Only one, and it is optional but recommended — `web/src/app/page.tsx`, the
`<Graph3D … />` element (around line 237). Add one prop:

```tsx
<Graph3D
  nodes={viz.nodes}
  links={viz.links}
  visibleIds={visibleIds}
  visibleChains={chains}
  dimStale={dimStale}
  glass={glass}
  focusId={focusId}
  onNodeClick={setSelected}
  onBackgroundClick={() => setSelected(null)}
  onFocusChange={setFocusId}   // NEW — lets Reset / Esc / click-to-walk update the search box
/>
```

Without it everything still works: the graph keeps its own copy of the focus and
Reset / Esc un-focus the view, but the "Search company" `<select>` would keep
showing the old name (and re-picking that same name would not re-focus, because
the prop value would not change). With it, the two stay in sync.

No change is needed for `<Chain2D glass={glass} />`.

No change to `globals.css`, `types.ts`, `data.ts`, `taxonomy.ts`, `signals.ts`.

## New optional props (Graph3D)

| Prop | Type | Default | Meaning |
|---|---|---|---|
| `onFocusChange` | `(id: string \| null) => void` | — | Called with `null` by Reset / Esc, and with a node id when the user clicks a node **while focus mode is active** (the focus "walks" to the clicked company; the detail panel still opens as before). When this prop is absent, node clicks never move the focus. |
| `showLegend` | `boolean` | `true` | Show the layer-color legend overlay (top-right). |
| `labelLimit` | `number` | `80` | Max name labels drawn in focus mode. Ordered nearest hop first, then degree, so hubs keep their labels when a 2-hop set is large. |

All existing props (`nodes, links, visibleIds, visibleChains, dimStale, glass,
focusId, onNodeClick, onBackgroundClick`) keep their exact behaviour.

## What each view does now

### Graph 3D
- **Focus mode** — active whenever `focusId` names a visible node. Everything
  outside the neighborhood is dimmed to ~10 % (nodes) / ~8 % (links). The
  neighborhood is walked over the links that are currently visible (sidebar
  filters respected), in both directions. A `1 hop | 2 hops` toggle appears in
  the toolbar; the chip reads `Focus: NVIDIA · 27 neighbors · Esc to exit`.
  Dimming is done by returning `rgba(...)` colors from `nodeColor` / `linkColor`
  (three-forcegraph multiplies material opacity by the color's alpha, verified in
  its source) — no per-frame work, no extra objects.
- **Labels** for the focused set: HTML overlay (`.gx-labels`) positioned in the same
  animation-frame loop as the logo chips, transform-only updates, hidden when
  off-screen or behind the camera. Capped by `labelLimit`.
- **Edge width** = `0.5` for structure-only edges, `1.2 + 0.6 × contracts` capped at
  `3.2` (today's data tops out at 3 contracts per edge in `merged_graph.json`).
  Particles/arrows stay as before: only on links touching the hovered/focused node.
- **Legend** (top-right, collapsible; folded by default under 860 px): the layers and
  domains that have at least one visible node, with counts; node color = primary layer.
- **Fit view** frames the focused neighborhood if there is one, else all visible
  nodes (`zoomToFit` with a node filter). **Reset** leaves focus mode, resets hops
  to 1, and frames the whole visible graph.
- **Hover tooltip**: `Company badges` / `Primary layer · N chains · last data YYYY-MM-DD`
  (+ "outside the current focus" when applicable). Uses the library tooltip element,
  restyled via `.gx-graph .float-tooltip-kap`.
- **Esc** exits focus mode (ignored while typing in an input/textarea).
- Also fixed in passing: logo chips for nodes behind the camera were being projected
  to mirrored positions; they are now hidden like the labels.

### Chain 2D
- **Hover = full path**: hovering a company lights its complete downstream (amber)
  and upstream (blue) reach transitively and dims everything else (previously hover
  was 1-hop only). A 70 ms rest delay stops the map from flashing while the mouse
  sweeps across pills. Reach sets are memoised per node per render.
- **Click = pin** the ripple; click the same pill again, click the background, or
  press **Esc** to unpin. Esc closes the edge-detail panel first if it is open, then
  unpins on the next press. The pinned pill gets a white glow (`.gx-pinned`). With
  a pin active, clicking a directly connected company opens that edge's panel
  (behaviour kept from before). Pins survive a resize or a collapse toggle.
- **Tooltips**: edge = `A → B`, relationship, `N contracts`, `latest: <label>`
  (label with the newest `(MM-DD-YYYY)` date via `sigDate`); player = product,
  `N signals`, downstream / upstream counts, pin hint. External pills say
  "External — appears in another chain, not part of this chain's structure".
- **Collapse / expand per column**: click a layer label in the left gutter (now
  carries a ▾/▸ chevron) or a domain header on the right. A collapsed layer is drawn
  as one dashed bar; its players are spread along the bar so **edges still attach**
  and supply paths through it stay visible; the bar takes the strongest ripple mark
  of the companies inside it. Bars say "N companies collapsed — click to expand".
  Legend row has **Collapse all** / **Expand all**. Edges with both ends inside the
  same collapsed bar are not drawn. Collapse state is per session and keyed by
  layer slug, so it carries across chain switches (e.g. keep `equipment` folded).
- **Legend**: existing items kept; adds `external = appears in another chain` when
  the model has an External column, and the hint now reads
  `hover = full path · click = pin (click again / Esc = unpin) · click edge = contracts · layer label = collapse`.
- **Chain memory**: the chain switcher stores its value in
  `localStorage["aisc.chain2d"]` (every access wrapped in try/catch; server render
  and blocked storage fall back to "All"). If the remembered id is no longer in
  `chains/index.json` the view falls back to All.
- **External column** explanation appears in three places: the gutter subtitle
  "appears in another chain" under the EXTERNAL label, the pill tooltip, the legend.
- **Performance**: built models are cached per chain id in a module-level Map (tab
  switching back is instant, no refetch); the SVG is rebuilt only when data, width or
  the collapsed set changes; hover / pin / edge highlight only toggle CSS classes.
  The merged map (312 companies, 1,250 edges) does ~1.5 k classList operations per
  hover, which is well within a frame.

## Renderer API (lib/chain2d.ts)

```ts
renderChain2D(svg, tipEl, epanelEl, data, totalWidth, opts?: C2DOptions): C2DHandle

interface C2DOptions {
  collapsed?: Set<string>;                    // column slugs drawn as one bar
  onToggleCollapse?: (slug: string) => void;
  pinned?: string | null;                     // node key "colIdx|playerIdx" to restore
  onPinChange?: (key: string | null) => void;
}
interface C2DHandle {
  pin(key: string | null): void;
  escape(): boolean;   // panel open → close it; else pinned → unpin; returns whether anything changed
  pinned(): string | null;
}
```
`opts` is optional, so any other caller of `renderChain2D` keeps working unchanged.

## How I verified

- `cd web && npx tsc --noEmit --incremental false` → exit 0 on the baseline and after
  my writes. On the very last runs the shared tree had picked up errors from OTHER
  agents' in-progress files (`src/components/AskGraph.tsx`, then `src/lib/retrieval.ts`
  — they changed between runs); grouping the output by file showed **zero errors in
  `Chain2D.tsx`, `Graph3D.tsx`, `chain2d.ts`, `Graph.css`**.
- Cross-checked every `gx-` class used in TS/TSX against `Graph.css` (all defined
  except `gx-tip`, a wrapper `<div>` whose children carry the styles).
- Read the installed library sources to confirm the mechanisms relied upon:
  `three-forcegraph` `opacity = nodeOpacity * colorAlpha(color)` with tinycolor
  parsing `rgba()`, and `float-tooltip` rendering string content with `.html()`
  under class `float-tooltip-kap`.
- Confirmed data facts used for sizing: `merged_graph.json` has 312 nodes, 1,250
  edges, max 3 contracts per edge, TSMC degree 248.
- I could not run the app or look at it (dev server/build forbidden for agents), so
  the visual checks below are for the orchestrator.

## Please eyeball (things I could not see)

1. Graph tab: pick a company in Search → nodes outside the neighborhood should be
   faint, labels appear under the focused set, `1 hop | 2 hops` toggles, Esc clears.
   With `onFocusChange={setFocusId}` wired, Reset should also blank the select.
2. Graph tab on a phone width: legend starts folded; toolbar wraps; chip hidden ≤400 px.
3. Chain 2D: hover a hub (e.g. TSMC in "All value chains") — full path, no flicker
   while sweeping; click pins; Esc unpins; layer label click collapses to a bar and
   edges still reach the bar; External gutter note visible on a single chain.
4. Chain 2D: reload the page after picking a chain — it should come back to that chain.

## Not done / judgement calls

- `onFocusChange` is one optional prop rather than separate clear/select callbacks;
  focus-walk-on-click only happens when it is wired, so nothing changes for a caller
  that does not pass it.
- Collapse state is not persisted to localStorage (only the chain is, as requested).
- No directional particles were added to focus mode beyond the existing
  hover/focus-touching links, to protect frame rate.
- `VizLink.contracts` is sliced to 3 in `lib/data.ts`; the data itself also tops out
  at 3 today, so the width scale is not affected. If edges ever carry more, either
  raise that slice or add a `contractCount` field in `buildViz` (shared file — not
  changed by me).
