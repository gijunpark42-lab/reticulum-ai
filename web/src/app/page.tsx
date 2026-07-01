"use client";

import { useEffect, useMemo, useState } from "react";
import type { MergedGraph, LogoManifest, VizNode } from "@/lib/types";
import { fetchJson, buildViz } from "@/lib/data";
import { CHAIN_COLORS, LAYERS, DOMAINS, slugLabel } from "@/lib/taxonomy";
import Sidebar from "@/components/Sidebar";
import Graph3D from "@/components/Graph3D";
import NodePanel from "@/components/NodePanel";
import Screener from "@/components/Screener";
import Timelines from "@/components/Timelines";
import Chain2D from "@/components/Chain2D";
import Generations from "@/components/Generations";
import Coverage from "@/components/Coverage";

const TABS = ["Graph", "Chain 2D", "Generations", "Timelines", "Screener", "Coverage"] as const;
type Tab = (typeof TABS)[number];

export default function Page() {
  const [graph, setGraph] = useState<MergedGraph | null>(null);
  const [manifest, setManifest] = useState<LogoManifest>({});
  const [reportKeys, setReportKeys] = useState<Set<string>>(new Set());
  const [err, setErr] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>("Graph");
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
        const [g, m, rb] = await Promise.all([
          fetchJson<MergedGraph>("/data/merged_graph.json"),
          fetchJson<LogoManifest>("/logos/manifest.json"),
          fetchJson<Record<string, unknown>>("/data/reports.bundle.json"),
        ]);
        setGraph(g);
        setManifest(m);
        setReportKeys(new Set(Object.keys(rb)));
      } catch (e: any) {
        setErr(e?.message || String(e));
      }
    })();
  }, []);

  // Reflect glass on <body> so CSS theme rules apply app-wide.
  useEffect(() => {
    document.body.classList.toggle("glass", glass);
  }, [glass]);

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

  const searchNames = useMemo(
    () => [...visibleIds].sort((a, b) => a.localeCompare(b)),
    [visibleIds]
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
        glass={glass}
        setGlass={setGlass}
        chains={chains}
        layers={layers}
        domains={domains}
        toggle={toggle}
        bulk={bulk}
        dimStale={dimStale}
        setDimStale={setDimStale}
      />

      <main className="main">
        <header className="app-header">
          <div className="app-header-row">
            <h1 className="app-title">AI Supply Chain</h1>
            <p className="app-sub">
              The global AI &amp; semiconductor web — every supplier, customer, and deal,
              connected.
            </p>
          </div>
          <div className="tabs" role="tablist">
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
                <select
                  value={focusId || ""}
                  onChange={(e) => setFocusId(e.target.value || null)}
                >
                  <option value="">—</option>
                  {searchNames.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
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
            />
          </>
        )}

        {viz && tab === "Chain 2D" && <Chain2D glass={glass} />}
        {viz && tab === "Generations" && (
          <Generations nodes={viz.nodes} byId={viz.byId} onSelect={setSelected} />
        )}
        {viz && tab === "Timelines" && <Timelines />}
        {viz && tab === "Screener" && <Screener byId={viz.byId} />}
        {viz && tab === "Coverage" && <Coverage nodes={viz.nodes} onSelect={setSelected} />}
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
