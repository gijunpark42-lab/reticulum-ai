"use client";

import { useEffect, useMemo, useState } from "react";
import type { VizNode } from "@/lib/types";

// Coverage — the enrichment workflow dashboard. Joins each tracked company's
// next/last earnings-call date (Yahoo, via /api/earnings) with the graph's own
// data freshness (lastData from source labels) to answer: WHAT SHOULD I ENRICH
// NEXT? A call that already happened with no newer data = "enrich now".

interface Earn {
  ts: number | null;
  start: number | null;
  end: number | null;
}

type Status = "due" | "upcoming" | "covered" | "unknown";

interface Row {
  id: string;
  ticker: string;
  call: Date | null;
  status: Status;
  days: number; // days until (upcoming) / since (due, covered); -1 when unknown
  lastData: string | null;
  stale: boolean;
  qd: number;
  node: VizNode;
}

const STATUS_META: Record<Status, { chip: string; cls: string }> = {
  due: { chip: "🔴 Enrich now", cls: "due" },
  upcoming: { chip: "🗓 Upcoming", cls: "up" },
  covered: { chip: "✅ Covered", cls: "ok" },
  unknown: { chip: "—", cls: "na" },
};

const PRIO: Record<Status, number> = { due: 0, upcoming: 1, covered: 2, unknown: 3 };

type Filter = "all" | "due" | "up14" | "stale" | "nodata";
type SortKey = "prio" | "company" | "call" | "last" | "qd";

const fmtDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;

export default function Coverage({
  nodes,
  onSelect,
}: {
  nodes: VizNode[];
  onSelect: (n: VizNode) => void;
}) {
  const [dates, setDates] = useState<Record<string, Earn>>({});
  const [loaded, setLoaded] = useState(false);
  const [apiOk, setApiOk] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("prio");
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [copied, setCopied] = useState<string | null>(null);

  const listed = useMemo(() => nodes.filter((n) => n.ticker), [nodes]);
  const unlisted = nodes.length - listed.length;

  useEffect(() => {
    const companies = listed.map((n) => ({
      id: n.id,
      ticker: n.ticker,
      exchange: n.exchange,
    }));
    if (!companies.length) {
      setLoaded(true);
      return;
    }
    fetch("/api/earnings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ companies }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((j) => {
        setDates(j.dates || {});
        setApiOk(j.authOk !== false);
      })
      .catch(() => setApiOk(false))
      .finally(() => setLoaded(true));
  }, [listed]);

  const rows = useMemo<Row[]>(() => {
    const now = new Date();
    return listed.map((n) => {
      const e = dates[n.id];
      const ts = e?.ts ?? e?.start ?? null;
      const call = ts ? new Date(ts * 1000) : null;
      let status: Status = "unknown";
      let days = -1;
      if (call) {
        const diff = Math.round((call.getTime() - now.getTime()) / 86400e3);
        if (diff >= 0) {
          status = "upcoming";
          days = diff;
        } else {
          days = -diff;
          status = n.lastData && n.lastData >= fmtDate(call) ? "covered" : "due";
        }
      }
      return {
        id: n.id,
        ticker: n.ticker || "—",
        call,
        status,
        days,
        lastData: n.lastData,
        stale: n.stale,
        qd: n.quarterly_data.length,
        node: n,
      };
    });
  }, [listed, dates]);

  const counts = useMemo(
    () => ({
      due: rows.filter((r) => r.status === "due").length,
      up14: rows.filter((r) => r.status === "upcoming" && r.days <= 14).length,
      stale: rows.filter((r) => r.stale).length,
      nodata: rows.filter((r) => r.qd === 0).length,
    }),
    [rows]
  );

  const shown = useMemo(() => {
    const query = q.trim().toLowerCase();
    let out = rows.filter((r) => {
      if (query && !r.id.toLowerCase().includes(query) && !r.ticker.toLowerCase().includes(query))
        return false;
      if (filter === "due") return r.status === "due";
      if (filter === "up14") return r.status === "upcoming" && r.days <= 14;
      if (filter === "stale") return r.stale;
      if (filter === "nodata") return r.qd === 0;
      return true;
    });
    const cmp = (a: Row, b: Row): number => {
      switch (sortKey) {
        case "company":
          return a.id.localeCompare(b.id);
        case "call": {
          const av = a.call?.getTime() ?? Infinity;
          const bv = b.call?.getTime() ?? Infinity;
          return av - bv;
        }
        case "last":
          return (a.lastData || "").localeCompare(b.lastData || "");
        case "qd":
          return a.qd - b.qd;
        default: {
          // priority queue: due (most recent call first) → upcoming (soonest)
          // → covered (most recent) → unknown
          if (PRIO[a.status] !== PRIO[b.status]) return PRIO[a.status] - PRIO[b.status];
          if (a.status === "due" || a.status === "covered") return a.days - b.days;
          if (a.status === "upcoming") return a.days - b.days;
          return a.id.localeCompare(b.id);
        }
      }
    };
    out.sort((a, b) => cmp(a, b) * sortDir);
    return out;
  }, [rows, filter, q, sortKey, sortDir]);

  const onSort = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(k);
      setSortDir(1);
    }
  };

  const copy = (id: string) => {
    const text = `Transcript:${id}`;
    try {
      navigator.clipboard?.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied((c) => (c === id ? null : c)), 1400);
    } catch {}
  };

  const stat = (f: Filter, label: string, n: number, cls: string) => (
    <button
      className={"cov-stat " + cls + (filter === f ? " on" : "")}
      onClick={() => setFilter(filter === f ? "all" : f)}
    >
      <b>{n}</b> {label}
    </button>
  );

  const HEADERS: { key: SortKey | null; label: string }[] = [
    { key: "company", label: "Company" },
    { key: null, label: "Ticker" },
    { key: "call", label: "Earnings call" },
    { key: "prio", label: "Status" },
    { key: "last", label: "Last data" },
    { key: "qd", label: "Signals" },
    { key: null, label: "Enrich" },
  ];

  return (
    <div>
      <h3>📡 Coverage</h3>
      <p className="caption">
        The enrichment queue: each company&apos;s next / most recent earnings call (Yahoo
        Finance) joined with the freshness of its data in the graph. A call that already
        happened with no newer data = <b>Enrich now</b> — the 📋 button copies the{" "}
        <code>Transcript:&lt;company&gt;</code> command for Claude Code.
        {unlisted > 0 && <> {unlisted} private/unlisted companies not shown.</>}
      </p>

      {!apiOk && loaded && (
        <p className="caption" style={{ color: "#d29922" }}>
          ⚠ Earnings dates unavailable right now (Yahoo auth failed) — showing coverage from
          graph data only.
        </p>
      )}

      <div className="cov-stats">
        {stat("due", "enrich now", counts.due, "due")}
        {stat("up14", "upcoming ≤14d", counts.up14, "up")}
        {stat("stale", "stale (180d)", counts.stale, "st")}
        {stat("nodata", "no signals", counts.nodata, "na")}
        <span className="cov-total">{rows.length} listed companies tracked</span>
      </div>

      <div className="row" style={{ margin: "0.6rem 0 0.8rem" }}>
        <div className="grow" style={{ maxWidth: 340 }}>
          <input
            type="search"
            placeholder="Search company or ticker…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      {!loaded && <div className="spinner">Loading earnings dates…</div>}

      {loaded && (
        <div className="tbl-wrap">
          <table className="data screener coverage">
            <colgroup>
              <col style={{ width: "20%" }} />
              <col style={{ width: "10%" }} />
              <col style={{ width: "17%" }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "15%" }} />
            </colgroup>
            <thead>
              <tr>
                {HEADERS.map((h) => (
                  <th
                    key={h.label}
                    className={h.key && sortKey === h.key ? "active" : ""}
                    style={h.key ? undefined : { cursor: "default" }}
                    onClick={h.key ? () => onSort(h.key!) : undefined}
                  >
                    <span className="th-label">{h.label}</span>
                    {h.key && (
                      <span className="sort-arrow">
                        {sortKey === h.key ? (sortDir === 1 ? "▲" : "▼") : "↕"}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} onClick={() => onSelect(r.node)} style={{ cursor: "pointer" }}>
                  <td data-label="Company" className="co">
                    <div className="cell">{r.id}</div>
                  </td>
                  <td data-label="Ticker">
                    <div className="cell nowrap">{r.ticker}</div>
                  </td>
                  <td data-label="Earnings call">
                    <div className="cell nowrap">
                      {r.call ? (
                        <>
                          {fmtDate(r.call)}{" "}
                          <span className="muted">
                            {r.status === "upcoming"
                              ? r.days === 0
                                ? "· today"
                                : `· in ${r.days}d`
                              : `· ${r.days}d ago`}
                          </span>
                        </>
                      ) : (
                        "—"
                      )}
                    </div>
                  </td>
                  <td data-label="Status">
                    <div className="cell nowrap">
                      <span className={"cov-chip " + STATUS_META[r.status].cls}>
                        {STATUS_META[r.status].chip}
                      </span>
                    </div>
                  </td>
                  <td data-label="Last data">
                    <div className="cell nowrap">
                      {r.lastData || "—"}
                      {r.stale && <span title="no data in 180d"> 💤</span>}
                    </div>
                  </td>
                  <td data-label="Signals">
                    <div className="cell nowrap">{r.qd}</div>
                  </td>
                  <td data-label="Enrich">
                    <div className="cell nowrap">
                      <button
                        className="copy-btn"
                        title={`Copy "Transcript:${r.id}"`}
                        onClick={(e) => {
                          e.stopPropagation();
                          copy(r.id);
                        }}
                      >
                        {copied === r.id ? "✓ copied" : "📋 Transcript"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loaded && (
        <p className="caption" style={{ marginTop: "0.6rem" }}>
          {shown.length} shown · dates from Yahoo Finance (best-effort; refreshed ~6h) ·
          &quot;Covered&quot; = the graph has data on or after the call date.
        </p>
      )}
    </div>
  );
}
