// transitions.ts — the generation-transition delta engine.
//
// The project's core thesis: chains are split by accelerator GENERATION, so the
// investable signal is who keeps / gains / loses a socket across a transition
// (B200→Vera Rubin, MI355→MI450, Trainium2→3, TPU v7→v8) and how the content
// changes (HBM3E→HBM4, copper→optical, ...). This is pure computation over the
// chains[] and products[] each node already carries — no LLM, no new data.

import type { VizNode } from "./types";
import { LAYER_ORDER, DOMAIN_ORDER } from "./taxonomy";

export interface Transition {
  key: string;
  vendor: string; // accelerator vendor the transition belongs to
  label: string; // full label ("B200 (Blackwell) → Vera Rubin")
  short: string; // compact label for chips ("B200 → Rubin")
  from: string[]; // current-gen chain slug(s)
  to: string[]; // next-gen chain slug(s) — TPU v8 has two (v8t + v8i)
}

export const TRANSITIONS: Transition[] = [
  {
    key: "nvidia",
    vendor: "NVIDIA",
    label: "B200 (Blackwell) → Vera Rubin",
    short: "B200 → Rubin",
    from: ["nvda_b200"],
    to: ["nvidia_vera_rubin"],
  },
  {
    key: "amd",
    vendor: "AMD",
    label: "MI355 → MI450 / Helios",
    short: "MI355 → MI450",
    from: ["amd_mi355"],
    to: ["amd_mi450_helios"],
  },
  {
    key: "aws",
    vendor: "AWS",
    label: "Trainium2 → Trainium3",
    short: "Trn2 → Trn3",
    from: ["aws_trainium2"],
    to: ["aws_trainium3"],
  },
  {
    key: "google",
    vendor: "Google",
    label: "TPU v7 (Ironwood) → TPU v8 (v8t + v8i)",
    short: "TPU v7 → v8",
    from: ["google_tpu_v7_ironwood"],
    to: ["tpu_v8t", "tpu_v8i"],
  },
];

export type GenStatus = "retained" | "gained" | "lost";

export interface TransitionRow {
  id: string;
  primary: string; // layer/domain slug — drives dot color + ordering
  status: GenStatus;
  productFrom: string | null;
  productTo: string | null;
  toChains: string[]; // which successor chain(s) the company appears in
}

export interface TransitionResult {
  t: Transition;
  rows: TransitionRow[];
  counts: Record<GenStatus, number>;
}

// A company's product string within a set of chains (joins distinct products
// when it plays several roles, e.g. in both tpu_v8t and tpu_v8i).
export function productIn(node: VizNode, chains: string[]): string | null {
  const seen: string[] = [];
  for (const p of node.products || []) {
    if (chains.includes(p.chain) && p.product && !seen.includes(p.product)) seen.push(p.product);
  }
  return seen.length ? seen.join(" · ") : null;
}

const groupOrd = (s: string) =>
  s in LAYER_ORDER ? LAYER_ORDER[s] : 100 + (DOMAIN_ORDER[s] ?? 50);

export function computeTransition(nodes: VizNode[], t: Transition): TransitionResult {
  const rows: TransitionRow[] = [];
  for (const n of nodes) {
    const inFrom = t.from.some((c) => n.chains.includes(c));
    const inTo = t.to.some((c) => n.chains.includes(c));
    if (!inFrom && !inTo) continue;
    const status: GenStatus = inFrom && inTo ? "retained" : inTo ? "gained" : "lost";
    rows.push({
      id: n.id,
      primary: n.primary,
      status,
      productFrom: inFrom ? productIn(n, t.from) : null,
      productTo: inTo ? productIn(n, t.to) : null,
      toChains: t.to.filter((c) => n.chains.includes(c)),
    });
  }
  rows.sort((a, b) => groupOrd(a.primary) - groupOrd(b.primary) || a.id.localeCompare(b.id));
  const counts: Record<GenStatus, number> = { retained: 0, gained: 0, lost: 0 };
  for (const r of rows) counts[r.status]++;
  return { t, rows, counts };
}

// For the node detail panel: this company's exposure across every transition.
export interface ExposureItem {
  t: Transition;
  status: GenStatus;
  productFrom: string | null;
  productTo: string | null;
}

export function nodeExposure(node: VizNode): ExposureItem[] {
  const out: ExposureItem[] = [];
  for (const t of TRANSITIONS) {
    const inFrom = t.from.some((c) => node.chains.includes(c));
    const inTo = t.to.some((c) => node.chains.includes(c));
    if (!inFrom && !inTo) continue;
    out.push({
      t,
      status: inFrom && inTo ? "retained" : inTo ? "gained" : "lost",
      productFrom: inFrom ? productIn(node, t.from) : null,
      productTo: inTo ? productIn(node, t.to) : null,
    });
  }
  return out;
}
