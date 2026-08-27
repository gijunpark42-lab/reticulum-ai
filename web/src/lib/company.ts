// Resolve a free-text company name to a graph node id.
//
// The Timelines / Capex tables are hand-written, so their company names don't
// always match a node id character-for-character: "Amkor" vs "Amkor Technology",
// "NVIDIA (buyer)" vs "NVIDIA", "AWS" vs "Amazon". This turns those strings back
// into node ids so any table cell can open the same NodePanel the 3D graph does.
//
// It only ever matches a WHOLE cell — never a substring — so ordinary cells
// ("Volume", "2027", "Enabler") stay plain text instead of becoming bogus links.

// Trailing words that are part of a legal name but not how people write it.
const SUFFIX = new Set([
  "systems", "technologies", "technology", "inc", "corp", "corporation",
  "holdings", "group", "semiconductor", "semiconductors", "co", "ltd",
  "limited", "plc", "sa", "ag", "nv",
]);

// Names that are a real business unit / former parent rather than a spelling
// variant, so no amount of normalising would connect them.
const ALIAS: Record<string, string> = {
  aws: "Amazon",
  awstrainium: "Amazon",
  amazonwebservices: "Amazon",
  alphabet: "Google",
  googlecloud: "Google",
};

// Lowercase, drop any "(qualifier)", collapse punctuation to single spaces.
const norm = (s: string) =>
  s
    .replace(/\([^)]*\)/g, " ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

const key = (s: string) => norm(s).replace(/ /g, "");

// Same as `key`, but with trailing corporate suffixes removed:
// "Amkor Technology" and "Amkor" both stem to "amkor".
function stem(s: string): string {
  const w = norm(s).split(" ").filter(Boolean);
  while (w.length > 1 && SUFFIX.has(w[w.length - 1])) w.pop();
  return w.join("");
}

export type Resolver = (text: string) => string | null;

/** Build a resolver over the current graph's node ids. */
export function buildResolver(ids: Iterable<string>): Resolver {
  const exact = new Set<string>();
  const byKey = new Map<string, string>();
  const stems = new Map<string, string[]>();

  for (const id of ids) {
    exact.add(id);
    if (!byKey.has(key(id))) byKey.set(key(id), id);
    const st = stem(id);
    stems.set(st, [...(stems.get(st) || []), id]);
  }

  // Suffix-stripped matching is only safe where exactly one node claims the
  // stem; drop anything ambiguous rather than guess.
  const byStem = new Map<string, string>();
  for (const [st, list] of stems) if (list.length === 1) byStem.set(st, list[0]);

  return (text: string) => {
    // A long cell is prose, not a company name — don't even try.
    if (!text || text.length > 60) return null;
    if (exact.has(text)) return text;
    const k = key(text);
    if (!k) return null;
    return ALIAS[k] || byKey.get(k) || byStem.get(stem(text)) || null;
  };
}
