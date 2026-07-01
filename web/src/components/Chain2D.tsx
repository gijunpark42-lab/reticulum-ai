"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/data";
import { slugLabel } from "@/lib/taxonomy";

interface ChainIndexEntry {
  id: string;
  company: string;
  chain_focus: string;
}

// NOTE: full SVG layer-band / bezier-edge rendering is ported in a later step.
// This interim view loads the chain index + selected chain so the tab is wired.
export default function Chain2D({ glass }: { glass: boolean }) {
  const [index, setIndex] = useState<ChainIndexEntry[]>([]);
  const [sel, setSel] = useState<string>("");

  useEffect(() => {
    fetchJson<ChainIndexEntry[]>("/data/chains/index.json").then((idx) => {
      setIndex(idx);
      if (idx.length) setSel(idx[0].id);
    });
  }, []);

  const cur = index.find((c) => c.id === sel);

  return (
    <div>
      <div className="row" style={{ marginBottom: "0.9rem" }}>
        <div className="grow" style={{ maxWidth: 420 }}>
          <label className="field-label">Chain</label>
          <select value={sel} onChange={(e) => setSel(e.target.value)}>
            {index.map((c) => (
              <option key={c.id} value={c.id}>
                {slugLabel(c.id)}
              </option>
            ))}
          </select>
        </div>
        {cur && (
          <div className="caption">
            <b style={{ color: "var(--ap-text)" }}>{cur.company}</b> — {cur.chain_focus}
          </div>
        )}
      </div>
      <div
        className="graph-wrap"
        style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <p className="muted">Chain 2D layer map — being ported to React SVG (next step).</p>
      </div>
    </div>
  );
}
