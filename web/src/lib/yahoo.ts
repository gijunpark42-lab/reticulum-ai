// yahoo.ts — shared Yahoo Finance symbol mapping (used by /api/quote and
// /api/earnings). Turns the project's (ticker, exchange) into a Yahoo symbol.

const SYMBOL_OVERRIDE: Record<string, string> = { BESI: "BESI.AS" };

// Exchange → Yahoo suffix for tickers stored WITHOUT one. US listings need none;
// most Asian tickers in company_metadata already carry their suffix (.TW/.T/.HK).
const EXCHANGE_SUFFIX: Record<string, string> = {
  TSE: ".T",
  KOSPI: ".KS",
  KRX: ".KS",
  KOSDAQ: ".KQ", // KOSDAQ is .KQ on Yahoo, NOT .KS
  TWSE: ".TW",
  SZSE: ".SZ",
  XETRA: ".DE",
  AMS: ".AS",
  "Euronext Amsterdam": ".AS",
  EPA: ".PA",
  "Euronext Paris": ".PA",
  MIL: ".MI",
  STO: ".ST",
  "OMX Stockholm": ".ST",
  OSE: ".OL",
  SIX: ".SW",
  HKEX: ".HK",
  VIE: ".VI",
  LSE: ".L",
  IDX: ".JK",
};

export function yahooSymbol(
  ticker?: string | null,
  exchange?: string | null
): string | null {
  const t = (ticker || "").trim();
  if (!t) return null;
  if (SYMBOL_OVERRIDE[t]) return SYMBOL_OVERRIDE[t];
  if (t.includes(".")) return t; // already carries a Yahoo suffix
  const suf = exchange ? EXCHANGE_SUFFIX[exchange] : undefined;
  if (suf) return t + suf;
  if (/^\d+$/.test(t)) return t + ".KS"; // legacy fallback: bare numeric = KRX
  return t; // plain US / ADR ticker works as-is
}
