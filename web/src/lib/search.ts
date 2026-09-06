// search.ts — typeahead matching for the company SearchBox.
//
// Pure functions, no React: build an index ONCE from the VizNode list, then rank
// a query against it on every keystroke. Kept separate from the component so the
// ranking can be unit-tested (or reused by another view) without rendering.
//
// Ranking, best first:
//   0  company name STARTS with the query        ("nvi"   -> NVIDIA)
//   1  a WORD inside the name starts with it     ("hynix" -> SK Hynix)
//   2  the name CONTAINS it anywhere             ("micro" -> Supermicro)
//   3  the ticker starts with it                 ("2382"  -> Quanta, "nvda" -> NVIDIA)
//   4  a product or sector text contains it      ("hbm4"  -> SK Hynix, Samsung, Micron)
// Ties inside one tier go to the better-connected node (higher degree), then A→Z.

import type { VizNode } from "./types";

// Lowercase, strip accents, collapse anything that is not a letter/digit into a
// single space. "Résonac (Showa Denko)" -> "resonac showa denko".
export function normalize(s: string): string {
  return (s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // the accents NFD split off (U+0300..U+036F)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export interface IndexedNode {
  node: VizNode;
  name: string; // normalized company name
  ticker: string; // normalized full ticker ("2382 tw")
  tickerBase: string; // ticker without its Yahoo suffix ("2382")
  products: string[]; // original product strings (for the "why it matched" hint)
  sectors: string[]; // original sector strings
  text: string; // normalized products + sectors joined — one string to search
}

export type MatchKind = "name" | "ticker" | "product";

export interface SearchHit {
  node: VizNode;
  kind: MatchKind; // what the query matched — the row shows a hint for non-name hits
  why: string | null; // the product/sector text that matched (kind === "product")
  score: number; // tier number, lower = better
}

export function buildSearchIndex(nodes: VizNode[]): IndexedNode[] {
  return nodes.map((node) => {
    const products: string[] = [];
    for (const p of node.products || []) {
      if (p.product && !products.includes(p.product)) products.push(p.product);
    }
    const sectors = (node.sectors || []).filter(Boolean);
    const ticker = normalize(node.ticker || "");
    return {
      node,
      name: normalize(node.id),
      ticker,
      tickerBase: ticker.split(" ")[0] || "",
      products,
      sectors,
      text: normalize([...products, ...sectors].join(" | ")),
    };
  });
}

export function searchNodes(index: IndexedNode[], query: string, limit = 10): SearchHit[] {
  const q = normalize(query);
  if (!q) return [];
  const hits: SearchHit[] = [];
  for (const it of index) {
    let tier = -1;
    let kind: MatchKind = "name";
    let why: string | null = null;
    if (it.name.startsWith(q)) tier = 0;
    else if (it.name.includes(" " + q)) tier = 1;
    else if (it.name.includes(q)) tier = 2;
    else if (it.tickerBase && (it.tickerBase.startsWith(q) || it.ticker.startsWith(q))) {
      tier = 3;
      kind = "ticker";
    } else if (it.text.includes(q)) {
      tier = 4;
      kind = "product";
      // Find the human-readable text that matched, so the row can say why.
      why =
        it.products.find((p) => normalize(p).includes(q)) ||
        it.sectors.find((s) => normalize(s).includes(q)) ||
        null;
    }
    if (tier < 0) continue;
    hits.push({ node: it.node, kind, why, score: tier });
  }
  hits.sort(
    (a, b) =>
      a.score - b.score ||
      b.node.degree - a.node.degree ||
      a.node.id.localeCompare(b.node.id)
  );
  return hits.slice(0, limit);
}

// ── Recent picks (localStorage) ────────────────────────────────────────────
// The last 8 companies the user picked, newest first. Every localStorage call is
// wrapped in try/catch: it throws in private windows / SSR / when storage is full,
// and a search box must never crash the page over a nicety.

const RECENT_KEY = "aisc.recent";
const RECENT_MAX = 8;

export function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr)
      ? arr.filter((x): x is string => typeof x === "string").slice(0, RECENT_MAX)
      : [];
  } catch {
    return [];
  }
}

export function pushRecent(id: string): string[] {
  const next = [id, ...loadRecent().filter((x) => x !== id)].slice(0, RECENT_MAX);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {}
  return next;
}
