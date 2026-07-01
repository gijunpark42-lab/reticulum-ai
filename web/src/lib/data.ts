// data.ts — fetch the curated JSON and enrich the merged graph into the
// VizNode / VizLink shapes the 3D graph and panel consume. Ports app.py's
// degree / incoming-index / node-build loops (lines ~461-569).

import type {
  MergedGraph,
  GraphNode,
  VizNode,
  VizLink,
  LogoManifest,
} from "./types";
import { GROUP_COLORS, CHAIN_COLORS } from "./taxonomy";
import { nodeSignalMeta } from "./signals";

export async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  return res.json();
}

export interface VizData {
  nodes: VizNode[];
  links: VizLink[];
  byId: Map<string, VizNode>;
}

export function buildViz(
  graph: MergedGraph,
  manifest: LogoManifest,
  reportKeys: Set<string>
): VizData {
  // Degree = in + out edges per node → drives sphere size.
  const degree: Record<string, number> = {};
  for (const e of graph.edges) {
    degree[e.source] = (degree[e.source] || 0) + 1;
    degree[e.target] = (degree[e.target] || 0) + 1;
  }

  // Who supplies INTO each node (incoming) and who each node supplies (outgoing).
  const incoming: Record<string, VizNode["incoming"]> = {};
  const outgoing: Record<string, VizNode["outgoing"]> = {};
  for (const e of graph.edges) {
    (incoming[e.target] ||= []).push({
      source: e.source,
      relationship: e.relationship,
      contracts: e.contracts || [],
    });
    (outgoing[e.source] ||= []).push({
      target: e.target,
      relationship: e.relationship,
      contracts: e.contracts || [],
      chain: e.chain,
    });
  }

  const nodes: VizNode[] = graph.nodes.map((node: GraphNode) => {
    const layers = node.layers || [];
    const domains = node.domains || [];
    const primary = layers[0] || domains[0] || "unknown";
    const deg = degree[node.id] || 0;
    const val = Math.max(4, Math.floor(Math.pow(deg, 1.5)));
    const { badges, lastData, stale } = nodeSignalMeta(node.quarterly_data);
    const logo = manifest[node.id];
    return {
      ...node,
      primary,
      color: GROUP_COLORS[primary] || "#94a3b8",
      val,
      degree: deg,
      incoming: incoming[node.id] || [],
      outgoing: outgoing[node.id] || [],
      badges,
      lastData,
      stale,
      logo: logo ? `/logos/${encodeURIComponent(logo.file)}` : null,
      logoBg: logo ? logo.bg : null,
      hasReport: reportKeys.has(node.id),
    };
  });

  const byId = new Map(nodes.map((n) => [n.id, n]));

  const links: VizLink[] = graph.edges.map((e) => ({
    source: e.source,
    target: e.target,
    relationship: e.relationship,
    contracts: (e.contracts || []).slice(0, 3),
    chain: e.chain,
    color: CHAIN_COLORS[e.chain] || "#8b949e",
  }));

  return { nodes, links, byId };
}
