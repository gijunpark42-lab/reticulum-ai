"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

export interface CellDetail {
  /** Source label the value came from, e.g. "Analog Devices Q3 FY2026 (08-19-2026)". */
  source?: string;
  /** The full signal paragraph behind the compact figure the table shows. */
  signal?: string;
}

/**
 * A table cell whose text CSS clamps to 1-3 lines (`.cell` in globals.css).
 *
 * The clamp keeps the tables dense, but the tail it cuts off is often where the
 * useful detail sits — you see "Rev $4.02B (+40% YoY); GM 72.5%; op margin…" and
 * the rest is gone. So this measures the clamp and, ONLY when the text is really
 * cut off, turns the cell into something you can open: the cell gets a "⋯" mark,
 * a zoom cursor, and click / Enter reveals the whole value in a dialog.
 *
 * A cell that already fits keeps zero chrome — no marks on a table of short cells.
 *
 * The DOM stays exactly `<div class="cell">…</div>` so every existing rule (the
 * clamp itself, the mobile card layout, `.cb-source`) keeps applying unchanged.
 */
export default function CellText({
  text,
  label,
  subject,
  detail,
  className,
  children,
}: {
  /** Plain text of the cell — also the dialog body. */
  text: string;
  /** Column name, shown as a chip in the dialog ("Guidance"). */
  label: string;
  /** Row subject, usually the company name, shown as the dialog title. */
  subject?: string;
  /** Optional richer source behind the value. */
  detail?: CellDetail;
  /** Extra classes for the cell div (e.g. "nowrap", "cb-source"). */
  className?: string;
  /** Rendered instead of `text` when the cell holds markup (a company link). */
  children?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [clipped, setClipped] = useState(false);
  const [open, setOpen] = useState(false);

  // A cell is clipped when its content is taller than the box (line-clamp) or
  // wider than it (nowrap + ellipsis). Re-measure on resize: the same cell fits
  // on a wide screen and overflows on a narrow one, and the tables are fluid.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () =>
      setClipped(el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [text]);

  // Esc closes, like the node panel.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const cls = ["cell", className, clipped ? "clipped" : ""].filter(Boolean).join(" ");

  return (
    <>
      <div
        ref={ref}
        className={cls}
        // Only a clipped cell is interactive. `title` still carries the full text
        // for a plain mouse hover — the dialog is for reading it properly.
        title={clipped ? text : undefined}
        role={clipped ? "button" : undefined}
        tabIndex={clipped ? 0 : undefined}
        aria-label={clipped ? `Show full ${label}${subject ? " for " + subject : ""}` : undefined}
        onClick={(e) => {
          if (!clipped) return;
          // A company link inside the cell owns its own click (it opens the node
          // panel), so never hijack it.
          if ((e.target as HTMLElement).closest("button, a")) return;
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (!clipped) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        {children ?? text}
      </div>

      {open && <CellDialog {...{ text, label, subject, detail }} onClose={() => setOpen(false)} />}
    </>
  );
}

/**
 * The reader. Rendered into <body> through a portal: the tables live inside
 * `.tbl-wrap`, which is an `overflow: auto` box, and a dialog rendered inside it
 * would be clipped and would scroll with the table.
 */
function CellDialog({
  text,
  label,
  subject,
  detail,
  onClose,
}: {
  text: string;
  label: string;
  subject?: string;
  detail?: CellDetail;
  onClose: () => void;
}) {
  // The portal target only exists in the browser, so mount before rendering.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  if (!ready) return null;

  // Only worth a second block when the underlying signal says more than the
  // figure already on screen.
  const extra = detail?.signal && detail.signal.trim() !== text.trim() ? detail.signal : null;

  return createPortal(
    <div className="cell-backdrop" onClick={onClose} role="presentation">
      <div
        className="cell-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`${subject ? subject + " — " : ""}${label}`}
        onClick={(e) => e.stopPropagation()}
      >
        <button className="panel-close" onClick={onClose} aria-label="Close">
          ✕
        </button>
        <div className="cell-modal-head">
          {subject && <span className="cell-modal-subject">{subject}</span>}
          <span className="tag">{label}</span>
        </div>
        <p className="cell-modal-body">{text}</p>
        {extra && (
          <div className="cell-modal-detail">
            <div className="cell-modal-detail-h">
              Full signal
              {/* The source label is a proper name ("NVIDIA Q1 FY2027 …"); the
                  heading is uppercased, so it rides in its own normal-case span. */}
              {detail?.source && <span className="cell-modal-src">{detail.source}</span>}
            </div>
            <p>{extra}</p>
          </div>
        )}
        {!extra && detail?.source && (
          <div className="cell-modal-detail-h" style={{ marginTop: "0.9rem" }}>
            Source
            <span className="cell-modal-src">{detail.source}</span>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
