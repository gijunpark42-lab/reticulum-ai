"use client";

import { useEffect, useMemo, useState } from "react";
import type { VizNode } from "@/lib/types";
import { fetchJson } from "@/lib/data";
import { GROUP_NAMES, LAYER_ORDER, DOMAIN_ORDER, slugLabel } from "@/lib/taxonomy";

interface Metric {
  revenue_growth?: string;
  guidance?: string;
  backlog_or_b2b?: string;
  supply_status?: string;
  next_catalyst?: string;
  asof?: string;
}

interface Row {
  company: string;
  ticker: string;
  growth: string;
  guidance: string;
  backlog: string;
  supply: string;
  catalyst: string;
  asof: string;
}

const COLS: { key: keyof Row; label: string }[] = [
  { key: "company", label: "Company" },
  { key: "ticker", label: "Ticker" },
  { key: "growth", label: "Growth" },
  { key: "guidance", label: "Guidance" },
  { key: "backlog", label: "Backlog / B2B" },
  { key: "supply", label: "Supply status" },
  { key: "catalyst", label: "Next catalyst" },
  { key: "asof", label: "As of" },
];

export default function Screener({ byId }: { byId: Map<string, VizNode> }) {
  const [metrics, setMetrics] = useState<Record<string, Metric>>({});
  const [gLayer, setGLayer] = useState("All");
  const [gSector, setGSector] = useState("All");
  const [gChain, setGChain] = useState("All");
  const [sortKey, setSortKey] = useState<keyof Row>("asof");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);

  useEffect(() => {
    fetchJson<Record<string, Metric>>("/data/company_metrics.json").then((m) => {
      const { _schema, ...rest } = m as any;
      setMetrics(rest);
    });
  }, []);

  // Options for the filters, derived from the graph nodes that have metrics.
  const { groupOpts, sectorOpts, chainOpts } = useMemo(() => {
    const groups = new Set<string>();
    const sectors = new Set<string>();
    const chns = new Set<string>();
    for (const name of Object.keys(metrics)) {
      const n = byId.get(name);
      if (!n) continue;
      n.layers.forEach((l) => groups.add(l));
      n.domains.forEach((d) => groups.add(d));
      n.sectors.forEach((s) => sectors.add(s));
      n.chains.forEach((c) => chns.add(c));
    }
    const order = (s: string) =>
      s in LAYER_ORDER ? LAYER_ORDER[s] : 100 + (DOMAIN_ORDER[s] ?? 0);
    return {
      groupOpts: [...groups].sort((a, b) => order(a) - order(b)),
      sectorOpts: [...sectors].sort((a, b) => a.localeCompare(b)),
      chainOpts: [...chns].sort((a, b) => a.localeCompare(b)),
    };
  }, [metrics, byId]);

  const rows = useMemo(() => {
    const out: Row[] = [];
    for (const [name, m] of Object.entries(metrics)) {
      const n = byId.get(name);
      const anyFilter = gLayer !== "All" || gSector !== "All" || gChain !== "All";
      if (anyFilter && !n) continue;
      if (n) {
        if (gLayer !== "All" && !n.layers.includes(gLayer) && !n.domains.includes(gLayer))
          continue;
        if (gSector !== "All" && !n.sectors.includes(gSector)) continue;
        if (gChain !== "All" && !n.chains.includes(gChain)) continue;
      }
      out.push({
        company: name,
        ticker: n?.ticker || "—",
        growth: m.revenue_growth || "",
        guidance: m.guidance || "",
        backlog: m.backlog_or_b2b || "",
        supply: m.supply_status || "",
        catalyst: m.next_catalyst || "",
        asof: m.asof || "",
      });
    }
    out.sort((a, b) => {
      const av = a[sortKey] || "";
      const bv = b[sortKey] || "";
      return av < bv ? -sortDir : av > bv ? sortDir : 0;
    });
    return out;
  }, [metrics, byId, gLayer, gSector, gChain, sortKey, sortDir]);

  const onSort = (k: keyof Row) => {
    if (k === sortKey) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(k);
      setSortDir(k === "asof" ? -1 : 1);
    }
  };

  return (
    <div>
      <h3>🔎 Company Screener</h3>
      <p className="caption">
        Headline operational metrics per company — no share prices, just signals. Filter by
        layer, sector, or chain; click a column header to sort.
      </p>

      <div className="row" style={{ margin: "1rem 0" }}>
        <div className="grow" style={{ maxWidth: 260 }}>
          <label className="field-label">Layer / Domain</label>
          <select value={gLayer} onChange={(e) => setGLayer(e.target.value)}>
            <option value="All">All</option>
            {groupOpts.map((g) => (
              <option key={g} value={g}>
                {GROUP_NAMES[g] || g}
              </option>
            ))}
          </select>
        </div>
        <div className="grow" style={{ maxWidth: 260 }}>
          <label className="field-label">Sector</label>
          <select value={gSector} onChange={(e) => setGSector(e.target.value)}>
            <option value="All">All</option>
            {sectorOpts.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="grow" style={{ maxWidth: 260 }}>
          <label className="field-label">Chain</label>
          <select value={gChain} onChange={(e) => setGChain(e.target.value)}>
            <option value="All">All</option>
            {chainOpts.map((c) => (
              <option key={c} value={c}>
                {slugLabel(c)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="tbl-wrap">
        <table className="data">
          <thead>
            <tr>
              {COLS.map((c) => (
                <th key={c.key} onClick={() => onSort(c.key)}>
                  {c.label}
                  {sortKey === c.key && (
                    <span className="sort-arrow">{sortDir === 1 ? "▲" : "▼"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.company}>
                <td style={{ fontWeight: 600, whiteSpace: "nowrap" }}>{r.company}</td>
                <td>{r.ticker}</td>
                <td>{r.growth}</td>
                <td>{r.guidance}</td>
                <td>{r.backlog}</td>
                <td>{r.supply}</td>
                <td>{r.catalyst}</td>
                <td style={{ whiteSpace: "nowrap" }}>{r.asof}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption" style={{ marginTop: "0.6rem" }}>
        {rows.length} companies with curated metrics · {Object.keys(metrics).length} total in
        company_metrics.json
      </p>
    </div>
  );
}
