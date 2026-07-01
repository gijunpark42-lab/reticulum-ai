// /api/earnings — batched next/last earnings-call dates from Yahoo Finance.
// POST { companies: [{ id, ticker, exchange }] } → { dates: { [id]: { ts, start, end } } }
// (epoch SECONDS or null). Yahoo's v7 quote endpoint needs the cookie+crumb
// handshake (same dance yfinance does); both the auth and the per-symbol dates
// are cached in module memory so a warm serverless instance answers instantly.

import { NextRequest, NextResponse } from "next/server";
import { yahooSymbol } from "@/lib/yahoo";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

interface Earn {
  ts: number | null; // earningsTimestamp (next call if scheduled, else the last one)
  start: number | null;
  end: number | null;
}

let auth: { cookie: string; crumb: string; at: number } | null = null;

async function getAuth() {
  if (auth && Date.now() - auth.at < 30 * 60_000) return auth;
  try {
    const r1 = await fetch("https://fc.yahoo.com/", {
      redirect: "manual",
      headers: { "User-Agent": UA },
      cache: "no-store",
    });
    const cookie = (r1.headers.get("set-cookie") || "").split(";")[0];
    if (!cookie) return null;
    const r2 = await fetch("https://query1.finance.yahoo.com/v1/test/getcrumb", {
      headers: { "User-Agent": UA, cookie },
      cache: "no-store",
    });
    const crumb = (await r2.text()).trim();
    if (!r2.ok || !crumb || crumb.includes("<")) return null;
    auth = { cookie, crumb, at: Date.now() };
    return auth;
  } catch {
    return null;
  }
}

const cache = new Map<string, { v: Earn; at: number }>();
const TTL = 6 * 3600_000; // earnings dates move slowly — 6h is plenty

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  const companies: { id: string; ticker?: string | null; exchange?: string | null }[] =
    Array.isArray(body?.companies) ? body.companies : [];
  if (!companies.length) return NextResponse.json({ dates: {} });

  // symbol → all company ids that share it (e.g. Samsung + Samsung Foundry).
  const symToIds = new Map<string, string[]>();
  for (const c of companies) {
    if (!c || typeof c.id !== "string") continue;
    const sym = yahooSymbol(c.ticker, c.exchange);
    if (!sym) continue;
    const arr = symToIds.get(sym) || [];
    arr.push(c.id);
    symToIds.set(sym, arr);
  }

  const now = Date.now();
  const need = [...symToIds.keys()].filter((s) => {
    const hit = cache.get(s);
    return !hit || now - hit.at > TTL;
  });

  let authOk = true;
  if (need.length) {
    const a = await getAuth();
    if (!a) authOk = false;
    else {
      for (let i = 0; i < need.length; i += 50) {
        const chunk = need.slice(i, i + 50);
        try {
          const url =
            `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(
              chunk.join(",")
            )}&fields=earningsTimestamp,earningsTimestampStart,earningsTimestampEnd` +
            `&crumb=${encodeURIComponent(a.crumb)}`;
          const r = await fetch(url, {
            headers: { "User-Agent": UA, cookie: a.cookie },
            cache: "no-store",
          });
          if (!r.ok) continue;
          const j = await r.json();
          for (const q of j?.quoteResponse?.result || []) {
            if (!q?.symbol) continue;
            cache.set(q.symbol, {
              v: {
                ts: q.earningsTimestamp ?? null,
                start: q.earningsTimestampStart ?? null,
                end: q.earningsTimestampEnd ?? null,
              },
              at: now,
            });
          }
          // Symbols Yahoo didn't echo back (delisted/unknown): cache the miss
          // so we don't hammer the endpoint on every page view.
          for (const s of chunk) {
            const hit = cache.get(s);
            if (!hit || now - hit.at > TTL)
              cache.set(s, { v: { ts: null, start: null, end: null }, at: now });
          }
        } catch {
          /* chunk failed — leave uncached, next request retries */
        }
      }
    }
  }

  const dates: Record<string, Earn> = {};
  for (const [sym, ids] of symToIds) {
    const hit = cache.get(sym);
    if (!hit) continue;
    for (const id of ids) dates[id] = hit.v;
  }
  return NextResponse.json({ dates, authOk });
}
