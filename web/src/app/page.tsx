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

const TABS = ["Graph", "Chain 2D", "Timelines", "Screener"] as const;
type Tab = (typeof TABS)[number];

const STALE_COLOR = "#3a3f46";

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

  // Apply sidebar filters (mirrors app.py 613-642).
  const filtered = useMemo(() => {
    if (!viz) return { nodes: [], links: [], ids: new Set<string>() };
    const nodes = viz.nodes.filter((n) => {
      const chainOk = n.chains.length === 0 || n.chains.some((c) => chains.has(c));
      const hasGroups = n.layers.length + n.domains.length > 0;
      const groupOk =
        !hasGroups ||
        n.layers.some((l) => layers.has(l)) ||
        n.domains.some((d) => domains.has(d));
      return chainOk && groupOk;
    });
    const ids = new Set(nodes.map((n) => n.id));
    // Dim-stale: swap color to gray (clone so we don't mutate shared objects).
    const shown = nodes.map((n) =>
      dimStale && n.stale ? { ...n, color: STALE_COLOR } : n
    );
    const links = viz.links.filter(
      (l) => chains.has(l.chain) && ids.has(l.source) && ids.has(l.target)
    );
    return { nodes: shown, links, ids };
  }, [viz, chains, layers, domains, dimStale]);

  const toggle = (kind: "chain" | "layer" | "domain", slug: string) => {
    const map = { chain: [chains, setChains], layer: [layers, setLayers], domain: [domains, setDomains] } as const;
    const [set, setter] = map[kind] as [Set<string>, (s: Set<string>) => void];
    const next = new Set(set);
    next.has(slug) ? next.delete(slug) : next.add(slug);
    setter(next);
  };

  const searchNames = useMemo(
    () => filtered.nodes.map((n) => n.id).sort((a, b) => a.localeCompare(b)),
    [filtered.nodes]
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
        dimStale={dimStale}
        setDimStale={setDimStale}
      />

      <main className="main">
        <h1 className="hero-title">AI Supply Chain</h1>
        <p className="hero-tag">
          The global AI &amp; semiconductor web — every supplier, customer, and deal, connected.
        </p>

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
                {filtered.nodes.length} companies · {filtered.links.length} edges — click a
                node for details. Drag to rotate, scroll to zoom.
              </div>
            </div>
            <Graph3D
              nodes={filtered.nodes}
              links={filtered.links}
              glass={glass}
              focusId={focusId}
              onNodeClick={setSelected}
              onBackgroundClick={() => setSelected(null)}
            />
          </>
        )}

        {viz && tab === "Chain 2D" && <Chain2D glass={glass} />}
        {viz && tab === "Timelines" && <Timelines />}
        {viz && tab === "Screener" && <Screener byId={viz.byId} />}
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
