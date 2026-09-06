// types.ts — shapes of the curated JSON data (see merged_graph.json etc.).

export interface Product {
  chain: string;
  layer?: string | null;
  domain?: string | null;
  sector?: string | null;
  sub_sector?: string | null;
  product: string;
}

export interface QuarterlyData {
  quarter: string;
  signal: string;
  figure: string;
  chain?: string;
  // Optional tags written by enrichment (CLAUDE.md Workflow 2, JOB 5).
  topics?: string[];
  slot?: "revenue_growth" | "guidance" | "backlog_or_b2b" | "supply_status" | "next_catalyst";
  capex?: { field: string; busd?: number | null; display?: string; period?: string; metric?: string; growth?: string };
  // Present when the entry was folded from an edge whose counterparty is not a node
  // (2026-09-05 cleanup): "Customer X: ..." / "Supplier X: ..." entries.
  counterparty?: string;
  counterparty_role?: "customer" | "supplier";
}

export interface Contract {
  source: string;
  signal: string;
  units: string;
  value: string;
  date_signed: string;
  type: string;
  topics?: string[];
}

export interface GraphNode {
  id: string;
  layers: string[];
  domains: string[];
  sectors: string[];
  chains: string[];
  products: Product[];
  quarterly_data: QuarterlyData[];
  ticker: string | null;
  exchange: string | null;
  country: string;
  status: "public" | "private" | "subsidiary";
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  contracts: Contract[];
  chain: string;
}

export interface MergedGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface LogoEntry {
  file: string;
  bg: "light" | "dark";
}
export type LogoManifest = Record<string, LogoEntry>;

// ── Live quote (from /api/quote, mirrors the Python _fetch_quote output) ──
export interface LiveQuote {
  price: number | null;
  change_pct: number | null;
  market_cap: number | null;
  year_high: number | null;
  year_low: number | null;
  currency: string;
  series: Record<string, [number, number][]>; // range -> [[epochMs, close], ...]
  as_of: string;
}

// ── The node object we feed into the 3D graph / panel (enriched at load time) ──
export interface VizNode extends GraphNode {
  primary: string;
  color: string;
  val: number;
  degree: number;
  incoming: {
    source: string;
    relationship: string;
    contracts: Contract[];
  }[];
  outgoing: {
    target: string;
    relationship: string;
    contracts: Contract[];
    chain: string;
  }[];
  badges: string[]; // slugs: tight/guideup/lta/capex
  lastData: string | null;
  stale: boolean;
  logo: string | null; // /logos/<file> url
  logoBg: "light" | "dark" | null;
  hasReport: boolean;
}

export interface VizLink {
  source: string;
  target: string;
  relationship: string;
  contracts: Contract[];
  chain: string;
  color: string;
}
