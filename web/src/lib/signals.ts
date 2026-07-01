// signals.ts — badge heuristics, freshness, and timeline extraction.
// Ported 1:1 from app.py (BADGE_PATTERNS / node_signal_meta) and the panel JS
// (BADGE_RULES / buildBadges / buildTimeline). Same regexes, same behavior.

import type { QuarterlyData } from "./types";

export interface BadgeRule {
  key: string;
  label: string;
  color: string;
  re: RegExp;
}

export const BADGE_RULES: BadgeRule[] = [
  {
    key: "tight",
    label: "⚡ Supply tight",
    color: "#f85149",
    re: /sold out|fully allocated|fully booked|booked out|almost fully|nearly fully subscribed|exceed.{0,12}(production )?capacity|demand.{0,20}outpac|demand.{0,20}exceed|capacity.{0,15}constrain|allocated through|supply.{0,20}tight|very tight|capacity.{0,12}tight|tight (into|through|beyond)/i,
  },
  {
    key: "guideup",
    label: "📈 Guidance raised",
    color: "#3fb950",
    re: /rais(ed|ing)\s[^.;]{0,45}(guidance|outlook|target|growth|forecast|guide)|guidance raised|raised guidance|outlook raised|raised to|increase[sd]? (our |its )?(full[- ]year|fy|annual)/i,
  },
  {
    key: "lta",
    label: "📜 Long-term contracts",
    color: "#a371f7",
    re: /\bLTA|long[- ]term (supply )?(agreement|contract|offtake)|multi[- ]?year (supply |purchase |contract|agreement|commitment)|supply agreement|\bNBM|\bSCA\b|build[- ]to[- ]order contract|purchase commitment/i,
  },
  {
    key: "capex",
    label: "🏗️ Capacity expanding",
    color: "#d29922",
    re: /capacity expansion|expand(ing)? (our |its )?(manufacturing |production )?capacity|new (fab|facility|factory|plant|cleanroom|building)|additional capacity|capacity invest|broke ground|increase[sd]? capacity/i,
  },
];

export const BADGE_EMOJI: Record<string, string> = {
  tight: "⚡",
  guideup: "📈",
  lta: "📜",
  capex: "🏗️",
};

const LABEL_DATE = /\((\d{2})-(\d{2})-(\d{4})\)/;
const STALE_DAYS = 180;

// Badges (slug list), newest-signal date (YYYY-MM-DD | null), and staleness.
export function nodeSignalMeta(qd: QuarterlyData[]): {
  badges: string[];
  lastData: string | null;
  stale: boolean;
} {
  const parts: string[] = [];
  let latest: Date | null = null;
  for (const q of qd || []) {
    parts.push((q.signal || "") + " " + (q.figure || ""));
    const m = LABEL_DATE.exec(q.quarter || "");
    if (m) {
      const d = new Date(+m[3], +m[1] - 1, +m[2]);
      if (!isNaN(d.getTime()) && (latest === null || d > latest)) latest = d;
    }
  }
  const text = parts.join(" ");
  const badges = BADGE_RULES.filter((r) => r.re.test(text)).map((r) => r.key);
  const now = new Date();
  const stale =
    latest === null || (now.getTime() - latest.getTime()) / 86400000 > STALE_DAYS;
  const lastData = latest
    ? `${latest.getFullYear()}-${String(latest.getMonth() + 1).padStart(2, "0")}-${String(
        latest.getDate()
      ).padStart(2, "0")}`
    : null;
  return { badges, lastData, stale };
}

// Chronological sort key from a source label like "... (05-28-2026)".
export function sigDate(label: string): number {
  const m = /\((\d{2})-(\d{2})-(\d{4})\)/.exec(label || "");
  return m ? +m[3] * 10000 + +m[1] * 100 + +m[2] : -1;
}

export function buildBadges(sigs: QuarterlyData[]): BadgeRule[] {
  const hit: Record<string, boolean> = {};
  for (const q of sigs) {
    const text = (q.signal || "") + " " + (q.figure || "");
    for (const r of BADGE_RULES) if (!hit[r.key] && r.re.test(text)) hit[r.key] = true;
  }
  return BADGE_RULES.filter((r) => hit[r.key]);
}

const DATE_RE =
  /\b(Q[1-4]\s*(?:FY\s*)?20\d\d|[12]H\s*20\d\d|H[12]\s*(?:FY\s*)?20\d\d|(?:early|mid|late|end of|exiting|through|by)\s*(?:calendar |CY|fiscal |FY)?\s*20\d\d|CY20\d\d|FY20\d\d|20\d\d)\b/i;

function dateKey(s: string): number {
  const y = /20(\d\d)/.exec(s);
  if (!y) return 99999;
  let k = +("20" + y[1]) * 10;
  const q = /Q([1-4])/i.exec(s);
  const h = /([12])H|H([12])/.exec(s);
  if (q) k += +q[1] * 2;
  else if (h) k += +(h[1] || h[2]) * 4;
  else if (/late|end|exiting|H2/i.test(s)) k += 8;
  else if (/mid/i.test(s)) k += 5;
  else if (/early|H1/i.test(s)) k += 2;
  return k;
}

export interface TimelineItem {
  when: string;
  key: number;
  text: string;
}

// ── Near-duplicate detection (so the timeline doesn't repeat the same fact) ──
const yearOf = (s: string): string => (/20\d\d/.exec(s) || [""])[0];
const tokenSet = (s: string): Set<string> =>
  new Set(
    s
      .toLowerCase()
      .replace(/[^a-z0-9%. ]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .split(" ")
      .filter((w) => w.length > 2)
  );
function jaccard(a: Set<string>, b: Set<string>): number {
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  const uni = a.size + b.size - inter;
  return uni === 0 ? 0 : inter / uni;
}
const DUP_SIM = 0.6; // same year + token overlap ≥ this → treat as the same fact

// Pull date-bearing sentences out of a company's signals, ordered chronologically.
// Near-identical entries (same year, high word overlap) collapse into one — keeping
// the longer, more complete phrasing.
export function buildTimeline(sigs: QuarterlyData[]): TimelineItem[] {
  interface Kept extends TimelineItem {
    tokens: Set<string>;
    year: string;
  }
  const kept: Kept[] = [];
  for (const q of sigs) {
    for (const sent of (q.signal || "").split(/(?<=[.;])\s+/)) {
      const t = sent.trim();
      if (t.length < 25 || t.length > 240) continue;
      const m = DATE_RE.exec(t);
      if (!m) continue;
      const tokens = tokenSet(t);
      const year = yearOf(t) || yearOf(m[1]);
      const dupIdx = kept.findIndex(
        (k) => k.year === year && jaccard(k.tokens, tokens) >= DUP_SIM
      );
      if (dupIdx >= 0) {
        // Merge: keep whichever phrasing is longer (more complete).
        if (t.length > kept[dupIdx].text.length)
          kept[dupIdx] = { when: m[1], key: dateKey(m[1]), text: t, tokens, year };
        continue;
      }
      kept.push({ when: m[1], key: dateKey(m[1]), text: t, tokens, year });
    }
  }
  kept.sort((a, b) => a.key - b.key);
  return kept.slice(0, 10).map(({ when, key, text }) => ({ when, key, text }));
}

// Country flag emoji (matches app.py FLAG map).
export const FLAG: Record<string, string> = {
  US: "🇺🇸",
  TW: "🇹🇼",
  KR: "🇰🇷",
  JP: "🇯🇵",
  NL: "🇳🇱",
  DE: "🇩🇪",
  CN: "🇨🇳",
  CA: "🇨🇦",
  ID: "🇮🇩",
  PH: "🇵🇭",
  HK: "🇭🇰",
  GB: "🇬🇧",
  FR: "🇫🇷",
  IL: "🇮🇱",
};
