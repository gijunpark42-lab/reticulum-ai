// chain2d.ts — build the {columns, edges} model for the Chain 2D layer map, and
// an imperative SVG renderer ported (near 1:1) from app.py's CHAIN2D_TEMPLATE.
//
// Two builders feed the SAME renderer:
//   buildFromChain(chain)  — one curated chain file (preserves sector nesting)
//   buildFromMerged(graph) — ALL value chains at once (grouped by primary layer)

import type { MergedGraph, GraphNode } from "./types";
import {
  LAYERS, DOMAINS, LAYER_ORDER, LAYER_NAMES, LAYER_COLORS, DOMAIN_NAMES, DOMAIN_COLORS,
} from "./taxonomy";

export interface C2DPlayer {
  c: string; p: string; qd: number; ext: number; row: number; sec: string; sub: string;
}
export interface C2DHeader { label: string; sub: number; row: number; }
export interface C2DColumn {
  slug: string; name: string; color: string;
  kind: "layer" | "domain" | "external";
  players: C2DPlayer[]; headers: C2DHeader[]; nrows: number;
}
export interface C2DEdge {
  ci: number; pi: number; cj: number; pj: number; rel: string; nc: number; contracts: any[];
}
export interface C2DData { columns: C2DColumn[]; edges: C2DEdge[]; }

// ── Builder 1: a single curated chain file ──────────────────────────────────
function buildColumn(slug: string, name: string, color: string, kind: C2DColumn["kind"], group: any) {
  const players: C2DPlayer[] = [];
  const headers: C2DHeader[] = [];
  const raw: any[] = [];
  let row = 0;
  for (const sec of group.sectors || []) {
    headers.push({ label: sec.sector || "", sub: 0, row });
    row++;
    for (const ss of sec.sub_sectors || []) {
      headers.push({ label: ss.sub_sector || "", sub: 1, row });
      row++;
      for (const p of ss.players || []) {
        players.push({
          c: p.company, p: p.product || "", qd: (p.quarterly_data || []).length,
          ext: 0, row, sec: sec.sector || "", sub: ss.sub_sector || "",
        });
        raw.push(p);
        row++;
      }
    }
    for (const p of sec.players || []) {
      players.push({
        c: p.company, p: p.product || "", qd: (p.quarterly_data || []).length,
        ext: 0, row, sec: sec.sector || "", sub: "",
      });
      raw.push(p);
      row++;
    }
  }
  return { col: { slug, name, color, kind, players, headers, nrows: row } as C2DColumn, raw };
}

export function buildFromChain(chain: any): C2DData {
  const cols: C2DColumn[] = [];
  const raws: any[][] = [];

  const layerGroups: Record<string, any> = {};
  for (const g of chain.flow || []) if (g.layer) layerGroups[g.layer] = g;
  for (const slug of Object.keys(layerGroups).sort(
    (a, b) => (LAYER_ORDER[a] ?? 999) - (LAYER_ORDER[b] ?? 999)
  )) {
    const { col, raw } = buildColumn(slug, LAYER_NAMES[slug] || slug, LAYER_COLORS[slug] || "#94a3b8", "layer", layerGroups[slug]);
    cols.push(col);
    raws.push(raw);
  }

  const domOrder: Record<string, number> = Object.fromEntries(DOMAINS.map((d, i) => [d[0], i]));
  const domGroups: Record<string, any> = {};
  for (const g of chain.domains || []) if (g.domain) domGroups[g.domain] = g;
  for (const slug of Object.keys(domGroups).sort(
    (a, b) => (domOrder[a] ?? 999) - (domOrder[b] ?? 999)
  )) {
    const { col, raw } = buildColumn(slug, DOMAIN_NAMES[slug] || slug, DOMAIN_COLORS[slug] || "#94a3b8", "domain", domGroups[slug]);
    cols.push(col);
    raws.push(raw);
  }

  const pos: Record<string, [number, number]> = {};
  cols.forEach((col, ci) => col.players.forEach((pl, pi) => {
    if (!(pl.c in pos)) pos[pl.c] = [ci, pi];
  }));

  const ext: Record<string, number> = {};
  const pending: [number, number, [string | number, number], any][] = [];
  raws.forEach((raw, ci) =>
    raw.forEach((p, pi) =>
      (p.connects_to || []).forEach((e: any) => {
        const tgtCo = e.company;
        if (tgtCo === p.company) return;
        let tgt = pos[tgtCo] as [string | number, number] | undefined;
        if (!tgt) {
          if (!(tgtCo in ext)) ext[tgtCo] = Object.keys(ext).length;
          tgt = ["EXT", ext[tgtCo]];
        }
        pending.push([ci, pi, tgt, e]);
      })
    )
  );

  if (Object.keys(ext).length) {
    const extPlayers: C2DPlayer[] = Object.entries(ext)
      .sort((a, b) => a[1] - b[1])
      .map(([co, i]) => ({ c: co, p: "appears in another chain", qd: 0, ext: 1, row: i, sec: "", sub: "" }));
    cols.push({ slug: "external", name: "External", color: "#475569", kind: "external", players: extPlayers, headers: [], nrows: extPlayers.length });
  }
  const extCi = cols.length - 1;

  const edges: C2DEdge[] = [];
  for (const [ci, pi, tgt, e] of pending) {
    const [cj, pj] = tgt[0] === "EXT" ? [extCi, tgt[1] as number] : (tgt as [number, number]);
    const contracts = e.contracts || [];
    edges.push({ ci, pi, cj, pj, rel: e.relationship || "", nc: contracts.length, contracts });
  }

  return { columns: cols, edges };
}

// ── Builder 2: ALL chains merged (one big layered map from merged_graph) ─────
export function buildFromMerged(graph: MergedGraph): C2DData {
  const primaryOf = (n: GraphNode) =>
    (n.layers && n.layers[0]) || (n.domains && n.domains[0]) || "other";

  const byGroup: Record<string, GraphNode[]> = {};
  for (const n of graph.nodes) (byGroup[primaryOf(n)] ||= []).push(n);

  const cols: C2DColumn[] = [];
  const pos: Record<string, [number, number]> = {};

  const pushCol = (slug: string, name: string, color: string, kind: C2DColumn["kind"]) => {
    const ns = byGroup[slug];
    if (!ns || !ns.length) return;
    ns.sort((a, b) =>
      (a.sectors[0] || "").localeCompare(b.sectors[0] || "") || a.id.localeCompare(b.id)
    );
    const players: C2DPlayer[] = [];
    const headers: C2DHeader[] = [];
    let row = 0;
    let prevSec: string | null = null;
    for (const n of ns) {
      const sec = n.sectors[0] || "";
      if (sec && sec !== prevSec) {
        headers.push({ label: sec, sub: 0, row });
        row++;
        prevSec = sec;
      }
      players.push({
        c: n.id, p: n.products[0]?.product || "", qd: (n.quarterly_data || []).length,
        ext: 0, row, sec, sub: "",
      });
      row++;
    }
    const ci = cols.length;
    cols.push({ slug, name, color, kind, players, headers, nrows: row });
    players.forEach((pl, pi) => {
      if (!(pl.c in pos)) pos[pl.c] = [ci, pi];
    });
  };

  for (const [slug, name, color] of LAYERS) pushCol(slug, name, color, "layer");
  for (const [slug, name, color] of DOMAINS) pushCol(slug, name, color, "domain");
  pushCol("other", "Other", "#94a3b8", "layer");

  const edges: C2DEdge[] = [];
  for (const e of graph.edges) {
    const s = pos[e.source];
    const t = pos[e.target];
    if (!s || !t) continue;
    edges.push({
      ci: s[0], pi: s[1], cj: t[0], pj: t[1],
      rel: e.relationship || "", nc: (e.contracts || []).length, contracts: e.contracts || [],
    });
  }

  return { columns: cols, edges };
}

// ── Imperative SVG renderer (ported from CHAIN2D_TEMPLATE JS) ────────────────
const NS = "http://www.w3.org/2000/svg";
const esc = (s: string) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;");

export function renderChain2D(
  svg: SVGSVGElement,
  tipEl: HTMLElement,
  epanelEl: HTMLElement,
  data: C2DData,
  totalWidth: number
): void {
  svg.innerHTML = "";
  tipEl.style.display = "none";
  epanelEl.style.display = "none";
  epanelEl.innerHTML = "";

  const cols: any[] = data.columns;

  // flatten into node/edge lists keyed by "colIdx|playerIdx"
  const nodes: any[] = [];
  const idx: Record<string, any> = {};
  cols.forEach((col, ci) =>
    col.players.forEach((p: any, pi: number) => {
      const k = ci + "|" + pi;
      const n = { k, ti: ci, j: pi, row: p.row, color: col.color, c: p.c, p: p.p, qd: p.qd, ext: p.ext || 0, sec: p.sec };
      nodes.push(n);
      idx[k] = n;
    })
  );
  const edges = data.edges.map((e) => ({
    s: e.ci + "|" + e.pi, t: e.cj + "|" + e.pj, rel: e.rel, nc: e.nc, cn: e.contracts || [],
  }));
  const outs: Record<string, number[]> = {};
  const ins: Record<string, number[]> = {};
  edges.forEach((e, i) => {
    (outs[e.s] = outs[e.s] || []).push(i);
    (ins[e.t] = ins[e.t] || []).push(i);
  });

  // geometry: LEFT = 13-layer stack; RIGHT = domain panel
  const GUT = 180, padX = 14, padT = 8, pillW = 150, pillH = 26;
  const gapX = 10, gapY = 10, secH = 14, rowGap = 13, hdrH = 18, divW = 18;
  const isDomain = (col: any) => col.kind === "domain";
  const hasDom = cols.some(isDomain);
  const totalW = Math.max(900, totalWidth - 24);
  const rightCols = 3;
  const RW = hasDom ? rightCols * (pillW + gapX) - gapX + 2 * padX : 0;
  const DIV = hasDom ? divW : 0;
  const leftW = totalW - RW - DIV;
  const leftPerRow = Math.max(1, Math.floor((leftW - GUT - 2 * padX + gapX) / (pillW + gapX)));
  const rightPerRow = Math.max(1, Math.floor((RW - 2 * padX + gapX) / (pillW + gapX)));
  const rightX0 = leftW + DIV + padX;
  let topL = padT, topR = padT;
  cols.forEach((col) => {
    const dom = isDomain(col);
    col._dom = dom;
    col._perRow = dom ? rightPerRow : leftPerRow;
    const np = col.players.length;
    const rows = np === 0 ? 0 : Math.ceil(np / col._perRow);
    col._hasSec = (col.headers || []).some((h: any) => !h.sub);
    col._stripH = col._hasSec && np > 0 ? secH : 0;
    col._hdrH = dom ? hdrH : 0;
    col._x0 = dom ? rightX0 : GUT + padX;
    if (dom) { col._top = topR; col._pillTop = topR + col._hdrH + col._stripH; }
    else { col._top = topL; col._pillTop = topL + col._stripH; }
    const bandH = col._hdrH + col._stripH + Math.max(1, rows) * pillH + Math.max(0, rows - 1) * rowGap;
    if (dom) topR += bandH + gapY; else topL += bandH + gapY;
  });
  const W = totalW + 10;
  const H = Math.max(topL, topR) + 8;
  svg.setAttribute("width", String(W));
  svg.setAttribute("height", String(H));
  nodes.forEach((n) => {
    const col = cols[n.ti];
    const s = n.j, rr = Math.floor(s / col._perRow), cc = s % col._perRow;
    n.x = col._x0 + cc * (pillW + gapX);
    n.y = col._pillTop + rr * (pillH + rowGap);
  });

  function fitText(el: SVGTextElement, maxPx: number) {
    if (!el || maxPx <= 0) return;
    const full = el.textContent || "";
    const w = el.getComputedTextLength();
    if (!w) {
      const fs = parseFloat(el.getAttribute("font-size") || "11") || 11;
      const cw = fs * 0.6;
      if (full.length * cw <= maxPx) return;
      const keep = Math.max(1, Math.floor(maxPx / cw) - 1);
      el.textContent = full.length > keep ? full.slice(0, keep) + "…" : full;
      return;
    }
    if (w <= maxPx) return;
    let lo = 0, hi = full.length;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      el.textContent = full.slice(0, mid) + "…";
      if (el.getComputedTextLength() <= maxPx) lo = mid;
      else hi = mid - 1;
    }
    el.textContent = lo > 0 ? full.slice(0, lo) + "…" : "…";
  }
  function tip(ev: MouseEvent, html: string) {
    tipEl.innerHTML = html;
    tipEl.style.display = "block";
    tipEl.style.left = Math.min(ev.clientX + 14, window.innerWidth - 310) + "px";
    tipEl.style.top = ev.clientY + 12 + "px";
  }
  const hideTip = () => (tipEl.style.display = "none");

  // edges (drawn first)
  const gE = document.createElementNS(NS, "g");
  svg.appendChild(gE);
  const edgeEls: SVGPathElement[] = [];
  edges.forEach((e, i) => {
    const a = idx[e.s], b = idx[e.t];
    if (!a || !b) { edgeEls.push(document.createElementNS(NS, "path")); return; }
    const ar = cols[a.ti]._dom, br = cols[b.ti]._dom;
    const cxa = a.x + pillW / 2, cxb = b.x + pillW / 2;
    let d: string;
    if (ar !== br) {
      const ax = ar ? a.x : a.x + pillW, bx = br ? b.x : b.x + pillW;
      const ya = a.y + pillH / 2, yb = b.y + pillH / 2, mx = (ax + bx) / 2;
      d = `M ${ax} ${ya} C ${mx} ${ya}, ${mx} ${yb}, ${bx} ${yb}`;
    } else if (b.ti > a.ti) {
      const y1 = a.y + pillH, y2 = b.y, mid = (y1 + y2) / 2;
      d = `M ${cxa} ${y1} C ${cxa} ${mid}, ${cxb} ${mid}, ${cxb} ${y2}`;
    } else if (b.ti < a.ti) {
      const y1 = a.y, y2 = b.y + pillH, mid = (y1 + y2) / 2;
      d = `M ${cxa} ${y1} C ${cxa} ${mid}, ${cxb} ${mid}, ${cxb} ${y2}`;
    } else {
      const ya = a.y + pillH / 2, yb = b.y + pillH / 2, xr = Math.max(a.x, b.x) + pillW + 30;
      d = `M ${a.x + pillW} ${ya} C ${xr} ${ya}, ${xr} ${yb}, ${b.x + pillW} ${yb}`;
    }
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", d);
    p.classList.add("c2edge");
    p.setAttribute("stroke", e.nc > 0 ? "#7dd3fc" : "#475569");
    p.setAttribute("stroke-width", e.nc > 0 ? "1.8" : "1");
    if (e.nc === 0) p.setAttribute("stroke-dasharray", "4 4");
    p.setAttribute("opacity", e.nc > 0 ? "0.85" : "0.5");
    (p.style as any).pointerEvents = "none";
    gE.appendChild(p);
    edgeEls.push(p);
    const hit = document.createElementNS(NS, "path");
    hit.setAttribute("d", d);
    hit.setAttribute("fill", "none");
    hit.setAttribute("stroke", "transparent");
    hit.setAttribute("stroke-width", "14");
    (hit.style as any).cursor = "pointer";
    hit.addEventListener("mousemove", (ev) =>
      tip(ev,
        `<b>${esc(a.c)} → ${esc(b.c)}</b><br>${esc(e.rel)}<br>` +
        `<span style="color:#7dd3fc">${e.nc} signal${e.nc === 1 ? "" : "s"}</span> · ` +
        `<span style="color:#64748b">click = detail</span>`)
    );
    hit.addEventListener("mouseleave", hideTip);
    hit.addEventListener("click", (ev) => { ev.stopPropagation(); showEdge(i); });
    gE.appendChild(hit);
  });

  // band labels
  cols.forEach((col) => {
    const cnt = col.players.length + (col.players.length === 1 ? " company" : " companies");
    if (col._dom) {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", String(col._x0));
      t.setAttribute("y", String(col._top + 13));
      t.classList.add("c2hdr");
      t.setAttribute("fill", col.color || "#94a3b8");
      t.textContent = "▸ " + (col.name || col.slug).toUpperCase() + "  ·  " + cnt;
      svg.appendChild(t);
      fitText(t, RW - 2 * padX);
    } else {
      const ty = col._pillTop + pillH / 2;
      const tx = document.createElementNS(NS, "text");
      tx.setAttribute("x", "12");
      tx.setAttribute("y", String(ty - 4));
      tx.classList.add("c2hdr");
      tx.setAttribute("font-size", "10.5px");
      tx.setAttribute("letter-spacing", ".2px");
      tx.setAttribute("fill", col.color || "#94a3b8");
      tx.textContent = (col.name || col.slug).toUpperCase();
      svg.appendChild(tx);
      fitText(tx, GUT - 18);
      const c = document.createElementNS(NS, "text");
      c.setAttribute("x", "12");
      c.setAttribute("y", String(ty + 11));
      c.classList.add("c2cnt");
      c.setAttribute("fill", col.color || "#64748b");
      c.textContent = cnt;
      svg.appendChild(c);
    }
  });
  if (hasDom) {
    const dl = document.createElementNS(NS, "line");
    dl.setAttribute("x1", String(leftW + DIV / 2));
    dl.setAttribute("y1", String(padT));
    dl.setAttribute("x2", String(leftW + DIV / 2));
    dl.setAttribute("y2", String(H - 8));
    dl.setAttribute("stroke", "#1e293b");
    dl.setAttribute("stroke-width", "2");
    svg.appendChild(dl);
  }

  // sector labels
  cols.forEach((col, ci) => {
    if (!col._hasSec) return;
    let prev: string | null = null;
    col.players.forEach((p: any, pi: number) => {
      if (p.sec && p.sec !== prev) {
        const n = idx[ci + "|" + pi];
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", String(n.x));
        t.setAttribute("y", String(n.y - 4));
        t.setAttribute("fill", "#9aa6b2");
        t.setAttribute("font-size", "10px");
        t.textContent = p.sec;
        svg.appendChild(t);
        fitText(t, pillW);
      }
      prev = p.sec;
    });
  });

  // ripple reachability
  function reach(k: string, adj: Record<string, number[]>, next: (e: any) => string) {
    const seen = new Set<string>();
    const q = [k];
    while (q.length) {
      const cur = q.pop()!;
      (adj[cur] || []).forEach((i) => {
        const nx = next(edges[i]);
        if (!seen.has(nx)) { seen.add(nx); q.push(nx); }
      });
    }
    seen.delete(k);
    return seen;
  }
  const downOf = (k: string) => reach(k, outs, (e) => e.t);
  const upOf = (k: string) => reach(k, ins, (e) => e.s);

  let pinned: string | null = null;
  const pillEls: Record<string, SVGGElement> = {};
  function clearAll() {
    Object.values(pillEls).forEach((el) => el.classList.remove("dim", "rself", "rdown", "rup"));
    edgeEls.forEach((el) => el.classList.remove("dim", "edown", "eup"));
  }
  function applyRipple(k: string) {
    const D = downOf(k), U = upOf(k);
    clearAll();
    nodes.forEach((n) => {
      const el = pillEls[n.k];
      if (n.k === k) el.classList.add("rself");
      else if (D.has(n.k)) el.classList.add("rdown");
      else if (U.has(n.k)) el.classList.add("rup");
      else el.classList.add("dim");
    });
    edgeEls.forEach((el, i) => {
      const e = edges[i];
      const sD = e.s === k || D.has(e.s), tD = D.has(e.t);
      const sU = U.has(e.s), tU = e.t === k || U.has(e.t);
      if (sD && tD) el.classList.add("edown");
      else if (sU && tU) el.classList.add("eup");
      else el.classList.add("dim");
    });
  }
  function hoverHl(k: string) {
    const keep = new Set([k]);
    const keepE = new Set<number>();
    (outs[k] || []).forEach((i) => { keep.add(edges[i].t); keepE.add(i); });
    (ins[k] || []).forEach((i) => { keep.add(edges[i].s); keepE.add(i); });
    Object.entries(pillEls).forEach(([kk, el]) => el.classList.toggle("dim", !keep.has(kk)));
    edgeEls.forEach((el, i) => el.classList.toggle("dim", !keepE.has(i)));
  }

  // edge-detail panel
  let selEdge: number | null = null;
  function clearSel() {
    if (selEdge !== null && edgeEls[selEdge]) edgeEls[selEdge].classList.remove("esel");
    Object.values(pillEls).forEach((el) => el.classList.remove("epin"));
    selEdge = null;
  }
  function edgeBetween(k1: string, k2: string) {
    const res: number[] = [];
    (outs[k1] || []).forEach((i) => { if (edges[i].t === k2) res.push(i); });
    (outs[k2] || []).forEach((i) => { if (edges[i].t === k1) res.push(i); });
    return res;
  }
  function renderPanel(i: number) {
    const e = edges[i], a = idx[e.s], b = idx[e.t];
    let h = `<div class="ep-h"><span><b>${esc(a.c)}</b> &rarr; <b>${esc(b.c)}</b></span>`
      + `<span class="ep-x" id="ep-x">&times;</span></div>`
      + `<div class="ep-rel">${esc(e.rel) || "supply relationship"}</div>`;
    if (e.cn && e.cn.length) {
      h += `<div class="ep-n">${e.cn.length} signal${e.cn.length === 1 ? "" : "s"} on this link</div>`;
      e.cn.forEach((c: any) => {
        const meta = [c.units, c.value, c.date_signed, c.type]
          .filter((x) => x && x !== "no specific figure" && x !== "not stated").join("  ·  ");
        h += `<div class="ep-c">`
          + (c.source ? `<div class="ep-src">${esc(c.source)}</div>` : "")
          + (c.signal ? `<div class="ep-sig">${esc(c.signal)}</div>` : "")
          + (meta ? `<div class="ep-meta">${esc(meta)}</div>` : "")
          + `</div>`;
      });
    } else {
      h += `<div class="ep-empty">Structure only — no deal/contract data on this link yet.</div>`;
    }
    epanelEl.innerHTML = h;
    epanelEl.style.display = "block";
    const x = epanelEl.querySelector("#ep-x");
    if (x) x.addEventListener("click", (ev) => { ev.stopPropagation(); closePanel(); });
  }
  function showEdge(i: number) {
    clearSel();
    selEdge = i;
    edgeEls[i].classList.add("esel");
    if (pillEls[edges[i].s]) pillEls[edges[i].s].classList.add("epin");
    if (pillEls[edges[i].t]) pillEls[edges[i].t].classList.add("epin");
    renderPanel(i);
  }
  function closePanelSoft() { epanelEl.style.display = "none"; clearSel(); }
  function closePanel() { closePanelSoft(); pinned = null; clearAll(); }

  // company pills
  nodes.forEach((n) => {
    const g = document.createElementNS(NS, "g");
    g.classList.add("c2pill");
    const r = document.createElementNS(NS, "rect");
    r.setAttribute("x", String(n.x));
    r.setAttribute("y", String(n.y));
    r.setAttribute("width", String(pillW));
    r.setAttribute("height", String(pillH));
    r.setAttribute("rx", "13");
    r.setAttribute("stroke", n.ext ? "#475569" : n.color || "#94a3b8");
    r.setAttribute("stroke-width", "1.2");
    if (n.ext) { r.setAttribute("stroke-dasharray", "4 3"); r.setAttribute("fill-opacity", "0.55"); }
    g.appendChild(r);
    if (n.qd > 0) {
      const dot = document.createElementNS(NS, "circle");
      dot.setAttribute("cx", String(n.x + 12));
      dot.setAttribute("cy", String(n.y + pillH / 2));
      dot.setAttribute("r", "3");
      dot.setAttribute("fill", "#34d399");
      g.appendChild(dot);
    }
    const tx = document.createElementNS(NS, "text");
    tx.setAttribute("x", String(n.x + (n.qd > 0 ? 20 : 10)));
    tx.setAttribute("y", String(n.y + pillH / 2 + 4));
    tx.textContent = n.c;
    g.appendChild(tx);
    g.addEventListener("mouseenter", () => { if (!pinned) hoverHl(n.k); });
    g.addEventListener("mousemove", (ev) => {
      const nd = downOf(n.k).size, nu = upOf(n.k).size;
      tip(ev,
        `<b>${esc(n.c)}</b><br>${esc(n.p)}` +
        (n.qd > 0 ? `<br><span style="color:#34d399">${n.qd} data point${n.qd === 1 ? "" : "s"}</span>` : "") +
        `<br><span style="color:#fbbf24">▼ downstream ${nd}</span> · ` +
        `<span style="color:#60a5fa">▲ upstream ${nu}</span>` +
        `<br><span style="color:#64748b">click = ripple</span>`);
    });
    g.addEventListener("mouseleave", () => { if (!pinned) clearAll(); hideTip(); });
    g.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (pinned && pinned !== n.k) {
        const es = edgeBetween(pinned, n.k);
        if (es.length) { showEdge(es[0]); return; }
      }
      closePanelSoft();
      pinned = pinned === n.k ? null : n.k;
      if (pinned) applyRipple(n.k);
      else clearAll();
    });
    svg.appendChild(g);
    pillEls[n.k] = g;
    fitText(tx, pillW - (n.qd > 0 ? 20 : 10) - 8);
  });
  svg.addEventListener("click", () => { pinned = null; clearAll(); closePanelSoft(); });
}
