"use client";

import { useEffect, useState } from "react";
import { CHAIN_COLORS, LAYERS, DOMAINS, slugLabel } from "@/lib/taxonomy";
import "./Sidebar.css";

// Optional: how many currently VISIBLE nodes each chain / layer / domain has.
// page.tsx computes it from `visibleIds` (see INTEGRATION_NOTES/ui-nodepanel.md);
// when it is not passed the rows simply show no counts.
export interface VisibleCounts {
  chains: Record<string, number>;
  layers: Record<string, number>;
  domains: Record<string, number>;
}

interface Props {
  // On phones/tablets the sidebar is an off-canvas drawer: `open` slides it in,
  // `onClose` is the ✕ button. On desktop the CSS ignores both and it is always
  // a pinned column.
  open: boolean;
  onClose: () => void;
  glass: boolean;
  setGlass: (v: boolean) => void;
  chains: Set<string>;
  layers: Set<string>;
  domains: Set<string>;
  toggle: (kind: "chain" | "layer" | "domain", slug: string) => void;
  bulk: (kind: "chain" | "layer" | "domain", on: boolean) => void;
  dimStale: boolean;
  setDimStale: (v: boolean) => void;
  visibleCounts?: VisibleCounts;
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
  count,
}: {
  checked: boolean;
  onChange: () => void;
  color: string;
  label: string;
  title: string;
  count?: number; // visible-node count; undefined = counts not available
}) {
  return (
    <label className="check-row" title={title}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="dot" style={{ background: color }} />
      <span className="row-label">{label}</span>
      {count !== undefined && (
        <span className={"sbx-cnt" + (count === 0 ? " zero" : "")} title={`${count} visible companies`}>
          {count}
        </span>
      )}
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

// Compact color key: the 13 layers in stack order, then the 4 domains. Useful
// when the Layers / Domains sections above are collapsed.
function Legend() {
  const [open, setOpen] = usePersistedBool("sb.legend", false);
  return (
    <div className="sbx-legend">
      <div className="sbx-legend-head" onClick={() => setOpen(!open)}>
        <span className="sb-caret">{open ? "▾" : "▸"}</span>
        <span className="sb-title">Legend</span>
        <span className="sb-count">node colors</span>
      </div>
      {open && (
        <div className="sbx-legend-grid">
          <div className="sbx-legend-sub">Layers (top → bottom)</div>
          {LAYERS.map(([slug, name, color]) => (
            <span className="sbx-lg" key={slug} title={name}>
              <span className="dot" style={{ background: color }} />
              {name}
            </span>
          ))}
          <div className="sbx-legend-sub">Domains</div>
          {DOMAINS.map(([slug, name, color]) => (
            <span className="sbx-lg" key={slug} title={name}>
              <span className="dot" style={{ background: color }} />
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const CHAIN_SLUGS = Object.keys(CHAIN_COLORS);

export default function Sidebar({
  open,
  onClose,
  glass,
  setGlass,
  chains,
  layers,
  domains,
  toggle,
  bulk,
  dimStale,
  setDimStale,
  visibleCounts,
}: Props) {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const match = (label: string) => !query || label.toLowerCase().includes(query);

  const chainRows = CHAIN_SLUGS.map((slug) => ({ slug, label: slugLabel(slug), color: CHAIN_COLORS[slug] })).filter(
    (r) => match(r.label)
  );
  const layerRows = LAYERS.filter(([, name]) => match(name));
  const domainRows = DOMAINS.filter(([, name]) => match(name));

  // How many checkboxes are currently OFF across the three sections — drives the
  // "Reset filters" button (disabled when there is nothing to reset).
  const offCount =
    CHAIN_SLUGS.length - chains.size + (LAYERS.length - layers.size) + (DOMAINS.length - domains.size);
  const reset = () => {
    bulk("chain", true);
    bulk("layer", true);
    bulk("domain", true);
    setQ("");
  };

  // Count lookup for a row; undefined when page.tsx did not pass counts.
  const cnt = (kind: keyof VisibleCounts, slug: string): number | undefined =>
    visibleCounts ? visibleCounts[kind][slug] || 0 : undefined;

  return (
    <aside className={"sidebar" + (open ? " open" : "")}>
      <button className="sb-close" onClick={onClose} aria-label="Close filters">
        ✕
      </button>
      <h1>AI Supply Chain</h1>

      <input
        className="sb-search"
        type="search"
        placeholder="Filter chains, layers…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="sbx-tools">
        <button
          className="sbx-reset"
          onClick={reset}
          disabled={offCount === 0 && !query}
          title="Turn every chain, layer and domain back on"
        >
          ↺ Reset filters
        </button>
        {offCount > 0 && (
          <span className="sbx-off">
            {offCount} filter{offCount === 1 ? "" : "s"} off
          </span>
        )}
      </div>
      <div className="sb-legend">
        <span className="dot" style={{ background: "#7dd3fc" }} /> dot = each item&apos;s color
        in the graph{visibleCounts ? " · number = visible companies" : ""}
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
            count={cnt("chains", r.slug)}
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
            count={cnt("layers", slug)}
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
            count={cnt("domains", slug)}
          />
        ))}
        {domainRows.length === 0 && <div className="sb-empty">no match</div>}
      </Section>

      <Legend />

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
