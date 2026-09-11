"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { MergedGraph, LogoManifest, VizNode } from "@/lib/types";
import { fetchJson, buildViz } from "@/lib/data";
import { CHAIN_COLORS, LAYERS, DOMAINS, slugLabel } from "@/lib/taxonomy";
import { buildResolver } from "@/lib/company";
import Sidebar from "@/components/Sidebar";
import Graph3D from "@/components/Graph3D";
import NodePanel from "@/components/NodePanel";
import Screener from "@/components/Screener";
import Timelines from "@/components/Timelines";
import Chain2D from "@/components/Chain2D";
import Generations from "@/components/Generations";
import Coverage from "@/components/Coverage";
import CapexBacklog from "@/components/CapexBacklog";
import SearchBox from "@/components/SearchBox";
import Exposure from "@/components/Exposure";
import AskGraph from "@/components/AskGraph";

const TABS = ["Graph", "Chain 2D", "Generations", "Exposure", "Timelines", "Screener", "Capex", "Coverage", "Ask", "Semi Bot"] as const;
// External dashboard embedded in the "Semi Bot" tab (its own Vercel project; sends no
// X-Frame-Options / CSP frame-ancestors header, so it can be shown inline in an iframe).
const SEMI_BOT_URL = "https://semiband-dashboard.vercel.app";
type Tab = (typeof TABS)[number];

export default function Page() {
  const [graph, setGraph] = useState<MergedGraph | null>(null);
  const [manifest, setManifest] = useState<LogoManifest>({});
  const [reportKeys, setReportKeys] = useState<Set<string>>(new Set());
  const [err, setErr] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>("Graph");
  const [navOpen, setNavOpen] = useState(false); // mobile filter drawer
  const [glass, setGlass] = useState(true);
  const [dimStale, setDimStale] = useState(false);
  const [chains, setChains] = useState<Set<string>>(new Set(Object.keys(CHAIN_COLORS)));
  const [layers, setLayers] = useState<Set<string>>(new Set(LAYERS.map((l) => l[0])));
  const [domains, setDomains] = useState<Set<string>>(new Set(DOMAINS.map((d) => d[0])));

  const [selected, setSelected] = useState<VizNode | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);

  // Load curated data once.
  useEffect(() => {
    (async () => {
      try {
        // report_keys.json is a ~1KB array of company names. We only need to know
        // WHICH companies have a report to draw the badge — the full 1.6MB
        // reports.bundle.json is lazy-loaded by NodePanel when one is opened.
        const [g, m, rk] = await Promise.all([
          fetchJson<MergedGraph>("/data/merged_graph.json"),
          fetchJson<LogoManifest>("/logos/manifest.json"),
          fetchJson<string[]>("/data/report_keys.json"),
        ]);
        setGraph(g);
        setManifest(m);
        setReportKeys(new Set(rk));
      } catch (e: any) {
        setErr(e?.message || String(e));
      }
    })();
  }, []);

  // Reflect glass on <body> so CSS theme rules apply app-wide.
  useEffect(() => {
    document.body.classList.toggle("glass", glass);
  }, [glass]);

  // While the mobile drawer is open, stop the page behind it from scrolling.
  useEffect(() => {
    document.body.classList.toggle("nav-open", navOpen);
    return () => document.body.classList.remove("nav-open");
  }, [navOpen]);

  // On a phone the tab bar is a scrollable strip, so the tab you just picked can
  // sit off-screen. Pull it back into view. (`block: "nearest"` keeps this from
  // scrolling the page vertically as a side effect. No `behavior: "smooth"` —
  // with the strip's scroll-snap it silently does nothing in Chrome.)
  const tabsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = tabsRef.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    el?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [tab]);

  const viz = useMemo(() => {
    if (!graph) return null;
    return buildViz(graph, manifest, reportKeys);
  }, [graph, manifest, reportKeys]);

  // Which nodes pass the sidebar filters (mirrors app.py 613-642). We compute a
  // visible-ID set rather than a filtered array, so the graph shows/hides nodes
  // instead of rebuilding — the layout stays put when you toggle a checkbox.
  const visibleIds = useMemo(() => {
    const s = new Set<string>();
    if (!viz) return s;
    for (const n of viz.nodes) {
      const chainOk = n.chains.length === 0 || n.chains.some((c) => chains.has(c));
      const hasGroups = n.layers.length + n.domains.length > 0;
      const groupOk =
        !hasGroups ||
        n.layers.some((l) => layers.has(l)) ||
        n.domains.some((d) => domains.has(d));
      if (chainOk && groupOk) s.add(n.id);
    }
    return s;
  }, [viz, chains, layers, domains]);

  const linkCount = useMemo(() => {
    if (!viz) return 0;
    let c = 0;
    for (const l of viz.links)
      if (chains.has(l.chain) && visibleIds.has(l.source) && visibleIds.has(l.target)) c++;
    return c;
  }, [viz, chains, visibleIds]);

  const toggle = (kind: "chain" | "layer" | "domain", slug: string) => {
    const map = { chain: [chains, setChains], layer: [layers, setLayers], domain: [domains, setDomains] } as const;
    const [set, setter] = map[kind] as [Set<string>, (s: Set<string>) => void];
    const next = new Set(set);
    next.has(slug) ? next.delete(slug) : next.add(slug);
    setter(next);
  };

  // Select-all / clear for a whole checklist section.
  const bulk = (kind: "chain" | "layer" | "domain", on: boolean) => {
    const all =
      kind === "chain"
        ? Object.keys(CHAIN_COLORS)
        : kind === "layer"
        ? LAYERS.map((l) => l[0])
        : DOMAINS.map((d) => d[0]);
    const setter = kind === "chain" ? setChains : kind === "layer" ? setLayers : setDomains;
    setter(on ? new Set(all) : new Set());
  };

  // Companies the SearchBox can pick from = the ones the sidebar filters leave visible.
  const searchNodes = useMemo(
    () => (viz ? viz.nodes.filter((n) => visibleIds.has(n.id)) : []),
    [viz, visibleIds]
  );

  // Per-row counts for the sidebar checklists ("how many visible companies sit in
  // this chain / layer / domain") — recomputed only when the filters change.
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

  // Open a company's NodePanel by name — the same panel a 3D-graph node click
  // opens. Handed to the table views so any company name in them is clickable.
  const openNode = (id: string) => {
    const n = viz?.byId.get(id);
    if (n) setSelected(n);
  };
  // Maps a table's free-text company name back to a graph node id.
  const resolveCompany = useMemo(
    () => buildResolver(viz ? viz.byId.keys() : []),
    [viz]
  );

  if (err)
    return (
      <div className="app">
        <div className="main">
          <h2>Failed to load data</h2>
          <p className="muted">{err}</p>
          <p className="caption">
            Run <code>npm run sync</code> in <code>web/</code> to copy the JSON assets.
          </p>
        </div>
      </div>
    );

  return (
    <div className="app">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        glass={glass}
        setGlass={setGlass}
        chains={chains}
        layers={layers}
        domains={domains}
        toggle={toggle}
        bulk={bulk}
        dimStale={dimStale}
        setDimStale={setDimStale}
        visibleCounts={visibleCounts}
      />

      {/* Backdrop only exists while the mobile drawer is open. */}
      {navOpen && <div className="nav-backdrop" onClick={() => setNavOpen(false)} />}

      <main className="main">
        <header className="app-header">
          <div className="app-header-row">
            <button
              className="nav-toggle"
              onClick={() => setNavOpen(true)}
              aria-label="Open filters"
              aria-expanded={navOpen}
            >
              ☰<span className="nav-toggle-text">Filters</span>
            </button>
            <h1 className="app-title">AI Supply Chain</h1>
            <p className="app-sub">
              The global AI &amp; semiconductor web — every supplier, customer, and deal,
              connected.
            </p>
          </div>
          <div className="tabs" role="tablist" ref={tabsRef}>
            {TABS.map((t) => (
              <button
                key={t}
                className="tab"
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </header>

        {!viz && <div className="spinner">Loading the graph…</div>}

        {viz && tab === "Graph" && (
          <>
            <div className="row" style={{ marginBottom: "0.9rem" }}>
              <div className="grow" style={{ maxWidth: 420 }}>
                <label className="field-label">Search company</label>
                <SearchBox
                  nodes={searchNodes}
                  onPick={(id) => setFocusId(id)}
                  onClear={() => setFocusId(null)}
                />
              </div>
              <div className="caption">
                {visibleIds.size} companies · {linkCount} edges — click a node for details.
                Drag to rotate, scroll to zoom.
              </div>
            </div>
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
              onFocusChange={setFocusId}
            />
          </>
        )}

        {viz && tab === "Chain 2D" && <Chain2D glass={glass} />}
        {viz && tab === "Generations" && (
          <Generations nodes={viz.nodes} byId={viz.byId} onSelect={setSelected} />
        )}
        {viz && tab === "Timelines" && (
          <Timelines resolve={resolveCompany} onOpen={openNode} />
        )}
        {viz && tab === "Screener" && <Screener byId={viz.byId} onOpen={openNode} />}
        {viz && tab === "Capex" && (
          <CapexBacklog resolve={resolveCompany} onOpen={openNode} />
        )}
        {viz && tab === "Exposure" && (
          <Exposure nodes={viz.nodes} byId={viz.byId} onOpen={openNode} />
        )}
        {viz && tab === "Coverage" && <Coverage nodes={viz.nodes} onSelect={setSelected} />}
        {viz && tab === "Ask" && (
          <AskGraph nodes={viz.nodes} links={viz.links} onOpen={openNode} />
        )}
        {tab === "Semi Bot" && (
          <div className="embed">
            <p className="caption embed-caption">
              Semi Bot dashboard, shown inline.{" "}
              <a href={SEMI_BOT_URL} target="_blank" rel="noopener noreferrer">
                Open in a new tab ↗
              </a>
            </p>
            <iframe
              className="embed-frame"
              src={SEMI_BOT_URL}
              title="Semi Bot dashboard"
              loading="lazy"
              allow="clipboard-write; fullscreen"
            />
          </div>
        )}
      </main>

      {selected && (
        <NodePanel
          node={selected}
          glass={glass}
          onClose={() => setSelected(null)}
          onNavigate={(id) => {
            const n = viz?.byId.get(id);
            if (n) setSelected(n);
          }}
        />
      )}
    </div>
  );
}
