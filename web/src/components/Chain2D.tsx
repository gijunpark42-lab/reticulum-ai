"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fetchJson } from "@/lib/data";
import { slugLabel } from "@/lib/taxonomy";
import type { MergedGraph } from "@/lib/types";
import {
  buildFromChain, buildFromMerged, renderChain2D, type C2DData,
} from "@/lib/chain2d";

interface ChainIndexEntry {
  id: string;
  company: string;
  chain_focus: string;
}

const ALL = "__ALL__";

export default function Chain2D({ glass }: { glass: boolean }) {
  const [index, setIndex] = useState<ChainIndexEntry[]>([]);
  const [sel, setSel] = useState<string>(ALL);
  const [data, setData] = useState<C2DData | null>(null);
  const [loading, setLoading] = useState(true);

  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const epanelRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);

  useEffect(() => {
    fetchJson<ChainIndexEntry[]>("/data/chains/index.json").then(setIndex).catch(() => {});
  }, []);

  // Load the selected chain (or the whole merged graph for "All").
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setData(null);
    const p =
      sel === ALL
        ? fetchJson<MergedGraph>("/data/merged_graph.json").then(buildFromMerged)
        : fetchJson<any>(`/data/chains/${sel}.json`).then(buildFromChain);
    p.then((d) => {
      if (alive) {
        setData(d);
        setLoading(false);
      }
    }).catch(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [sel]);

  // Track container width so the SVG lays out to the available space.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // (Re)draw the SVG whenever the data or width changes.
  useEffect(() => {
    if (!data || !svgRef.current || !tipRef.current || !epanelRef.current) return;
    renderChain2D(svgRef.current, tipRef.current, epanelRef.current, data, width);
  }, [data, width]);

  const cur = index.find((c) => c.id === sel);
  const counts = useMemo(() => {
    if (!data) return { c: 0, e: 0 };
    return { c: data.columns.reduce((s, col) => s + col.players.length, 0), e: data.edges.length };
  }, [data]);

  const bg = glass ? "#262b35" : "#0b0e13";

  return (
    <div className={"c2d" + (glass ? " glass" : "")}>
      <div className="row" style={{ marginBottom: "0.9rem" }}>
        <div className="grow" style={{ maxWidth: 460 }}>
          <label className="field-label">Chain</label>
          <select value={sel} onChange={(e) => setSel(e.target.value)}>
            <option value={ALL}>🌐 All value chains (everything)</option>
            {index.map((c) => (
              <option key={c.id} value={c.id}>
                {slugLabel(c.id)}
              </option>
            ))}
          </select>
        </div>
        <div className="caption">
          {sel === ALL ? (
            <>
              <b style={{ color: "var(--ap-text)" }}>All value chains</b> — every company &amp;
              edge, grouped by layer
            </>
          ) : cur ? (
            <>
              <b style={{ color: "var(--ap-text)" }}>{cur.company}</b> — {cur.chain_focus}
            </>
          ) : null}
        </div>
      </div>

      {/* Always-visible legend for the map's visual language + interactions. */}
      <div className="c2d-legend" aria-label="Map legend">
        <span className="lg-item">
          <span className="lg-dot" />
          earnings data
        </span>
        <span className="lg-item">
          <svg width="24" height="6" aria-hidden="true">
            <line x1="1" y1="3" x2="23" y2="3" stroke="#7dd3fc" strokeWidth="2" />
          </svg>
          deal data
        </span>
        <span className="lg-item">
          <svg width="24" height="6" aria-hidden="true">
            <line x1="1" y1="3" x2="23" y2="3" stroke="#64748b" strokeWidth="1.5" strokeDasharray="4 3" />
          </svg>
          structure only
        </span>
        <span className="lg-item">
          <span className="lg-sw" style={{ background: "#fbbf24" }} />▼ downstream
        </span>
        <span className="lg-item">
          <span className="lg-sw" style={{ background: "#60a5fa" }} />▲ upstream
        </span>
        <span className="lg-item lg-hint">
          hover = neighbors · click company = ripple · click edge = signals
        </span>
      </div>

      <div ref={wrapRef} className="c2d-wrap" style={{ background: bg }}>
        {loading && <div className="graph-msg">Building the map…</div>}
        <svg ref={svgRef} />
      </div>
      <div ref={tipRef} className="c2d-tip" />
      <div ref={epanelRef} className="c2d-epanel" />

      <p className="caption" style={{ marginTop: "0.6rem" }}>
        {counts.c} companies · {counts.e} edges {sel === ALL ? "across all chains" : "in this chain"}
      </p>
    </div>
  );
}
