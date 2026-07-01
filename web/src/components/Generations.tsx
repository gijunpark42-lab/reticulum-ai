"use client";

import { useMemo, useState } from "react";
import type { VizNode } from "@/lib/types";
import {
  TRANSITIONS,
  computeTransition,
  type GenStatus,
  type TransitionRow,
} from "@/lib/transitions";
import { GROUP_COLORS, GROUP_NAMES, slugLabel } from "@/lib/taxonomy";

interface Props {
  nodes: VizNode[];
  byId: Map<string, VizNode>;
  onSelect: (n: VizNode) => void;
}

const STATUS_META: Record<GenStatus, { icon: string; title: string; cls: string; note: string }> = {
  retained: {
    icon: "✅",
    title: "Retained",
    cls: "retained",
    note: "in both generations — watch the content delta",
  },
  gained: {
    icon: "📈",
    title: "New in next gen",
    cls: "gained",
    note: "won a socket it didn't have in the current generation",
  },
  lost: {
    icon: "⚠️",
    title: "Not in next gen",
    cls: "lost",
    note: "lost the socket — or not yet added to the new chain",
  },
};

function RowLine({ r, byId, onSelect }: { r: TransitionRow; byId: Props["byId"]; onSelect: Props["onSelect"] }) {
  const changed = r.productFrom && r.productTo && r.productFrom !== r.productTo;
  return (
    <div
      className="gen-row"
      onClick={() => {
        const n = byId.get(r.id);
        if (n) onSelect(n);
      }}
      title={GROUP_NAMES[r.primary] || r.primary}
    >
      <span className="dot" style={{ background: GROUP_COLORS[r.primary] || "#94a3b8" }} />
      <div>
        <div className="gen-name">{r.id}</div>
        <div className="gen-prod">
          {r.status === "retained" &&
            (changed ? (
              <>
                {r.productFrom} <span className="gen-arrow">→</span> {r.productTo}
              </>
            ) : (
              r.productTo || r.productFrom
            ))}
          {r.status === "gained" && (
            <>
              {r.productTo}
              {r.toChains.length > 0 && (
                <span className="gen-chains"> · {r.toChains.map(slugLabel).join(" · ")}</span>
              )}
            </>
          )}
          {r.status === "lost" && r.productFrom}
        </div>
      </div>
    </div>
  );
}

export default function Generations({ nodes, byId, onSelect }: Props) {
  const [sel, setSel] = useState(TRANSITIONS[0].key);

  const results = useMemo(
    () => new Map(TRANSITIONS.map((t) => [t.key, computeTransition(nodes, t)])),
    [nodes]
  );
  const cur = results.get(sel)!;

  const buckets: GenStatus[] = ["gained", "retained", "lost"];

  return (
    <div>
      <h3>🔀 Generation Transitions</h3>
      <p className="caption">
        Who keeps, gains, or loses a socket when an accelerator platform moves to its next
        generation — and how the content changes (HBM3E → HBM4, copper → optical, …). Computed
        from the curated chains; click a company for details.
      </p>

      <div className="gen-picker">
        {TRANSITIONS.map((t) => {
          const r = results.get(t.key)!;
          return (
            <button
              key={t.key}
              className={"gen-pick" + (sel === t.key ? " on" : "")}
              onClick={() => setSel(t.key)}
            >
              <span className="gen-pick-vendor">{t.vendor}</span>
              <span className="gen-pick-label">{t.short}</span>
              <span className="gen-pick-counts">
                <em className="g">📈{r.counts.gained}</em>
                <em className="r">✅{r.counts.retained}</em>
                <em className="l">⚠️{r.counts.lost}</em>
              </span>
            </button>
          );
        })}
      </div>

      <p className="caption" style={{ margin: "0.4rem 0 0.8rem" }}>
        <b style={{ color: "var(--ap-text)" }}>{cur.t.label}</b> — {cur.rows.length} companies
        across both generations.
      </p>

      <div className="gen-grid">
        {buckets.map((st) => {
          const meta = STATUS_META[st];
          const rows = cur.rows.filter((r) => r.status === st);
          return (
            <div key={st} className={"gen-col " + meta.cls}>
              <div className="gen-col-head">
                {meta.icon} {meta.title} ({rows.length})
              </div>
              <div className="gen-col-note">{meta.note}</div>
              {rows.map((r) => (
                <RowLine key={r.id} r={r} byId={byId} onSelect={onSelect} />
              ))}
              {rows.length === 0 && <div className="gen-empty">none</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
