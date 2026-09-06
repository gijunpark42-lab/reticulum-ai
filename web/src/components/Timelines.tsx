"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { fetchJson } from "@/lib/data";
import type { Resolver } from "@/lib/company";
import {
  copyToClipboard,
  csvFilename,
  downloadCsv,
  matchesQuery,
  parseIsoDate,
  sortRows,
  toCsv,
  useFlash,
  type SortDir,
} from "@/lib/table";
import CompanyLink from "./CompanyLink";
import CellText from "./CellText";
import "./Tables.css";

// One table inside a topic. Curated tables are hand-written in timelines/;
// derive.py appends one `generated: true` table per topic ("Latest graph
// signals (auto-derived)") with the columns Date, Company, Signal, Figure, Source.
interface TLTable {
  title?: string;
  columns: string[];
  rows: string[][];
  note?: string;
  generated?: boolean;
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
  transitions: "Transitions",
  supply: "Supply",
  optical: "Optical",
  memory: "Memory",
  compute: "Compute",
  manufacturing: "Manufacturing",
  infrastructure: "Infrastructure",
  products: "Products",
};

// "Since" filter for the auto-derived rows (their Date column is YYYY-MM-DD).
const SINCE: { label: string; days: number | null }[] = [
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "180d", days: 180 },
  { label: "All", days: null },
];
// Which generated-table columns can be sorted (the others are prose).
const SORTABLE = new Set(["Date", "Company", "Source"]);
// Fixed column widths for the generated table, by column name.
const GEN_W: Record<string, string> = {
  Date: "9%",
  Company: "13%",
  Signal: "44%",
  Figure: "22%",
  Source: "12%",
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const DAY_MS = 86_400_000;

export default function Timelines({
  resolve,
  onOpen,
}: {
  resolve: Resolver;
  onOpen: (id: string) => void;
}) {
  const [tls, setTls] = useState<Timeline[]>([]);
  const [topicId, setTopicId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [sinceKey, setSinceKey] = useState("All");
  const [groupBy, setGroupBy] = useState(false);
  const [sortCol, setSortCol] = useState(0); // column index in the generated table
  const [sortDir, setSortDir] = useState<SortDir>(-1); // Date desc = newest first
  const [flashed, flash] = useFlash();
  const now = useMemo(() => new Date(), []);

  useEffect(() => {
    fetchJson<Timeline[]>("/data/timelines.bundle.json").then(setTls);
  }, []);

  // Topics in a stable order: by category, then by the hand-set topic order.
  const ordered = useMemo(() => {
    const catIdx = (c: string) => {
      const i = CAT_ORDER.indexOf(c);
      return i < 0 ? 999 : i;
    };
    const tlIdx = (id: string) => {
      const i = TL_ORDER.indexOf(id);
      return i < 0 ? 999 : i;
    };
    return [...tls].sort(
      (a, b) =>
        catIdx(a.category || "other") - catIdx(b.category || "other") ||
        tlIdx(a.id) - tlIdx(b.id)
    );
  }, [tls]);

  // The pill strip: topics grouped under a small category label.
  const pillGroups = useMemo(() => {
    const groups: { cat: string; topics: Timeline[] }[] = [];
    for (const t of ordered) {
      const cat = t.category || "other";
      const last = groups[groups.length - 1];
      if (last && last.cat === cat) last.topics.push(t);
      else groups.push({ cat, topics: [t] });
    }
    return groups;
  }, [ordered]);

  const rowCount = (t: Timeline) => t.tables.reduce((s, tb) => s + tb.rows.length, 0);

  // The selected topic (falls back to the first one until the user picks).
  const topic = useMemo(
    () => ordered.find((t) => t.id === topicId) ?? ordered[0] ?? null,
    [ordered, topicId]
  );

  const sinceDays = SINCE.find((s) => s.label === sinceKey)?.days ?? null;

  // Each table of the topic after the search / since / sort steps.
  // `total` keeps the unfiltered count so the heading can say "12 of 67 rows".
  const views = useMemo(() => {
    if (!topic) return [];
    const q = query.trim();
    const cutoff = sinceDays === null ? null : new Date(now.getTime() - sinceDays * DAY_MS);
    return topic.tables.map((tbl) => {
      let rows = tbl.rows;
      if (tbl.generated) {
        const di = tbl.columns.indexOf("Date");
        if (cutoff && di >= 0)
          rows = rows.filter((r) => {
            const d = parseIsoDate(r[di]);
            return d !== null && d >= cutoff;
          });
      }
      if (q) rows = rows.filter((r) => matchesQuery(r, q));
      if (tbl.generated) {
        const ci = Math.min(sortCol, tbl.columns.length - 1);
        rows = sortRows(rows, (r) => r[ci], sortDir);
      }
      return { tbl, rows, total: tbl.rows.length };
    });
  }, [topic, query, sinceDays, now, sortCol, sortDir]);

  // The auto-derived rows currently on screen — what the CSV export contains.
  const { genRows, genCols } = useMemo(() => {
    const genViews = views.filter((v) => v.tbl.generated);
    return {
      genRows: genViews.flatMap((v) => v.rows),
      genCols: genViews[0]?.tbl.columns ?? [],
    };
  }, [views]);

  const onSort = (ci: number) => {
    if (ci === sortCol) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortCol(ci);
      setSortDir(genCols[ci] === "Date" ? -1 : 1);
    }
  };

  const csvText = () =>
    toCsv(
      genRows,
      genCols.map((c, i) => ({ header: c, get: (r: string[]) => r[i] ?? "" }))
    );
  const copyCsv = async () => {
    const ok = await copyToClipboard(csvText());
    flash(ok ? "csv" : "csv-fail");
  };
  const download = () =>
    downloadCsv(csvFilename(`timeline ${topic?.id ?? ""} signals`), csvText());

  // Group the (already sorted) rows by company, keeping first-appearance
  // order — so with the default newest-first sort, the company with the most
  // recent signal comes first. `latest` is the newest date in each group.
  const groupRows = (rows: string[][], ci: number, di: number) => {
    const order: string[] = [];
    const byCo = new Map<string, string[][]>();
    for (const r of rows) {
      const co = r[ci] ?? "";
      if (!byCo.has(co)) {
        byCo.set(co, []);
        order.push(co);
      }
      byCo.get(co)!.push(r);
    }
    return order.map((co) => {
      const rs = byCo.get(co)!;
      let latest = "";
      if (di >= 0) for (const r of rs) if ((r[di] || "") > latest) latest = r[di];
      return { company: co, rows: rs, latest };
    });
  };

  // One cell of the auto-derived table. Prose columns (Signal, Figure) clamp
  // to 3 lines and expand in place on click; Company opens the NodePanel.
  const genCell = (col: string, cell: string, subject: string) => {
    if (col === "Company")
      return (
        <div className="cell">
          <CompanyLink text={cell} resolve={resolve} onOpen={onOpen} />
        </div>
      );
    if (col === "Date") return <div className="cell tb-nowrap">{cell}</div>;
    if (col === "Source") return <div className="cell tb-src">{cell}</div>;
    return <CellText text={cell} label={col} subject={subject} className="tb-clamp" inline />;
  };

  return (
    <div>
      <h3>📈 Technology &amp; Product Timelines</h3>
      <p className="caption">
        Forward market-size, adoption and launch views — when each technology ramps, how big
        it gets, and which models adopt it. Curated tables are hand-maintained; the
        auto-derived table under each topic is generated from the graph&apos;s latest signals.
      </p>

      {/* Topic pills, grouped by category, each with its total row count. */}
      <div className="tb-pills" role="tablist" aria-label="Timeline topics">
        {pillGroups.map((g) => (
          <Fragment key={g.cat}>
            <span className="tb-pill-cat">{CAT_LABEL[g.cat] || cap(g.cat)}</span>
            {g.topics.map((t) => {
              const curated = t.tables.filter((x) => !x.generated).reduce((s, x) => s + x.rows.length, 0);
              const auto = rowCount(t) - curated;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  className="tb-pill"
                  aria-selected={topic?.id === t.id}
                  onClick={() => setTopicId(t.id)}
                  title={`${curated} curated rows · ${auto} auto-derived signals`}
                >
                  {t.name || t.id}
                  <span className="tb-pill-n">{rowCount(t)}</span>
                </button>
              );
            })}
          </Fragment>
        ))}
      </div>

      {topic && (
        <>
          <div className="tb-toolbar">
            <div className="tb-field tb-search">
              <label className="field-label" htmlFor="tl-q">
                Search this topic
              </label>
              <input
                id="tl-q"
                type="search"
                placeholder="Company, product, figure… (matches every table below)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="tb-field" style={{ flex: "0 0 auto", maxWidth: "none" }}>
              <span className="field-label">Auto-derived rows since</span>
              <div className="tb-seg" role="group" aria-label="Show auto-derived rows since">
                {SINCE.map((s) => (
                  <button
                    key={s.label}
                    type="button"
                    className="tb-btn"
                    aria-pressed={sinceKey === s.label}
                    onClick={() => setSinceKey(s.label)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="tb-actions">
              <button
                type="button"
                className="tb-btn"
                aria-pressed={groupBy}
                onClick={() => setGroupBy((v) => !v)}
                title="Group the auto-derived rows under each company"
              >
                Group by company
              </button>
              <button
                type="button"
                className="tb-btn"
                onClick={copyCsv}
                disabled={genRows.length === 0}
                title="Copy the visible auto-derived rows as CSV"
              >
                {flashed === "csv" ? "Copied ✓" : flashed === "csv-fail" ? "Copy failed" : "Copy CSV"}
              </button>
              <button
                type="button"
                className="tb-btn"
                onClick={download}
                disabled={genRows.length === 0}
                title="Download the visible auto-derived rows as a CSV file"
              >
                Download CSV
              </button>
            </div>
          </div>

          <div className="tb-topic-title">{topic.name || topic.id}</div>
          {topic.source && <div className="caption">Source: {topic.source}</div>}
          {topic.note && <div className="caption">{topic.note}</div>}

          {views.map(({ tbl, rows, total }, ti) => {
            const gen = !!tbl.generated;
            const coIdx = tbl.columns.indexOf("Company");
            const dateIdx = tbl.columns.indexOf("Date");
            // Row keys: date|company|start of signal, de-duplicated within the table.
            const seen = new Map<string, number>();
            const keyOf = (r: string[]) => {
              const base = r.slice(0, 3).join("|").slice(0, 160);
              const n = (seen.get(base) || 0) + 1;
              seen.set(base, n);
              return n > 1 ? `${base}#${n}` : base;
            };
            const renderRow = (r: string[]) => (
              <tr key={keyOf(r)}>
                {r.map((cell, ci) => (
                  <td key={ci} data-label={tbl.columns[ci]}>
                    {gen ? (
                      genCell(tbl.columns[ci], cell, coIdx >= 0 ? r[coIdx] : "")
                    ) : (
                      <div className="cell">
                        {/* Any cell whose whole text names a company in the
                            graph becomes a link to its NodePanel; the rest
                            ("Volume", "2027", a prose detail) stay text. */}
                        <CompanyLink text={cell} resolve={resolve} onOpen={onOpen} />
                      </div>
                    )}
                  </td>
                ))}
              </tr>
            );
            const groups = gen && groupBy && coIdx >= 0 ? groupRows(rows, coIdx, dateIdx) : null;

            return (
              <div key={ti}>
                <div className="tb-table-head">
                  <span className="tb-table-title">
                    {tbl.title || (gen ? "Latest graph signals" : "Table")}
                  </span>
                  <span className={"tb-badge " + (gen ? "auto" : "curated")}>
                    {gen ? "Auto-derived from graph" : "Curated"}
                  </span>
                  <span className="tb-rowcount">
                    {rows.length === total ? `${total} rows` : `${rows.length} of ${total} rows`}
                    {gen && groups ? ` · ${groups.length} companies` : ""}
                  </span>
                </div>
                {rows.length === 0 ? (
                  <div className="tb-empty">
                    No rows match
                    {query.trim() ? ` "${query.trim()}"` : ""}
                    {gen && sinceDays !== null ? ` in the last ${sinceDays} days` : ""}.
                  </div>
                ) : (
                  <div className="tbl-wrap">
                    {/* `tl` marks this as card-stackable on phones (globals.css,
                        max-width: 700px) — 4+ columns squeezed into 350px shreds
                        every word onto its own line. */}
                    <table className={"data tl" + (gen ? " tb-fixed" : "")}>
                      {gen && (
                        <colgroup>
                          {tbl.columns.map((c, ci) => (
                            <col key={ci} style={{ width: GEN_W[c] }} />
                          ))}
                        </colgroup>
                      )}
                      <thead>
                        <tr>
                          {tbl.columns.map((c, ci) =>
                            gen && SORTABLE.has(c) ? (
                              <th
                                key={ci}
                                className={"tb-sortable" + (sortCol === ci ? " active" : "")}
                                aria-sort={
                                  sortCol === ci
                                    ? sortDir === 1
                                      ? "ascending"
                                      : "descending"
                                    : "none"
                                }
                                tabIndex={0}
                                title={`Sort by ${c}`}
                                onClick={() => onSort(ci)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    onSort(ci);
                                  }
                                }}
                              >
                                <span className="th-label">{c}</span>
                                <span className="sort-arrow" aria-hidden="true">
                                  {sortCol === ci ? (sortDir === 1 ? "▲" : "▼") : "↕"}
                                </span>
                              </th>
                            ) : (
                              <th key={ci} className="tb-static">
                                {c}
                              </th>
                            )
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {groups
                          ? groups.map((g) => (
                              <Fragment key={"g:" + g.company}>
                                <tr className="tb-group">
                                  <td colSpan={tbl.columns.length}>
                                    <CompanyLink text={g.company} resolve={resolve} onOpen={onOpen} />
                                    <span className="tb-group-n">
                                      {g.rows.length} {g.rows.length === 1 ? "signal" : "signals"}
                                      {g.latest ? ` · latest ${g.latest}` : ""}
                                    </span>
                                  </td>
                                </tr>
                                {g.rows.map(renderRow)}
                              </Fragment>
                            ))
                          : rows.map(renderRow)}
                      </tbody>
                    </table>
                  </div>
                )}
                {tbl.note && (
                  <div className="caption" style={{ marginTop: "0.3rem" }}>
                    {tbl.note}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
