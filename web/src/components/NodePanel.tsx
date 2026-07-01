"use client";

import { useEffect, useMemo, useState } from "react";
import type { VizNode, Contract, QuarterlyData } from "@/lib/types";
import { buildBadges, buildTimeline, sigDate, FLAG } from "@/lib/signals";
import { GROUP_NAMES, GROUP_COLORS, slugLabel } from "@/lib/taxonomy";
import { fetchJson } from "@/lib/data";
import ReportView from "./ReportView";
import TradingViewChart from "./TradingViewChart";
import LiveQuote from "./LiveQuote";

const US = new Set(["NASDAQ", "NYSE"]);

interface Group {
  company: string;
  relationship: string;
  contracts: Contract[];
}

function groupOutgoing(node: VizNode): Group[] {
  const m = new Map<string, Group>();
  for (const e of node.outgoing) {
    const g = m.get(e.target) || { company: e.target, relationship: e.relationship, contracts: [] };
    g.contracts.push(...(e.contracts || []));
    m.set(e.target, g);
  }
  return [...m.values()].sort((a, b) => b.contracts.length - a.contracts.length);
}
function groupIncoming(node: VizNode): Group[] {
  const m = new Map<string, Group>();
  for (const e of node.incoming) {
    const g = m.get(e.source) || { company: e.source, relationship: e.relationship, contracts: [] };
    g.contracts.push(...(e.contracts || []));
    m.set(e.source, g);
  }
  return [...m.values()].sort((a, b) => b.contracts.length - a.contracts.length);
}

function ContractLine({ c }: { c: Contract }) {
  const meta = [c.units, c.value, c.date_signed, c.type]
    .filter((x) => x && x !== "no specific figure" && x !== "not stated")
    .join(" · ");
  return (
    <div className="deal-contract">
      <div className="deal-sig">{c.signal}</div>
      {meta && <div className="deal-meta">{meta}</div>}
      {c.source && <div className="deal-src">{c.source}</div>}
    </div>
  );
}

export default function NodePanel({
  node,
  glass,
  onClose,
  onNavigate,
}: {
  node: VizNode;
  glass: boolean;
  onClose: () => void;
  onNavigate: (id: string) => void;
}) {
  const [showReport, setShowReport] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [showAllSigs, setShowAllSigs] = useState(false);

  // Reset per-node view state.
  useEffect(() => {
    setShowReport(false);
    setShowAllSigs(false);
  }, [node.id]);

  // Lazy-load the reports bundle once, when a report is first opened.
  useEffect(() => {
    if (!showReport || report) return;
    fetchJson<Record<string, any>>("/data/reports.bundle.json").then((rb) =>
      setReport(rb[node.id] || null)
    );
  }, [showReport, report, node.id]);

  const badges = useMemo(() => buildBadges(node.quarterly_data), [node]);
  const timeline = useMemo(() => buildTimeline(node.quarterly_data), [node]);
  const sigs = useMemo(
    () => [...node.quarterly_data].sort((a, b) => sigDate(b.quarter) - sigDate(a.quarter)),
    [node]
  );
  const customers = useMemo(() => groupOutgoing(node), [node]);
  const suppliers = useMemo(() => groupIncoming(node), [node]);
  const plainSuppliers = suppliers.filter((s) => s.contracts.length === 0).slice(0, 18);
  const dealSuppliers = suppliers.filter((s) => s.contracts.length > 0);

  const isUS = node.exchange && US.has(node.exchange) && node.ticker;
  const accent = GROUP_COLORS[node.primary] || "#94a3b8";

  const shownSigs = showAllSigs ? sigs : sigs.slice(0, 8);

  return (
    <div className="panel-backdrop" onClick={onClose}>
      <div
        className={"panel" + (glass ? " glass" : "")}
        onClick={(e) => e.stopPropagation()}
      >
        {glass && <div className="pacc" style={{ background: accent }} />}
        <button className="panel-close" onClick={onClose} aria-label="Close">
          ✕
        </button>

        <div className="panel-head">
          {node.logo && (
            <span className={"logochip" + (node.logoBg === "dark" ? " dk" : "")}>
              <img src={node.logo} alt="" />
            </span>
          )}
          <h2 className="panel-title">{node.id}</h2>
        </div>

        <div className="panel-meta">
          {node.status === "private" ? (
            <span className="tag">Private</span>
          ) : (
            node.ticker && (
              <span className="tag">
                {node.ticker}
                {node.exchange ? ` · ${node.exchange}` : ""}
              </span>
            )
          )}
          {node.country && <span>{FLAG[node.country] || node.country}</span>}
          {node.lastData ? (
            <span className="muted">
              last data {node.lastData}
              {node.stale ? " · stale" : ""}
            </span>
          ) : (
            <span className="muted">no signals yet</span>
          )}
        </div>

        {isUS ? (
          <TradingViewChart symbol={`${node.exchange}:${node.ticker}`} />
        ) : node.ticker ? (
          <LiveQuote ticker={node.ticker} exchange={node.exchange} />
        ) : null}

        <div className="panel-btns">
          {node.hasReport && (
            <button className="btn" onClick={() => setShowReport((s) => !s)}>
              📊 {showReport ? "Hide" : "Stock"} Report
            </button>
          )}
          {node.hasReport && (
            <button
              className="btn"
              onClick={() =>
                window.open(`/report/${encodeURIComponent(node.id)}`, "_blank", "noopener")
              }
            >
              📄 Download PDF
            </button>
          )}
        </div>

        {showReport && (
          <div className="repbox">
            {report ? <ReportView report={report} /> : <p className="muted">Loading report…</p>}
          </div>
        )}

        {badges.length > 0 && (
          <div className="badge-row">
            {badges.map((b) => (
              <span key={b.key} className="status-badge" style={{ borderColor: b.color, color: b.color }}>
                {b.label}
              </span>
            ))}
          </div>
        )}

        <div className="badge-row">
          {node.layers.map((l) => (
            <span key={l} className="pill filled" style={{ background: GROUP_COLORS[l] }}>
              {GROUP_NAMES[l] || l}
            </span>
          ))}
          {node.domains.map((d) => (
            <span key={d} className="pill filled" style={{ background: GROUP_COLORS[d] }}>
              {GROUP_NAMES[d] || d}
            </span>
          ))}
        </div>
        <div className="badge-row">
          {node.chains.map((c) => (
            <span key={c} className="pill outline">
              {slugLabel(c)}
            </span>
          ))}
        </div>

        {node.products.length > 0 && (
          <div className="prod-cards">
            {node.products.map((p, i) => (
              <div className="prod-card" key={i}>
                <div className="prod-chain">{slugLabel(p.chain)}</div>
                <div className="prod-name">{p.product}</div>
              </div>
            ))}
          </div>
        )}

        <div className="pgrid">
          <div className="pcol">
            {timeline.length > 0 && (
              <>
                <div className="pcol-head">Product / Capacity Timeline</div>
                {timeline.map((t, i) => (
                  <div className="tl-item" key={i}>
                    <span className="tl-when">{t.when}</span>
                    <span>{t.text}</span>
                  </div>
                ))}
              </>
            )}
            {sigs.length > 0 && (
              <>
                <div className="pcol-head" style={{ marginTop: "1rem" }}>
                  Signals
                </div>
                {shownSigs.map((q, i) => (
                  <div className="sig-item" key={i}>
                    <div className="sig-q">{q.quarter}</div>
                    <div className="sig-s">{q.signal}</div>
                    {q.figure && q.figure !== "no specific figure" && (
                      <div className="sig-f">{q.figure}</div>
                    )}
                  </div>
                ))}
                {sigs.length > 8 && (
                  <button className="btn" onClick={() => setShowAllSigs((s) => !s)}>
                    {showAllSigs ? "Show less" : `Show ${sigs.length - 8} more`}
                  </button>
                )}
              </>
            )}
          </div>

          <div className="pcol">
            {customers.length > 0 && (
              <>
                <div className="pcol-head">Customers →</div>
                {customers.map((g) => (
                  <div className="deal-group" key={g.company}>
                    <div className="deal-co" onClick={() => onNavigate(g.company)}>
                      {g.company}
                    </div>
                    <div className="deal-rel">{g.relationship}</div>
                    {g.contracts.map((c, i) => (
                      <ContractLine c={c} key={i} />
                    ))}
                  </div>
                ))}
              </>
            )}
            {(dealSuppliers.length > 0 || plainSuppliers.length > 0) && (
              <>
                <div className="pcol-head" style={{ marginTop: "1rem" }}>
                  ← Suppliers
                </div>
                {dealSuppliers.map((g) => (
                  <div className="deal-group" key={g.company}>
                    <div className="deal-co" onClick={() => onNavigate(g.company)}>
                      {g.company}
                    </div>
                    <div className="deal-rel">{g.relationship}</div>
                    {g.contracts.map((c, i) => (
                      <ContractLine c={c} key={i} />
                    ))}
                  </div>
                ))}
                {plainSuppliers.length > 0 && (
                  <div className="deal-plain">
                    {plainSuppliers.map((s, i) => (
                      <span key={s.company}>
                        <span className="deal-link" onClick={() => onNavigate(s.company)}>
                          {s.company}
                        </span>
                        {i < plainSuppliers.length - 1 ? ", " : ""}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
