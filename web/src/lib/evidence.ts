// evidence.ts — "show me where this number comes from".
//
// evidence.py (repo root) walks the merged graph, opens the source transcript behind
// every quarterly_data entry and every contract, and saves the passage that backs it in
// graph/evidence.json (served here as /data/evidence.json). Each record is filed under a
// short key derived from the entry itself, so the browser can look an entry up without
// the JSON repeating company names and signal text:
//
//     key = first 16 hex chars of SHA-1( "<kind>|<company>|<target>|<label>|<signal>" )
//
//     kind    "qd" for a node's quarterly_data entry, "contract" for an edge contract
//     company the node id — for a contract, the edge SOURCE company
//     target  the edge TARGET company; "" for a quarterly_data entry
//     label   the entry's `quarter` (qd) / `source` (contract) label, exactly as stored
//     signal  the entry's `signal` text, exactly as stored (no trimming)
//
// The string is UTF-8 encoded before hashing, exactly like Python's
// hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]. Browsers only expose SHA-1
// through the async WebCrypto API, so a small synchronous SHA-1 lives here instead —
// it lets a component compute a key during render with no dependency.

export type EvidenceKind = "qd" | "contract";
export type EvidenceStatus = "found" | "no_match" | "no_source";

export interface EvidenceEntry {
  doc: string | null; // repo-relative source path, e.g. "transcripts/av/nvidia_q3_2027.txt"
  excerpt: string | null; // verbatim source text, ±220 chars, match wrapped in «…»
  matched: string | null; // the text inside «…»
  status: EvidenceStatus;
  via?: "number" | "phrase" | "words" | "counterparty" | null; // what the match was anchored on
  unmatched?: string[]; // figure/units/value numbers that occur nowhere in the document
}

export interface EvidenceRef {
  kind: EvidenceKind;
  company: string;
  target: string;
  label: string;
  signal: string;
}

export type EvidenceMap = Map<string, EvidenceEntry>;

interface EvidenceFile {
  generated: string;
  entries: Record<string, EvidenceEntry>;
}

// ── SHA-1 ────────────────────────────────────────────────────────────────────
// Straight from the FIPS 180-4 description. JavaScript bitwise operators work on
// signed 32-bit integers, so every sum is brought back to an unsigned 32-bit value
// with `>>> 0`. Intermediate sums stay below 2^36, which a double represents exactly.

function rotl(x: number, n: number): number {
  return ((x << n) | (x >>> (32 - n))) >>> 0;
}

export function sha1Hex(bytes: Uint8Array): string {
  // Padding: 0x80, zeros, then the message length in bits as a 64-bit big-endian int,
  // so the total is a multiple of 64 bytes.
  const total = Math.ceil((bytes.length + 9) / 64) * 64;
  const buf = new Uint8Array(total);
  buf.set(bytes);
  buf[bytes.length] = 0x80;
  const view = new DataView(buf.buffer);
  const bitLen = bytes.length * 8;
  view.setUint32(total - 8, Math.floor(bitLen / 0x100000000), false);
  view.setUint32(total - 4, bitLen >>> 0, false);

  let h0 = 0x67452301;
  let h1 = 0xefcdab89;
  let h2 = 0x98badcfe;
  let h3 = 0x10325476;
  let h4 = 0xc3d2e1f0;
  const w = new Uint32Array(80);

  for (let off = 0; off < total; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4, false);
    for (let i = 16; i < 80; i++) w[i] = rotl(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);

    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    for (let i = 0; i < 80; i++) {
      let f: number;
      let k: number;
      if (i < 20) {
        f = (b & c) | (~b & d);
        k = 0x5a827999;
      } else if (i < 40) {
        f = b ^ c ^ d;
        k = 0x6ed9eba1;
      } else if (i < 60) {
        f = (b & c) | (b & d) | (c & d);
        k = 0x8f1bbcdc;
      } else {
        f = b ^ c ^ d;
        k = 0xca62c1d6;
      }
      const temp = (rotl(a, 5) + (f >>> 0) + e + k + w[i]) >>> 0;
      e = d;
      d = c;
      c = rotl(b, 30);
      b = a;
      a = temp;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }
  return [h0, h1, h2, h3, h4].map((x) => x.toString(16).padStart(8, "0")).join("");
}

// ── The key ──────────────────────────────────────────────────────────────────

export function entryKey(
  kind: EvidenceKind,
  company: string,
  target: string,
  label: string,
  signal: string
): string {
  const raw = [kind, company, target, label, signal].join("|");
  return sha1Hex(new TextEncoder().encode(raw)).slice(0, 16);
}

export function refKey(ref: EvidenceRef): string {
  return entryKey(ref.kind, ref.company, ref.target, ref.label, ref.signal);
}

// Unit-style self-check: the two SHA-1 test vectors everyone knows, plus two keys
// computed with evidence.py (entry_key) — one of them full of non-ASCII characters so
// the UTF-8 step is exercised. Returns true when this file reproduces Python exactly.
export function evidenceSelfCheck(): boolean {
  const enc = new TextEncoder();
  const checks: [string, string][] = [
    [sha1Hex(enc.encode("abc")), "a9993e364706816aba3e25717850c26c9cd0d89d"],
    [sha1Hex(enc.encode("")), "da39a3ee5e6b4b0d3255bfef95601890afd80709"],
    [
      entryKey(
        "qd",
        "SK Hynix",
        "",
        "SK Hynix Q2 FY2026 (08-14-2026)",
        "HBM4 → 12-high; revenue 27조 8,000억원 — “record”"
      ),
      "5b1395e8a335588d",
    ],
    [
      entryKey(
        "contract",
        "Amazon Web Services",
        "Anthropic",
        "NVIDIA Q1 FY2027 (05-28-2026)",
        "AWS expanding Anthropic's compute capacity"
      ),
      "180c0758bd142fdf",
    ],
  ];
  return checks.every(([got, want]) => got === want);
}

// ── Loader ───────────────────────────────────────────────────────────────────
// Fetched at most once per page load (module-level promise cache). A missing file
// (404 — evidence.py has not run yet) or a network error yields an empty map, so the
// UI degrades to "no evidence record" instead of breaking.

let evidencePromise: Promise<EvidenceMap> | null = null;

export function loadEvidence(): Promise<EvidenceMap> {
  if (!evidencePromise) {
    evidencePromise = fetch("/data/evidence.json")
      .then(async (res) => {
        if (!res.ok) return new Map<string, EvidenceEntry>();
        const file = (await res.json()) as EvidenceFile;
        return new Map<string, EvidenceEntry>(Object.entries(file.entries || {}));
      })
      .catch(() => new Map<string, EvidenceEntry>());
  }
  return evidencePromise;
}

// Convenience: the record for one entry, or null when there is none.
export async function lookupEvidence(ref: EvidenceRef): Promise<EvidenceEntry | null> {
  const map = await loadEvidence();
  return map.get(refKey(ref)) ?? null;
}
