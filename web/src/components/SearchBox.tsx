"use client";

import { memo, useEffect, useId, useMemo, useRef, useState } from "react";
import type { VizNode } from "@/lib/types";
import { GROUP_NAMES } from "@/lib/taxonomy";
import { buildSearchIndex, searchNodes, loadRecent, pushRecent, type SearchHit } from "@/lib/search";
// The `.srch-*` styles live in Sidebar.css (this agent's shared stylesheet).
// Next's app router lets any client component import a global CSS file; the
// bundler includes it once no matter how many components import it.
import "./Sidebar.css";

interface Props {
  nodes: VizNode[]; // the companies to search over (pass the VISIBLE ones)
  onPick: (id: string) => void; // called with the node id the user chose
  onClear?: () => void; // optional: called when the ✕ button empties the box
  placeholder?: string;
}

const MAX_ROWS = 10;

// A typeahead search box: type a company name, ticker, product or sector and
// pick a result with the mouse or ↑ ↓ Enter. With an empty query it offers the
// last 8 picks (remembered in localStorage under "aisc.recent").
export default function SearchBox({
  nodes,
  onPick,
  onClear,
  placeholder = "Search company, ticker, product…",
}: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0); // index of the highlighted row
  const [recent, setRecent] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const listId = useId(); // stable ids for the aria wiring (input ↔ listbox ↔ option)

  // localStorage only exists in the browser, so read it after mount — never
  // during render (the server would produce different HTML and React would warn).
  useEffect(() => {
    setRecent(loadRecent());
  }, []);

  // Built once per node list, not per keystroke.
  const index = useMemo(() => buildSearchIndex(nodes), [nodes]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const query = q.trim();
  const rows: SearchHit[] = useMemo(() => {
    if (query) return searchNodes(index, query, MAX_ROWS);
    // Empty query → recent picks, but only the ones still in the current list.
    return recent
      .map((id) => byId.get(id))
      .filter((n): n is VizNode => !!n)
      .map((node) => ({ node, kind: "name" as const, why: null, score: 0 }));
  }, [query, index, recent, byId]);
  const showingRecent = !query && rows.length > 0;

  // Whenever the list changes, highlight its first row again.
  useEffect(() => {
    setActive(0);
  }, [query, rows.length]);

  // Keep the highlighted row scrolled into view while arrowing through a long list.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const pick = (id: string) => {
    setRecent(pushRecent(id));
    setQ(id); // leave the chosen name in the box so the user sees what is focused
    setOpen(false);
    onPick(id);
  };

  const clear = () => {
    setQ("");
    setOpen(false);
    onClear?.();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      else setActive((a) => Math.min(a + 1, Math.max(rows.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      const hit = rows[active] || rows[0];
      if (open && hit) {
        e.preventDefault();
        pick(hit.node.id);
      }
    } else if (e.key === "Escape") {
      if (open) {
        // We consumed this Esc (closing the list) — don't let a modal behind us
        // also react to it.
        e.preventDefault();
        e.stopPropagation();
        setOpen(false);
      } else if (q) {
        clear();
      }
    }
  };

  const activeId = open && rows[active] ? `${listId}-opt-${active}` : undefined;

  return (
    <div className="srch">
      <div className="srch-input-wrap">
        <input
          type="search"
          className="srch-input"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${listId}-list`}
          aria-autocomplete="list"
          aria-activedescendant={activeId}
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={(e) => {
            // Select the text so typing replaces a previous pick instead of appending.
            e.target.select();
            setOpen(true);
          }}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {q && (
          <button
            type="button"
            className="srch-clear"
            aria-label="Clear search"
            // mousedown (not click) so the input does not blur first and swallow it
            onMouseDown={(e) => {
              e.preventDefault();
              clear();
            }}
          >
            ✕
          </button>
        )}
      </div>

      {open && (query || showingRecent) && (
        <div
          className="srch-list"
          id={`${listId}-list`}
          role="listbox"
          ref={listRef}
          // Clicking inside the list must not blur the input (blur closes the list
          // before the row's onClick could fire).
          onMouseDown={(e) => e.preventDefault()}
        >
          {showingRecent && <div className="srch-sec">Recent</div>}
          {rows.length === 0 && <div className="srch-empty">No company matches “{query}”</div>}
          {rows.map((h, i) => (
            <ResultRow
              key={h.node.id}
              id={`${listId}-opt-${i}`}
              idx={i}
              hit={h}
              on={i === active}
              onHover={setActive}
              onPick={pick}
            />
          ))}
          {rows.length > 0 && (
            <div className="srch-kbd">↑ ↓ to move · Enter to open · Esc to close</div>
          )}
        </div>
      )}
    </div>
  );
}

// One result row. memo() so hovering (which re-renders the parent to move the
// highlight) does not re-render every other row.
const ResultRow = memo(function ResultRow({
  id,
  idx,
  hit,
  on,
  onHover,
  onPick,
}: {
  id: string;
  idx: number;
  hit: SearchHit;
  on: boolean;
  onHover: (i: number) => void;
  onPick: (id: string) => void;
}) {
  const n = hit.node;
  const chains = n.chains.length;
  return (
    <button
      type="button"
      id={id}
      role="option"
      aria-selected={on}
      data-idx={idx}
      className={"srch-row" + (on ? " on" : "")}
      onMouseEnter={() => onHover(idx)}
      onClick={() => onPick(n.id)}
    >
      <span className="srch-dot" style={{ background: n.color }} />
      <span className="srch-name">{n.id}</span>
      {n.ticker && <span className="srch-tick">{n.ticker}</span>}
      {hit.kind === "product" && hit.why && (
        <span className="srch-why" title={hit.why}>
          {hit.why}
        </span>
      )}
      <span className="srch-hint">
        {GROUP_NAMES[n.primary] || n.primary}
        {chains > 0 ? ` · ${chains} chain${chains === 1 ? "" : "s"}` : ""}
      </span>
    </button>
  );
});
