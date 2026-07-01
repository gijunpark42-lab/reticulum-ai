"use client";

import { CHAIN_COLORS, LAYERS, DOMAINS, slugLabel } from "@/lib/taxonomy";

interface Props {
  glass: boolean;
  setGlass: (v: boolean) => void;
  chains: Set<string>;
  layers: Set<string>;
  domains: Set<string>;
  toggle: (kind: "chain" | "layer" | "domain", slug: string) => void;
  dimStale: boolean;
  setDimStale: (v: boolean) => void;
}

function Check({
  checked,
  onChange,
  color,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  color?: string;
  label: string;
}) {
  return (
    <label className="check-row">
      <input type="checkbox" checked={checked} onChange={onChange} />
      {color && <span className="dot" style={{ background: color }} />}
      <span>{label}</span>
    </label>
  );
}

export default function Sidebar({
  glass,
  setGlass,
  chains,
  layers,
  domains,
  toggle,
  dimStale,
  setDimStale,
}: Props) {
  const chainKeys = Object.keys(CHAIN_COLORS);
  return (
    <aside className="sidebar">
      <h1>AI Supply Chain</h1>

      <label className="check-row" style={{ marginTop: "0.6rem" }}>
        <input type="checkbox" checked={glass} onChange={() => setGlass(!glass)} />
        <span>✨ Liquid Glass</span>
      </label>

      <hr className="sep" />

      <div className="side-section">
        <div className="side-head">Chains</div>
        {chainKeys.map((slug) => (
          <Check
            key={slug}
            checked={chains.has(slug)}
            onChange={() => toggle("chain", slug)}
            color={CHAIN_COLORS[slug]}
            label={slugLabel(slug)}
          />
        ))}
      </div>

      <details className="side-expander">
        <summary>Layers</summary>
        {LAYERS.map(([slug, name, color]) => (
          <Check
            key={slug}
            checked={layers.has(slug)}
            onChange={() => toggle("layer", slug)}
            color={color}
            label={name}
          />
        ))}
      </details>

      <details className="side-expander">
        <summary>Domains</summary>
        {DOMAINS.map(([slug, name, color]) => (
          <Check
            key={slug}
            checked={domains.has(slug)}
            onChange={() => toggle("domain", slug)}
            color={color}
            label={name}
          />
        ))}
      </details>

      <hr className="sep" />

      <Check
        checked={dimStale}
        onChange={() => setDimStale(!dimStale)}
        label="Dim stale nodes (no data 180d)"
      />
    </aside>
  );
}
