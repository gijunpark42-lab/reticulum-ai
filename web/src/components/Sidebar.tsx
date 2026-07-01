"use client";

import { useEffect, useState } from "react";
import { CHAIN_COLORS, LAYERS, DOMAINS, slugLabel } from "@/lib/taxonomy";

interface Props {
  glass: boolean;
  setGlass: (v: boolean) => void;
  chains: Set<string>;
  layers: Set<string>;
  domains: Set<string>;
  toggle: (kind: "chain" | "layer" | "domain", slug: string) => void;
  bulk: (kind: "chain" | "layer" | "domain", on: boolean) => void;
  dimStale: boolean;
  setDimStale: (v: boolean) => void;
}

// Remember collapse state across sessions (guarded for SSR).
function usePersistedBool(key: string, def: boolean): [boolean, (v: boolean) => void] {
  const [v, setV] = useState(def);
  useEffect(() => {
    try {
      const s = localStorage.getItem(key);
      if (s !== null) setV(s === "1");
    } catch {}
  }, [key]);
  const set = (nv: boolean) => {
    setV(nv);
    try {
      localStorage.setItem(key, nv ? "1" : "0");
    } catch {}
  };
  return [v, set];
}

function AllNone({ kind, bulk }: { kind: "chain" | "layer" | "domain"; bulk: Props["bulk"] }) {
  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    fn();
  };
  return (
    <span className="allnone">
      <button onClick={stop(() => bulk(kind, true))}>All</button>
      <span>·</span>
      <button onClick={stop(() => bulk(kind, false))}>None</button>
    </span>
  );
}

function Row({
  checked,
  onChange,
  color,
  label,
  title,
}: {
  checked: boolean;
  onChange: () => void;
  color: string;
  label: string;
  title: string;
}) {
  return (
    <label className="check-row" title={title}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="dot" style={{ background: color }} />
      <span className="row-label">{label}</span>
    </label>
  );
}

function Section({
  storageKey,
  title,
  kind,
  bulk,
  forceOpen,
  count,
  children,
}: {
  storageKey: string;
  title: string;
  kind: "chain" | "layer" | "domain";
  bulk: Props["bulk"];
  forceOpen: boolean;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = usePersistedBool(`sb.${storageKey}`, storageKey === "chains");
  const show = open || forceOpen;
  return (
    <div className="sb-section">
      <div className="sb-head" onClick={() => setOpen(!open)}>
        <span className="sb-caret">{show ? "▾" : "▸"}</span>
        <span className="sb-title">{title}</span>
        {count > 0 && <span className="sb-count">{count}</span>}
        <AllNone kind={kind} bulk={bulk} />
      </div>
      {show && <div className="sb-body">{children}</div>}
    </div>
  );
}

export default function Sidebar({
  glass,
  setGlass,
  chains,
  layers,
  domains,
  toggle,
  bulk,
  dimStale,
  setDimStale,
}: Props) {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const match = (label: string) => !query || label.toLowerCase().includes(query);

  const chainRows = Object.keys(CHAIN_COLORS)
    .map((slug) => ({ slug, label: slugLabel(slug), color: CHAIN_COLORS[slug] }))
    .filter((r) => match(r.label));
  const layerRows = LAYERS.filter(([, name]) => match(name));
  const domainRows = DOMAINS.filter(([, name]) => match(name));

  return (
    <aside className="sidebar">
      <h1>AI Supply Chain</h1>

      <input
        className="sb-search"
        type="search"
        placeholder="Filter chains, layers…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="sb-legend">
        <span className="dot" style={{ background: "#7dd3fc" }} /> dot = each item&apos;s color
        in the graph
      </div>

      <Section
        storageKey="chains"
        title="Chains"
        kind="chain"
        bulk={bulk}
        forceOpen={!!query}
        count={chainRows.length}
      >
        {chainRows.map((r) => (
          <Row
            key={r.slug}
            checked={chains.has(r.slug)}
            onChange={() => toggle("chain", r.slug)}
            color={r.color}
            label={r.label}
            title={`${r.label} — this chain's edge color in the graph`}
          />
        ))}
        {chainRows.length === 0 && <div className="sb-empty">no match</div>}
      </Section>

      <Section
        storageKey="layers"
        title="Layers"
        kind="layer"
        bulk={bulk}
        forceOpen={!!query}
        count={layerRows.length}
      >
        {layerRows.map(([slug, name, color]) => (
          <Row
            key={slug}
            checked={layers.has(slug)}
            onChange={() => toggle("layer", slug)}
            color={color}
            label={name}
            title={`${name} — layer node color in the graph`}
          />
        ))}
        {layerRows.length === 0 && <div className="sb-empty">no match</div>}
      </Section>

      <Section
        storageKey="domains"
        title="Domains"
        kind="domain"
        bulk={bulk}
        forceOpen={!!query}
        count={domainRows.length}
      >
        {domainRows.map(([slug, name, color]) => (
          <Row
            key={slug}
            checked={domains.has(slug)}
            onChange={() => toggle("domain", slug)}
            color={color}
            label={name}
            title={`${name} — domain node color in the graph`}
          />
        ))}
        {domainRows.length === 0 && <div className="sb-empty">no match</div>}
      </Section>

      <hr className="sep" />

      <label className="check-row" title="Fade companies with no data in the last 180 days">
        <input type="checkbox" checked={dimStale} onChange={() => setDimStale(!dimStale)} />
        <span className="row-label">Dim stale nodes (180d)</span>
      </label>

      <div className="sidebar-footer">
        <span className="sb-foot-label">⚙ Appearance</span>
        <label className="check-row" title="Frosted-glass panel material">
          <input type="checkbox" checked={glass} onChange={() => setGlass(!glass)} />
          <span className="row-label">✨ Liquid Glass</span>
        </label>
      </div>
    </aside>
  );
}
