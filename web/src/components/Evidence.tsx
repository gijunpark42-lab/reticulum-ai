"use client";

// Evidence.tsx — a tiny "source" pill next to a data point. Click it and the passage of
// the transcript / filing that backs the number unfolds inline, with the match
// highlighted. Records come from /data/evidence.json (written by evidence.py); the file
// is fetched lazily, on the first click anywhere on the page, and only once.
//
// Usage (NodePanel signal row):
//   <EvidenceButton kind="qd" company={node.id} label={q.quarter} signal={q.signal} />
// Usage (contract on the edge company -> target):
//   <EvidenceButton kind="contract" company={company} target={target} label={c.source} signal={c.signal} />

import { useEffect, useId, useState, type MouseEvent } from "react";
import {
  entryKey,
  loadEvidence,
  type EvidenceEntry,
  type EvidenceKind,
  type EvidenceRef,
} from "@/lib/evidence";
import "./Evidence.css";

export interface EvidenceButtonProps {
  kind: EvidenceKind;
  company: string;
  target?: string; // omit (or "") for quarterly_data entries
  label: string;
  signal: string;
}

// The excerpt marks the match as «…». Split on that and render the inside as <mark>.
// (The corpus contains no guillemets of its own, so the split is unambiguous.)
function renderExcerpt(excerpt: string) {
  const parts = excerpt.split(/«([^»]*)»/); // odd indices = matched text
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <mark className="ev-hit" key={i}>
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

function statusLine(entry: EvidenceEntry): { text: string; tone: "" | "ev-warn" | "ev-miss" } {
  if (entry.status === "no_source") {
    return { text: "Source text is not on disk for this label", tone: "ev-miss" };
  }
  if (entry.status === "no_match") {
    return { text: "Number not found in source — flagged for review", tone: "ev-warn" };
  }
  if (entry.via === "number") {
    return { text: "Number located in the source text", tone: "" };
  }
  if (entry.via === "counterparty") {
    return { text: "Counterparty named in the source text (no number to check)", tone: "" };
  }
  return { text: "Signal wording located in the source text (no number to check)", tone: "" };
}

function EvidenceBody({ entry }: { entry: EvidenceEntry }) {
  const status = statusLine(entry);
  return (
    <>
      <span className={"ev-status " + status.tone}>{status.text}</span>
      {entry.unmatched && entry.unmatched.length > 0 && entry.status !== "no_match" && (
        <span className="ev-status ev-warn">
          Not found in source: {entry.unmatched.join(", ")}
        </span>
      )}
      {entry.excerpt && (
        <>
          {entry.status === "no_match" && <span className="ev-status">Nearest passage:</span>}
          <span className="ev-excerpt">{renderExcerpt(entry.excerpt)}</span>
        </>
      )}
      {entry.doc && <code className="ev-doc">{entry.doc}</code>}
    </>
  );
}

export function EvidenceButton({ kind, company, target = "", label, signal }: EvidenceButtonProps) {
  const [open, setOpen] = useState(false);
  // undefined = not looked up yet, null = looked up but no record for this key
  const [entry, setEntry] = useState<EvidenceEntry | null | undefined>(undefined);
  const boxId = useId();

  const toggle = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // rows inside the panel may have their own click handlers
    const next = !open;
    setOpen(next);
    if (next && entry === undefined) {
      const key = entryKey(kind, company, target, label, signal);
      loadEvidence().then((map) => setEntry(map.get(key) ?? null));
    }
  };

  return (
    <span className="ev">
      <button
        type="button"
        className={"ev-pill" + (open ? " ev-open" : "")}
        aria-expanded={open}
        aria-controls={boxId}
        title="Show the source passage"
        onClick={toggle}
      >
        source
      </button>
      {open && (
        <span className="ev-box" id={boxId} role="region" aria-label="Source evidence" aria-busy={entry === undefined}>
          {entry === undefined && <span className="ev-status">Loading source…</span>}
          {entry === null && (
            <span className="ev-status ev-warn">
              No evidence record for this entry yet — run evidence.py and sync.
            </span>
          )}
          {entry && <EvidenceBody entry={entry} />}
        </span>
      )}
    </span>
  );
}

// Optional: one-line tally for a list of entries ("Sources: 12 located · 2 flagged · 1 no text").
// `entries` are plain refs; nothing is fetched until the component mounts.
export function EvidenceSummary({ entries }: { entries: EvidenceRef[] }) {
  const [counts, setCounts] = useState<{ found: number; no_match: number; no_source: number; missing: number } | null>(null);

  useEffect(() => {
    let alive = true;
    loadEvidence().then((map) => {
      if (!alive) return;
      const c = { found: 0, no_match: 0, no_source: 0, missing: 0 };
      for (const ref of entries) {
        const rec = map.get(entryKey(ref.kind, ref.company, ref.target, ref.label, ref.signal));
        if (!rec) c.missing += 1;
        else c[rec.status] += 1;
      }
      setCounts(c);
    });
    return () => {
      alive = false;
    };
  }, [entries]);

  if (!counts || entries.length === 0) return null;
  const parts = [`${counts.found} located`];
  if (counts.no_match) parts.push(`${counts.no_match} flagged`);
  if (counts.no_source) parts.push(`${counts.no_source} no source text`);
  if (counts.missing) parts.push(`${counts.missing} not indexed`);
  return <span className="ev-summary">Sources: {parts.join(" · ")}</span>;
}

export default EvidenceButton;
