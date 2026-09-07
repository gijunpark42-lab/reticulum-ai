// askProvider.ts — SERVER-ONLY helpers shared by the two Ask routes:
//   /api/ask          (the answer: local runner first, then the model API)
//   /api/ask/rewrite  (the cheap query-rewrite step that runs before retrieval)
// It reads API keys from process.env, so it must never be imported by a client
// component. Everything is plain fetch — no SDK to install.
//
// One idea to know: every free tier we use (Gemini, Groq, OpenRouter…) speaks
// the OpenAI "chat completions" protocol, so ONE request builder covers them
// all; only Anthropic's Messages API has its own shape.

import type { NextRequest } from "next/server";

// ── Provider resolution ────────────────────────────────────────────────────

export interface Provider {
  kind: "openai" | "anthropic";
  /** For error messages: "Gemini", "Groq", "Anthropic", "the configured OpenAI-compatible". */
  name: string;
  /** Short id the UI badge shows next to the model id. */
  engine: "gemini" | "groq" | "anthropic" | "openai-compatible";
  /** OpenAI-compatible root (…/v1) or the Anthropic messages URL. */
  baseUrl: string;
  apiKey: string;
  /** The built-in default model; ASK_MODEL overrides it. */
  model: string;
  /** Which env var holds the key — for the error text. */
  envVar: string;
}

export const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
export const ANTHROPIC_VERSION = "2023-06-01";
const ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-5"; // answers
const ANTHROPIC_CHEAP_MODEL = "claude-haiku-4-5"; // query rewrite

/**
 * Which service to call, decided by which env vars exist (first match wins).
 * Defaults are the cheapest capable model on each service — all free-tier
 * eligible when this was written (09-2026).
 */
export function resolveProvider(): Provider | null {
  const env = process.env;
  const model = env.ASK_MODEL?.trim();
  if (env.ASK_BASE_URL && env.ASK_API_KEY)
    return {
      kind: "openai",
      name: "the configured OpenAI-compatible",
      engine: "openai-compatible",
      baseUrl: env.ASK_BASE_URL.replace(/\/+$/, ""),
      apiKey: env.ASK_API_KEY,
      model: model || "gpt-4o-mini",
      envVar: "ASK_API_KEY",
    };
  if (env.GEMINI_API_KEY)
    return {
      kind: "openai",
      name: "Gemini",
      engine: "gemini",
      baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
      apiKey: env.GEMINI_API_KEY,
      // Google renames Flash models every few months; pickModels() asks the
      // service which ones exist, so this is only the fallback name.
      model: model || "gemini-3.8-flash",
      envVar: "GEMINI_API_KEY",
    };
  if (env.GROQ_API_KEY)
    return {
      kind: "openai",
      name: "Groq",
      engine: "groq",
      baseUrl: "https://api.groq.com/openai/v1",
      apiKey: env.GROQ_API_KEY,
      model: model || "llama-3.3-70b-versatile",
      envVar: "GROQ_API_KEY",
    };
  if (env.ANTHROPIC_API_KEY)
    return {
      kind: "anthropic",
      name: "Anthropic",
      engine: "anthropic",
      baseUrl: ANTHROPIC_URL,
      apiKey: env.ANTHROPIC_API_KEY,
      model: model || ANTHROPIC_DEFAULT_MODEL,
      envVar: "ANTHROPIC_API_KEY",
    };
  return null;
}

// ── Model discovery ────────────────────────────────────────────────────────
// Free-tier services retire model names often (gemini-2.5-flash already 404s
// on a new key). Unless ASK_MODEL pins one, ask the OpenAI-compatible service
// for its model list (GET /models) and rank the ones we recognise. The raw
// list is cached per warm instance for an hour; ranking is recomputed per
// purpose ("best" for answers, "cheap" for the query rewrite).

const MODEL_CACHE_MS = 3_600_000;
const modelCache = new Map<string, { at: number; ids: string[] }>();

export type Prefer = "best" | "cheap";

/** Rank the service's model ids for one purpose, best first (at most 3). [] = nothing recognised. */
export function rankModels(p: Provider, ids: string[], prefer: Prefer): string[] {
  const out: string[] = [];
  const push = (id?: string | null) => {
    if (id && !out.includes(id)) out.push(id);
  };
  if (p.engine === "gemini") {
    // Stable text Flash models look like "gemini-3.8-flash" / "gemini-3.5-flash-lite".
    const parse = (id: string) => {
      const m = /^gemini-(\d+(?:\.\d+)?)-flash(-lite)?$/.exec(id);
      return m ? { v: parseFloat(m[1]), lite: Boolean(m[2]) } : null;
    };
    const stable: { id: string; v: number; lite: boolean }[] = [];
    for (const id of ids) {
      const m = parse(id);
      if (m) stable.push({ id, v: m.v, lite: m.lite });
    }
    const newestFirst = (a: { v: number }, b: { v: number }) => b.v - a.v;
    const flash = stable.filter((x) => !x.lite).sort(newestFirst).map((x) => x.id);
    const lite = stable.filter((x) => x.lite).sort(newestFirst).map((x) => x.id);
    const previews = ids.filter((id) => /^gemini-[\d.]+-flash.*preview$/.test(id)).sort().reverse();
    // Answers: newest Flash, then Flash-Lite. Rewrite: Flash-Lite first (cheapest).
    const order = prefer === "cheap" ? [...lite, ...flash, ...previews] : [...flash, ...lite, ...previews];
    for (const id of order) push(id);
  } else if (p.engine === "groq") {
    const best = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.1-8b-instant"];
    const cheap = ["llama-3.1-8b-instant", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "openai/gpt-oss-120b"];
    for (const want of prefer === "cheap" ? cheap : best) if (ids.includes(want)) push(want);
    push(ids.find((id) => /llama/i.test(id) && /70b/i.test(id)));
  }
  if (ids.includes(p.model)) push(p.model); // the built-in default, as a last resort
  return out.slice(0, 3);
}

/**
 * The models to try, in order. One entry unless discovery found alternatives —
 * a second choice matters because free-tier "model overloaded" errors are per model.
 */
export async function pickModels(p: Provider, prefer: Prefer = "best"): Promise<string[]> {
  const pinned = process.env.ASK_MODEL?.trim();
  if (p.kind === "anthropic") return [pinned ? p.model : prefer === "cheap" ? ANTHROPIC_CHEAP_MODEL : p.model];
  if (pinned) return [p.model];

  let ids: string[] | undefined = undefined;
  const cached = modelCache.get(p.baseUrl);
  if (cached && Date.now() - cached.at < MODEL_CACHE_MS) ids = cached.ids;
  if (ids === undefined) {
    ids = [];
    try {
      const r = await fetch(`${p.baseUrl}/models`, {
        headers: { authorization: `Bearer ${p.apiKey}` },
        cache: "no-store",
        signal: AbortSignal.timeout(8_000),
      });
      if (r.ok) {
        const j: any = await r.json();
        for (const m of (j?.data as any[]) || []) {
          const id = String(m?.id || "").replace(/^models\//, "");
          if (id) ids.push(id);
        }
        if (ids.length) modelCache.set(p.baseUrl, { at: Date.now(), ids });
      }
    } catch {
      /* discovery is best-effort: fall through to the default name */
    }
  }
  const ranked = rankModels(p, ids, prefer);
  return ranked.length ? ranked : [p.model];
}

// ── Request builder ────────────────────────────────────────────────────────

export interface ChatOptions {
  system: string;
  user: string;
  stream: boolean;
  temperature: number;
  maxTokens: number;
  /** OpenAI-compatible only: ask for a JSON object reply (the rewrite step). */
  jsonObject?: boolean;
  /** Anthropic only: brief adaptive thinking before answering (the answer step). */
  think?: boolean;
}

/** The HTTP request for one model name — the two APIs differ in shape. Never logs the key. */
export function buildChatRequest(
  p: Provider,
  model: string,
  o: ChatOptions
): { url: string; headers: Record<string, string>; body: Record<string, unknown> } {
  if (p.kind === "anthropic") {
    const body: Record<string, unknown> = {
      model,
      max_tokens: o.maxTokens,
      stream: o.stream,
      system: o.system,
      messages: [{ role: "user", content: o.user }],
    };
    if (o.think) {
      // Adaptive thinking at low effort: a short check of the snippets before
      // answering, without spending the token budget on long reasoning.
      // (Temperature must stay at its default when thinking is on.)
      body.thinking = { type: "adaptive" };
      body.output_config = { effort: "low" };
    } else {
      body.temperature = o.temperature;
    }
    return {
      url: ANTHROPIC_URL,
      headers: {
        "content-type": "application/json",
        "x-api-key": p.apiKey,
        "anthropic-version": ANTHROPIC_VERSION,
      },
      body,
    };
  }
  const body: Record<string, unknown> = {
    model,
    max_tokens: o.maxTokens,
    stream: o.stream,
    temperature: o.temperature,
    messages: [
      { role: "system", content: o.system },
      { role: "user", content: o.user },
    ],
  };
  if (o.jsonObject) body.response_format = { type: "json_object" };
  return {
    url: `${p.baseUrl}/chat/completions`,
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${p.apiKey}`,
    },
    body,
  };
}

// ── Retry helpers ──────────────────────────────────────────────────────────

/** Statuses worth retrying: rate limit, and the "overloaded / unavailable" family. */
export const RETRYABLE_STATUSES = new Set([429, 500, 502, 503, 529]);

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Exponential backoff: retry 1 → 1 s, 2 → 2 s, 3 → 4 s, each plus 0–500 ms of jitter
 *  so several waiting requests do not all hit the service in the same instant. */
export function backoffMs(retry: number): number {
  return 1000 * 2 ** (retry - 1) + Math.floor(Math.random() * 500);
}

/** True for the errors fetch throws when an AbortSignal.timeout fires. */
export function isTimeout(e: unknown): boolean {
  const name = (e as { name?: string } | null)?.name;
  return name === "TimeoutError" || name === "AbortError";
}

/** A countdown from the request start, so every step can ask "how long is left?". */
export function makeDeadline(budgetMs: number) {
  const start = Date.now();
  return {
    start,
    elapsed: () => Date.now() - start,
    remaining: () => budgetMs - (Date.now() - start),
  };
}

// ── Rate limit (per warm instance) ─────────────────────────────────────────
// In-memory, so it is per serverless instance and resets on a cold start — a
// speed bump against runaway scripts and against a burst spawning many local
// `claude` processes, not a billing guarantee. Good enough for a personal tool.

const hits = new Map<string, number[]>();

/** True when `ip` already made `limit` requests to `bucket` inside the window. */
export function rateLimited(bucket: string, ip: string, limit: number, windowMs: number): boolean {
  const key = `${bucket}:${ip}`;
  const now = Date.now();
  const recent = (hits.get(key) || []).filter((t) => now - t < windowMs);
  if (recent.length >= limit) {
    hits.set(key, recent);
    return true;
  }
  recent.push(now);
  hits.set(key, recent);
  // Keep the map from growing forever on a long-lived instance.
  if (hits.size > 5_000) {
    for (const [k, v] of hits) if (!v.some((t) => now - t < windowMs)) hits.delete(k);
  }
  return false;
}

export function clientIp(req: NextRequest): string {
  const fwd = req.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return req.headers.get("x-real-ip") || "unknown";
}
