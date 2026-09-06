"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { VizNode } from "@/lib/types";
import { fetchJson } from "@/lib/data";
import { GROUP_NAMES, LAYER_ORDER, DOMAIN_ORDER, slugLabel } from "@/lib/taxonomy";
import {
  AGING_DAYS,
  FRESH_DAYS,
  FRESHNESS_LABEL,
  copyToClipboard,
  csvFilename,
  downloadCsv,
  formatAge,
  freshnessBucket,
  matchesQuery,
  readStorage,
  sortRows,
  toCsv,
  useFlash,
  writeStorage,
  type CsvColumn,
  type Freshness,
  type SortDir,
} from "@/lib/table";
import CellText, { type CellDetail } from "./CellText";
import "./Tables.css";

// One company's entry in company_metrics.json — derive.py's output on top of
// the curated baseline. The five text "slots" are the screener's columns.
interface Metric {
  revenue_growth?: string;
  guidance?: string;
  backlog_or_b2b?: string;
  supply_status?: string;
  next_catalyst?: string;
  asof?: string;
}

// The row the table renders: the metrics plus what the graph node knows.
interface Row {
  company: string;
  ticker: string; // "" when the graph has no ticker (rendered as "—")
  exchange: string;
  layer: string; // primary layer / domain, display name
  growth: string;
  guidance: string;
  backlog: string;
  supply: string;
  catalyst: string;
  asof: string; // YYYY-MM-DD — the source call date
  fresh: Freshness; // derived from asof: drives the colour and the hide-stale filter
  days: number | null; // age of asof in days
  hasNode: boolean; // company exists in the graph → the name opens its NodePanel
}

// Only the text fields are columns (fresh/days/hasNode are helpers).
type ColKey =
  | "company"
  | "ticker"
  | "exchange"
  | "layer"
  | "growth"
  | "guidance"
  | "backlog"
  | "supply"
  | "catalyst"
  | "asof";

interface Col {
  key: ColKey;
  label: string;
  w: number; // relative width — normalised across the columns currently shown
  nowrap?: boolean;
  bold?: boolean;
  offByDefault?: boolean;
}

const COLS: Col[] = [
  { key: "company", label: "Company", w: 13, bold: true },
  { key: "ticker", label: "Ticker", w: 8, nowrap: true },
  // Off by default: nine columns squeeze every cell on a laptop; it stays in the Columns menu.
  { key: "exchange", label: "Exchange", w: 8, nowrap: true, offByDefault: true },
  { key: "layer", label: "Layer", w: 10, offByDefault: true },
  { key: "growth", label: "Growth", w: 15 },
  { key: "guidance", label: "Guidance", w: 16 },
  { key: "backlog", label: "Backlog / B2B", w: 14 },
  { key: "supply", label: "Supply status", w: 13 },
  { key: "catalyst", label: "Next catalyst", w: 15 },
  { key: "asof", label: "As of", w: 10, nowrap: true },
];
const DEFAULT_COLS: ColKey[] = COLS.filter((c) => !c.offByDefault).map((c) => c.key);

// Column choices and the hide-stale toggle are remembered per browser.
const PREFS_KEY = "tb.screener.v1";
interface Prefs {
  cols: ColKey[];
  hideStale: boolean;
}

// The export always has the same shape, whatever columns are on screen:
// company, ticker, exchange, the five slots, as-of.
const CSV_COLS: CsvColumn<Row>[] = [
  { header: "Company", get: (r) => r.company },
  { header: "Ticker", get: (r) => r.ticker },
  { header: "Exchange", get: (r) => r.exchange },
  { header: "Revenue growth", get: (r) => r.growth },
  { header: "Guidance", get: (r) => r.guidance },
  { header: "Backlog / B2B", get: (r) => r.backlog },
  { header: "Supply status", get: (r) => r.supply },
  { header: "Next catalyst", get: (r) => r.catalyst },
  { header: "As of", get: (r) => r.asof },
];

export default function Screener({
  byId,
  onOpen,
}: {
  byId: Map<string, VizNode>;
  // Every screener row is keyed by a graph node id, so the company cell can open
  // the NodePanel directly — no name resolution needed here.
  onOpen: (id: string) => void;
}) {
  const [metrics, setMetrics] = useState<Record<string, Metric>>({});
  const [gLayer, setGLayer] = useState("All");
  const [gSector, setGSector] = useState("All");
  const [gChain, setGChain] = useState("All");
  const [query, setQuery] = useState("");
  const [hideStale, setHideStale] = useState(false);
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(() => new Set(DEFAULT_COLS));
  const [sortKey, setSortKey] = useState<ColKey>("asof");
  const [sortDir, setSortDir] = useState<SortDir>(-1);
  const [flashed, flash] = useFlash();
  const menuRef = useRef<HTMLDetailsElement>(null);
  // One clock for the whole visit, so every row is bucketed the same way.
  const now = useMemo(() => new Date(), []);

  useEffect(() => {
    fetchJson<Record<string, Metric>>("/data/company_metrics.json").then((m) => {
      // `_schema` documents the columns; it is not a company.
      const { _schema, ...rest } = m as Record<string, Metric>;
      void _schema;
      setMetrics(rest);
    });
  }, []);

  // Load remembered preferences once, then save on every change (skipping the
  // very first run, which would otherwise overwrite them with the defaults
  // before they have loaded).
  useEffect(() => {
    const p = readStorage<Prefs>(PREFS_KEY);
    if (!p) return;
    const valid = (p.cols || []).filter((k) => COLS.some((c) => c.key === k));
    if (valid.length) setVisibleCols(new Set<ColKey>(["company", ...valid]));
    setHideStale(!!p.hideStale);
  }, []);
  const firstSave = useRef(true);
  useEffect(() => {
    if (firstSave.current) {
      firstSave.current = false;
      return;
    }
    const p: Prefs = { cols: [...visibleCols], hideStale };
    writeStorage(PREFS_KEY, p);
  }, [visibleCols, hideStale]);

  // The column menu is a <details>; close it when clicking anywhere else.
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      const m = menuRef.current;
      if (m?.open && !m.contains(e.target as Node)) m.open = false;
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
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

  // Step 1 — every company, with its graph facts and freshness worked out once.
  const allRows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const [name, m] of Object.entries(metrics)) {
      const n = byId.get(name);
      const { bucket, days } = freshnessBucket(m.asof, now);
      const primary = n ? n.layers[0] || n.domains[0] || "" : "";
      out.push({
        company: name,
        ticker: n?.ticker || "",
        exchange: n?.exchange || "",
        layer: primary ? GROUP_NAMES[primary] || primary : "",
        growth: m.revenue_growth || "",
        guidance: m.guidance || "",
        backlog: m.backlog_or_b2b || "",
        supply: m.supply_status || "",
        catalyst: m.next_catalyst || "",
        asof: m.asof || "",
        fresh: bucket,
        days,
        hasNode: !!n,
      });
    }
    return out;
  }, [metrics, byId, now]);

  // Step 2 — every filter EXCEPT hide-stale, so the legend can still count
  // how many stale rows the toggle is hiding.
  const filtered = useMemo(() => {
    const q = query.trim();
    const anyGraphFilter = gLayer !== "All" || gSector !== "All" || gChain !== "All";
    return allRows.filter((r) => {
      const n = byId.get(r.company);
      if (anyGraphFilter && !n) return false;
      if (n) {
        if (gLayer !== "All" && !n.layers.includes(gLayer) && !n.domains.includes(gLayer))
          return false;
        if (gSector !== "All" && !n.sectors.includes(gSector)) return false;
        if (gChain !== "All" && !n.chains.includes(gChain)) return false;
      }
      if (
        q &&
        !matchesQuery(
          [r.company, r.ticker, r.exchange, r.layer, r.growth, r.guidance, r.backlog, r.supply, r.catalyst, r.asof],
          q
        )
      )
        return false;
      return true;
    });
  }, [allRows, byId, gLayer, gSector, gChain, query]);

  const freshCounts = useMemo(() => {
    const c: Record<Freshness, number> = { fresh: 0, aging: 0, stale: 0, unknown: 0 };
    for (const r of filtered) c[r.fresh]++;
    return c;
  }, [filtered]);

  // Step 3 — the rows on screen: hide-stale applied, then sorted.
  const rows = useMemo(() => {
    const kept = hideStale ? filtered.filter((r) => r.fresh !== "stale") : filtered;
    return sortRows(kept, (r) => r[sortKey], sortDir);
  }, [filtered, hideStale, sortKey, sortDir]);

  // Columns currently shown, with widths re-normalised so they always fill 100%.
  const cols = useMemo(() => COLS.filter((c) => visibleCols.has(c.key)), [visibleCols]);
  const wSum = cols.reduce((s, c) => s + c.w, 0);

  // A screener cell holds the COMPACT text (`figure` when there is one, else the
  // signal) that derive.py picked for the column. The paragraph it came from is
  // still on the graph node, so find it and let the dialog show the whole thing —
  // that is the part the 3-line clamp throws away. Curated baseline rows have no
  // matching graph entry; they simply get no extra block.
  const detailFor = (company: string, value: string): CellDetail | undefined => {
    if (!value) return undefined;
    const qd = byId.get(company)?.quarterly_data;
    const hit = qd?.find((q) => q.figure === value || q.signal === value);
    return hit ? { source: hit.quarter, signal: hit.signal } : undefined;
  };

  const onSort = (k: ColKey) => {
    if (k === sortKey) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(k);
      setSortDir(k === "asof" ? -1 : 1); // dates: newest first; text: A→Z
    }
  };

  const toggleCol = (k: ColKey) =>
    setVisibleCols((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  // ── Export (visible rows only) ────────────────────────────────────────
  const copyCsv = async () => {
    const ok = await copyToClipboard(toCsv(rows, CSV_COLS));
    flash(ok ? "csv" : "csv-fail");
  };
  const download = () => downloadCsv(csvFilename("screener"), toCsv(rows, CSV_COLS));
  const copyTickers = async () => {
    // Comma list for a watchlist import; companies without a ticker are skipped.
    const tickers = [...new Set(rows.map((r) => r.ticker).filter(Boolean))];
    const ok = await copyToClipboard(tickers.join(", "));
    flash(ok ? "tickers" : "tickers-fail");
  };
  // Button text: momentary "Copied ✓" / "Copy failed" feedback, else the label.
  const btnText = (key: string, label: string) =>
    flashed === key ? "Copied ✓" : flashed === `${key}-fail` ? "Copy failed" : label;

  const hiddenStale = hideStale ? freshCounts.stale : 0;
  const tickerCount = new Set(rows.map((r) => r.ticker).filter(Boolean)).size;

  return (
    <div>
      <h3>🔎 Company Screener</h3>
      <p className="caption">
        Headline operational metrics per company — no share prices, just signals. Filter by
        layer, sector, chain or text; click a column header to sort. The &quot;As of&quot;
        colour is the age of the source call: green ≤{FRESH_DAYS} days, amber ≤{AGING_DAYS},
        red older.
      </p>

      <div className="tb-toolbar">
        <div className="tb-field">
          <label className="field-label" htmlFor="scr-layer">
            Layer / Domain
          </label>
          <select id="scr-layer" value={gLayer} onChange={(e) => setGLayer(e.target.value)}>
            <option value="All">All</option>
            {groupOpts.map((g) => (
              <option key={g} value={g}>
                {GROUP_NAMES[g] || g}
              </option>
            ))}
          </select>
        </div>
        <div className="tb-field">
          <label className="field-label" htmlFor="scr-sector">
            Sector
          </label>
          <select id="scr-sector" value={gSector} onChange={(e) => setGSector(e.target.value)}>
            <option value="All">All</option>
            {sectorOpts.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="tb-field">
          <label className="field-label" htmlFor="scr-chain">
            Chain
          </label>
          <select id="scr-chain" value={gChain} onChange={(e) => setGChain(e.target.value)}>
            <option value="All">All</option>
            {chainOpts.map((c) => (
              <option key={c} value={c}>
                {slugLabel(c)}
              </option>
            ))}
          </select>
        </div>
        <div className="tb-field tb-search">
          <label className="field-label" htmlFor="scr-q">
            Search
          </label>
          <input
            id="scr-q"
            type="search"
            placeholder="Company, ticker, or any word in the metrics…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="tb-actions">
          <button
            type="button"
            className="tb-btn"
            aria-pressed={hideStale}
            onClick={() => setHideStale((v) => !v)}
            title={`Hide companies whose latest source is older than ${AGING_DAYS} days`}
          >
            Hide stale
          </button>
          <details className="tb-menu" ref={menuRef}>
            <summary className="tb-btn" title="Show or hide columns">
              Columns ▾
            </summary>
            <div className="tb-menu-panel" role="group" aria-label="Show or hide columns">
              {COLS.filter((c) => c.key !== "company").map((c) => (
                <label key={c.key} className="tb-check">
                  <input
                    type="checkbox"
                    checked={visibleCols.has(c.key)}
                    onChange={() => toggleCol(c.key)}
                  />
                  {c.label}
                </label>
              ))}
              <button
                type="button"
                className="tb-link"
                onClick={() => setVisibleCols(new Set(DEFAULT_COLS))}
              >
                Reset to default
              </button>
            </div>
          </details>
          <button
            type="button"
            className="tb-btn"
            onClick={copyTickers}
            disabled={tickerCount === 0}
            title="Copy the visible rows' tickers as a comma-separated list (for a watchlist)"
          >
            {btnText("tickers", `Copy tickers (${tickerCount})`)}
          </button>
          <button
            type="button"
            className="tb-btn"
            onClick={copyCsv}
            disabled={rows.length === 0}
            title="Copy the visible rows as CSV"
          >
            {btnText("csv", "Copy CSV")}
          </button>
          <button
            type="button"
            className="tb-btn"
            onClick={download}
            disabled={rows.length === 0}
            title="Download the visible rows as a CSV file"
          >
            Download CSV
          </button>
        </div>
      </div>

      <div className="tb-summary">
        <span>
          Showing <strong>{rows.length}</strong> of {allRows.length} companies
          {hiddenStale > 0 && <> · {hiddenStale} stale hidden</>}
        </span>
        <span className="tb-legend" aria-label="Freshness of the visible rows">
          <span title={FRESHNESS_LABEL.fresh}>
            <span className="tb-dot fresh" aria-hidden="true" />
            {freshCounts.fresh} fresh
          </span>
          <span title={FRESHNESS_LABEL.aging}>
            <span className="tb-dot aging" aria-hidden="true" />
            {freshCounts.aging} aging
          </span>
          <span title={FRESHNESS_LABEL.stale}>
            <span className="tb-dot stale" aria-hidden="true" />
            {freshCounts.stale} stale
          </span>
        </span>
      </div>

      <div className="tbl-wrap">
        <table className="data screener">
          <colgroup>
            {cols.map((c) => (
              <col key={c.key} style={{ width: `${((c.w / wSum) * 100).toFixed(2)}%` }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {cols.map((c) => (
                <th
                  key={c.key}
                  className={"tb-sortable" + (sortKey === c.key ? " active" : "")}
                  aria-sort={
                    sortKey === c.key ? (sortDir === 1 ? "ascending" : "descending") : "none"
                  }
                  tabIndex={0}
                  title={`Sort by ${c.label}`}
                  onClick={() => onSort(c.key)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSort(c.key);
                    }
                  }}
                >
                  <span className="th-label">{c.label}</span>
                  <span className="sort-arrow" aria-hidden="true">
                    {sortKey === c.key ? (sortDir === 1 ? "▲" : "▼") : "↕"}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={cols.length} className="tb-empty">
                  No companies match the current filters.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.company}>
                {cols.map((c) => (
                  <td key={c.key} data-label={c.label} className={c.bold ? "co" : ""}>
                    {c.key === "company" ? (
                      <div className="cell" title={r.hasNode ? `Open ${r.company}` : undefined}>
                        {r.hasNode ? (
                          <button
                            type="button"
                            className="co-link"
                            onClick={() => onOpen(r.company)}
                          >
                            {r.company}
                          </button>
                        ) : (
                          r.company
                        )}
                      </div>
                    ) : c.key === "asof" ? (
                      <div
                        className={`cell tb-asof ${r.fresh}`}
                        title={
                          r.asof
                            ? `${FRESHNESS_LABEL[r.fresh]} — source dated ${r.asof} (${formatAge(r.days)})`
                            : "No source date"
                        }
                      >
                        <span className={`tb-dot ${r.fresh}`} aria-hidden="true" />
                        {r.asof || "—"}
                        {r.days !== null && <span className="tb-age">{formatAge(r.days)}</span>}
                      </div>
                    ) : (
                      <CellText
                        text={r[c.key] || "—"}
                        label={c.label}
                        subject={r.company}
                        className={c.nowrap ? "nowrap" : undefined}
                        detail={detailFor(r.company, r[c.key])}
                      />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption" style={{ marginTop: "0.6rem" }}>
        {rows.length} companies shown · {Object.keys(metrics).length} total in
        company_metrics.json · exports include the visible rows only
      </p>
    </div>
  );
}
