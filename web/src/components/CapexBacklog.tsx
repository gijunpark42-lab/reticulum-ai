"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/data";

// Capex & Backlog — the money view of the AI buildout. One side of the tab is
// what the buyers SPEND (capex, the top-of-funnel demand signal for every
// supplier below them in the graph); the other is what they have already SOLD
// (backlog / RPO / contracted revenue). All figures are hand-curated from
// earnings sources in chains/ — the component just renders capex_backlog.json.

interface Tile {
  label: string;
  value: string;
  delta?: string;
  detail?: string;
  source?: string;
}
interface CapexBar {
  name: string;
  busd: number;
  display: string;
  period?: string;
  metric?: string;
  growth?: string;
  detail?: string;
  source?: string;
}
interface BarBlock {
  title: string;
  unit: string;
  note?: string;
  bars: CapexBar[];
}
interface GroupRow {
  name: string;
  capex_q: string;
  capex_year: string;
  backlog: string;
  signal: string;
  source: string;
}
interface Group {
  title: string;
  rows: GroupRow[];
}
interface CapexBacklogData {
  updated: string;
  note?: string;
  tiles: Tile[];
  capex_bars: BarBlock;
  backlog_bars: BarBlock;
  groups: Group[];
  footnote?: string;
}

const COLS = ["Company", "Capex (latest qtr)", "Capex (annual / funding)", "Backlog / contracted", "Key signal", "Source"];

function BarChart({ block, color }: { block: BarBlock; color: string }) {
  const max = Math.max(...block.bars.map((b) => b.busd));
  return (
    <div className="cb-chart">
      <div className="cb-chart-title">{block.title}</div>
      {block.note && <div className="caption">{block.note}</div>}
      <div className="cb-bars">
        {block.bars.map((b) => {
          // Bars scale linearly to the widest, with 112px reserved so the
          // value label always fits to the right of the longest bar.
          const frac = b.busd / max;
          const sub = b.period || b.metric || "";
          const tip = [
            `${b.name} — ${b.display}${sub ? ` (${sub})` : ""}`,
            b.growth,
            b.detail,
            b.source ? `Source: ${b.source}` : "",
          ]
            .filter(Boolean)
            .join("\n");
          return (
            <div className="cb-row" key={b.name} title={tip}>
              <div className="cb-label">
                <span className="cb-name">{b.name}</span>
                {sub && <span className="cb-sub">{sub}</span>}
              </div>
              <div className="cb-track">
                <div
                  className="cb-bar"
                  style={{ width: `calc((100% - 112px) * ${frac.toFixed(4)})`, background: color }}
                />
                <span className="cb-val">
                  {b.display}
                  {b.growth && <span className="cb-growth"> {b.growth}</span>}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function CapexBacklog() {
  const [data, setData] = useState<CapexBacklogData | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<CapexBacklogData>("/data/capex_backlog.json")
      .then(setData)
      .catch((e) => setErr(e?.message || String(e)));
  }, []);

  if (err)
    return (
      <p className="caption">
        Failed to load capex_backlog.json — run <code>npm run sync</code>. ({err})
      </p>
    );
  if (!data) return <div className="spinner">Loading capex &amp; backlog…</div>;

  return (
    <div>
      <h3>💰 Capex &amp; Backlog</h3>
      <p className="caption">
        What the AI buildout&apos;s buyers spend (capex — the demand signal for every
        supplier below them) and what they have already sold (backlog / RPO / contracted
        revenue). Hyperscalers and neoclouds, from earnings sources only. Updated{" "}
        {data.updated}.
      </p>

      <div className="cb-tiles">
        {data.tiles.map((t) => (
          <div
            className="cb-tile"
            key={t.label}
            title={[t.detail, t.source ? `Source: ${t.source}` : ""].filter(Boolean).join("\n")}
          >
            <div className="cb-tile-label">{t.label}</div>
            <div className="cb-tile-value">{t.value}</div>
            {t.delta && <div className="cb-tile-delta">{t.delta}</div>}
          </div>
        ))}
      </div>

      <div className="cb-charts">
        <BarChart block={data.capex_bars} color="#2997ff" />
        <BarChart block={data.backlog_bars} color="#2ea852" />
      </div>

      {data.groups.map((g) => (
        <div key={g.title} style={{ marginTop: "1.4rem" }}>
          <div className="cb-group-title">{g.title}</div>
          <div className="tbl-wrap">
            <table className="data screener capexbacklog">
              <thead>
                <tr>
                  {COLS.map((c) => (
                    <th key={c} style={{ cursor: "default" }}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {g.rows.map((r) => (
                  <tr key={r.name}>
                    <td data-label="Company" className="co">
                      <div className="cell">{r.name}</div>
                    </td>
                    <td data-label="Capex (latest qtr)">
                      <div className="cell">{r.capex_q}</div>
                    </td>
                    <td data-label="Capex (annual / funding)">
                      <div className="cell">{r.capex_year}</div>
                    </td>
                    <td data-label="Backlog / contracted">
                      <div className="cell">{r.backlog}</div>
                    </td>
                    <td data-label="Key signal">
                      <div className="cell">{r.signal}</div>
                    </td>
                    <td data-label="Source">
                      <div className="cell cb-source">{r.source}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {data.footnote && (
        <p className="caption" style={{ marginTop: "0.8rem" }}>
          {data.footnote}
        </p>
      )}
    </div>
  );
}
