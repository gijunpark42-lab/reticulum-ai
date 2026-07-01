"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "@/lib/data";

interface TLTable {
  title?: string;
  columns: string[];
  rows: string[][];
  note?: string;
}
interface Timeline {
  id: string;
  name?: string;
  category?: string;
  source?: string;
  note?: string;
  tables: TLTable[];
}

const TL_ORDER = [
  "cpo", "optical_speed", "silicon_photonics", "ocs", "hbm", "nand_storage",
  "cpu", "foundry", "power_cooling", "product_launches",
];
const CAT_ORDER = [
  "transitions", "supply", "optical", "memory", "compute", "manufacturing",
  "infrastructure", "products",
];
const CAT_LABEL: Record<string, string> = {
  transitions: "🔀 Transitions",
  supply: "🌡️ Supply Tightness",
  optical: "Optical",
  memory: "Memory",
  compute: "Compute",
  manufacturing: "Manufacturing",
  infrastructure: "Infrastructure",
  products: "Products",
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export default function Timelines() {
  const [tls, setTls] = useState<Timeline[]>([]);
  const [cat, setCat] = useState<string>("");

  useEffect(() => {
    fetchJson<Timeline[]>("/data/timelines.bundle.json").then(setTls);
  }, []);

  const ordered = useMemo(() => {
    const idx = (id: string) => {
      const i = TL_ORDER.indexOf(id);
      return i < 0 ? 999 : i;
    };
    return [...tls].sort((a, b) => idx(a.id) - idx(b.id));
  }, [tls]);

  const byCat = useMemo(() => {
    const m: Record<string, Timeline[]> = {};
    for (const t of ordered) (m[t.category || "other"] ||= []).push(t);
    return m;
  }, [ordered]);

  const cats = useMemo(() => {
    const present = Object.keys(byCat);
    return [
      ...CAT_ORDER.filter((c) => present.includes(c)),
      ...present.filter((c) => !CAT_ORDER.includes(c)),
    ];
  }, [byCat]);

  useEffect(() => {
    if (cats.length && !cats.includes(cat)) setCat(cats[0]);
  }, [cats, cat]);

  return (
    <div>
      <h3>📈 Technology &amp; Product Timelines</h3>
      <p className="caption">
        Forward market-size, adoption and launch views — when each technology ramps, how big
        it gets, and which models adopt it. A separate layer from the supply graph.
      </p>

      <div className="tabs" role="tablist" style={{ marginTop: "1rem" }}>
        {cats.map((c) => (
          <button
            key={c}
            className="tab"
            role="tab"
            aria-selected={cat === c}
            onClick={() => setCat(c)}
          >
            {CAT_LABEL[c] || cap(c)}
          </button>
        ))}
      </div>

      {(byCat[cat] || []).map((tl, i) => (
        <div key={tl.id}>
          {i > 0 && <hr className="sep" />}
          <div
            style={{
              color: "#7dd3fc",
              fontWeight: 700,
              fontSize: "1.18rem",
              letterSpacing: "-0.01em",
              margin: "0.3rem 0 0.15rem",
            }}
          >
            {tl.name || tl.id}
          </div>
          {tl.source && <div className="caption">Source: {tl.source}</div>}
          {tl.note && <div className="caption">{tl.note}</div>}
          {tl.tables.map((tbl, ti) => (
            <div key={ti} style={{ marginTop: "0.7rem" }}>
              {tbl.title && (
                <div
                  style={{
                    color: "#aab4c2",
                    fontWeight: 700,
                    fontSize: "0.97rem",
                    letterSpacing: "0.2px",
                    margin: "0.7rem 0 0.15rem",
                  }}
                >
                  {tbl.title}
                </div>
              )}
              <div className="tbl-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      {tbl.columns.map((c, ci) => (
                        <th key={ci} style={{ cursor: "default" }}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tbl.rows.map((r, ri) => (
                      <tr key={ri}>
                        {r.map((cell, ci) => (
                          <td key={ci}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {tbl.note && <div className="caption" style={{ marginTop: "0.3rem" }}>{tbl.note}</div>}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
