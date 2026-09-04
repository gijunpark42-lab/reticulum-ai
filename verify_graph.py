"""
verify_graph.py — independent cross-verification of every data point in the merged graph.

What this is
------------
Enrichment (Workflow 2 / 2b) ADDS entries to the graph. Nothing, until now, ever went back
and asked: "is this entry actually supported by the document it claims to come from?"
This script does exactly that, from the outside:

  * it never touches chains/ or graph/merged_graph.json (read-only);
  * it does not trust the enrichment job — it re-opens the SOURCE FILE the entry's label
    points at (transcripts/**, supply_contracts/*) and checks the entry against the text;
  * it writes one report: graph/verification.json (+ a console summary).

Think of it as an auditor that was not in the room when the data was written.

The four checks, per entry
--------------------------
Every quarterly_data entry (node) and every contracts entry (edge) gets:

  1. SOURCE   — does the label ("NVIDIA Q2 FY2027 (08-26-2026)") resolve to a file on disk?
                Resolution order: exact "# source label:" header in the file → filename join
                (agent/corpus.py, "<company>_q<N>_<year>.txt") → loose event-name match
                ("nvda_gtc_taipei_2026.txt" for "NVIDIA GTC Taipei 2026 (…)").
  2. NUMBERS  — every number written in `figure` / `units` / `value` (e.g. "$107M", "45%",
                "27조 8,000억원", "1.6T") must appear in that document. Numbers are the part
                of an entry that can be checked mechanically; a paraphrased `signal` cannot.
                Entries with no numbers ("no specific figure") are "unchecked", not "passed".
  3. PARTY    — for a contract on edge A → B, the source document must mention the OTHER
                company (the one the document is not about). A deal with Meta that never
                says "Meta" is suspicious.
  4. HYGIENE  — label follows the canonical format, and no Korean characters leaked into
                the chain (Workflow 2b rule).

Plus one check per EDGE (not per entry) — the real "cross" in cross-verification:

  5. CORROBORATION — how many INDEPENDENT sources back this edge?
        two_sided     : A's own documents mention B  AND  B's own documents mention A.
                        Two companies, on their own earnings calls / filings, each naming
                        the other. This is the strongest evidence the corpus can give.
        multi_source  : contracts from ≥2 different companies' documents.
        single_source : only one side has ever said it.
        no_contracts  : skeleton edge (curated structure, no deal data yet) — not judged.

Verdict per entry:  pass | warn | fail | unchecked
  fail      — source file missing, or a number is not in the document, or Korean chars.
  warn      — counterparty not found in the document, or label format off.
  unchecked — source resolved but the entry carries nothing checkable (no numbers).

How to run
----------
    python verify_graph.py                 # full report → graph/verification.json
    python verify_graph.py --company NVIDIA
    python verify_graph.py --label "Samsung Q2 FY2026 (08-14-2026)"
    python verify_graph.py --fails         # print only failing entries

Exit code is 1 when any entry FAILS, so this can gate a build or a commit later.
"""

import argparse
import glob
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

# We reuse two helpers the agent already has, rather than re-inventing them:
#   normalize()                — folds curly quotes / dashes / whitespace so quotes match
#   find_document_for_label()  — joins "Rambus Q2 FY2026 (…)" to transcripts/**/rambus_q2_2026.txt
from agent.verify import normalize
from agent.corpus import list_documents, find_document_for_label, normalize_company

GRAPH_PATH = "graph/merged_graph.json"
REPORT_PATH = "graph/verification.json"
DOC_GLOBS = ["transcripts/**/*.txt", "supply_contracts/*.txt"]

LABEL_EARNINGS = re.compile(r"^.+ Q[1-4] FY20\d\d \(\d\d-\d\d-\d{4}\)$")
LABEL_OTHER = re.compile(r"^.+ \(\d\d-\d\d-\d{4}\)$")   # events, notes, DART supply contracts
KOREAN = re.compile(r"[가-힣]")

# Korean filings write counterparties in Korean. This small table lets the PARTY check
# recognise the big names inside a DART document; anything not listed is matched on its
# English node name only (and reported honestly as not found if the filing is Korean-only).
KO_ALIASES = {
    "Samsung": ["삼성전자"], "Samsung Foundry": ["삼성전자", "삼성파운드리"],
    "SK Hynix": ["SK하이닉스", "에스케이하이닉스"], "Samsung Electro-Mechanics": ["삼성전기"],
    "Hanmi Semiconductor": ["한미반도체"], "HD Hyundai Electric": ["HD현대일렉트릭", "현대일렉트릭"],
    "LS Electric": ["LS일렉트릭", "LS ELECTRIC"], "Doosan Enerbility": ["두산에너빌리티"],
    "Hyosung Heavy": ["효성중공업"], "Sanil Electric": ["산일전기"], "LG Electronics": ["LG전자"],
    "Hyundai Motor": ["현대자동차", "현대차"], "Korea Electric Power": ["한국전력", "한전"],
    "Naver": ["네이버"], "Samsung SDI": ["삼성SDI"], "LG Energy Solution": ["LG에너지솔루션"],
    "TSMC": ["TSMC"], "NVIDIA": ["엔비디아"], "Micron": ["마이크론"], "Intel": ["인텔"],
    "Google": ["구글"], "Microsoft": ["마이크로소프트"], "Amazon Web Services": ["아마존", "AWS"],
    "Meta": ["메타"], "Apple": ["애플"], "Tesla": ["테슬라"], "ASML": ["ASML"],
}


# ---------------------------------------------------------------------------
# 1. Load every source document once, indexed by its "# source label:" header
# ---------------------------------------------------------------------------

def compact(text):
    """Lowercase alphanumerics only: 'SK Hynix' -> 'skhynix'. Used for name matching."""
    return re.sub(r"[^a-z0-9가-힣]", "", unicodedata.normalize("NFKC", text).lower())


NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


class Doc:
    """One source document (or one ==== block of a supply_contracts file)."""

    def __init__(self, path, text, label=None):
        self.path = path.replace("\\", "/")
        self.text = text
        self.label = label                    # from the "# source label:" header, if present
        self.norm = normalize(text)           # for number matching
        self.norm_nocomma = self.norm.replace(",", "")
        self.compact = compact(text)          # for company-name matching

    def mentions(self, company):
        """Does this document name `company` (English node name or a Korean alias)?"""
        names = [company] + KO_ALIASES.get(company, [])
        for name in names:
            key = compact(name)
            if len(key) >= 3 and key in self.compact:
                return True
        # Fall back to the first word when it is distinctive ("Vistra Corp" -> "vistra")
        first = compact(company.split()[0]) if company.split() else ""
        return len(first) >= 5 and first in self.compact

    def has_number(self, number):
        """Is this number in the document? Four ways to say yes, loosest last:

        1. exact text          "3.274"  in the document (commas ignored on both sides)
        2. trailing zeros      "14.0" / "4.00"  ->  "14" / "4"        ("$14 billion")
        3. rounding            "88.9"  matches a document value 88.86  (we round the
                               document's numbers to the figure's own decimals)
        4. unit rescale        "1.898" (B) matches "1,898" (M); "50.9" (KRW B) matches a
                               filing's "50,912,345,678" (won) or "50,912" (백만원) — same
                               digits, different unit.
        """
        n = number.replace(",", "")
        if n in self.norm_nocomma:
            return True
        if "." in n and n.rstrip("0").rstrip(".") in self.norm_nocomma:
            return True
        try:
            value = float(n)
        except ValueError:
            return False
        decimals = len(n.split(".")[1]) if "." in n else 0
        if value in self._rounded(decimals):
            return True
        # "1.898" (B) vs "1,898" (M) share the digit string 1898; "484.1" (B) vs a
        # filing's 484,123 (백만원) share the prefix 4841.
        digits = re.sub(r"\D", "", n).lstrip("0")
        return len(digits) >= 3 and any(
            run == digits or (run.startswith(digits) and len(run) >= 5) for run in self._digit_runs())

    def _values(self):
        """Every number in the document as a float, parsed once and cached."""
        if not hasattr(self, "_vals"):
            vals = set()
            for m in NUMBER.findall(self.norm):
                try:
                    vals.add(float(m.replace(",", "")))
                except ValueError:
                    pass
            self._vals = vals
        return self._vals

    def _rounded(self, decimals):
        """The document's numbers rounded to `decimals` places, cached per precision."""
        if not hasattr(self, "_round_cache"):
            self._round_cache = {}
        if decimals not in self._round_cache:
            self._round_cache[decimals] = {round(v, decimals) for v in self._values()}
        return self._round_cache[decimals]

    def _digit_runs(self):
        """Long digit runs (commas stripped) — raw KRW/JPY amounts in filings."""
        if not hasattr(self, "_runs"):
            self._runs = set(re.findall(r"\d{3,}", self.norm_nocomma))
        return self._runs


def load_documents():
    """Read every txt under transcripts/ and supply_contracts/ into Doc objects.

    Returns (by_label, all_docs). by_label maps an exact source label -> Doc.
    supply_contracts files hold several filings separated by ==== lines; each becomes
    its own Doc so a contract label points at exactly the filing it came from.
    """
    by_label = {}
    all_docs = []
    header = re.compile(r"^#\s*source label:\s*(.+?)\s*$", re.M)
    for pattern in DOC_GLOBS:
        for path in sorted(glob.glob(pattern, recursive=True)):
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
            blocks = re.split(r"^={20,}\s*$", raw, flags=re.M) if path.startswith("supply_contracts") else [raw]
            for block in blocks:
                if not block.strip():
                    continue
                m = header.search(block[:2000])
                doc = Doc(path, block, m.group(1) if m else None)
                all_docs.append(doc)
                if doc.label:
                    by_label.setdefault(doc.label, doc)
    return by_label, all_docs


# Filename abbreviations that agent/corpus.py's alias table does not know about.
FILE_ALIASES = {"stmicroelectronics": "stm", "mksinstruments": "mks",
                "tokyoohkakogyo": "tok", "aehrtestsystems": "aehr"}


def same_company(a, b):
    """Strict company-token match: equal, or one is a full prefix of the other (>= 5 chars).

    'nvidia' vs 'nvda' is handled by the alias table in agent/corpus.py before we get here;
    'appliedmaterials' vs 'applieddigital' is rejected (neither is a prefix of the other).
    """
    a, b = FILE_ALIASES.get(a, a), FILE_ALIASES.get(b, b)
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 5 and long_.startswith(short)


def resolve_label(label, by_label, all_docs, filename_docs, cache):
    """Find the Doc a source label refers to, or None. Three strategies, in order."""
    if label in cache:
        return cache[label]
    doc = by_label.get(label)
    if doc is None:
        # Strategy 2: filename join for earnings labels ("<company>_q<N>_<year>.txt").
        # agent/corpus.py matches on a 7-letter prefix, which sent "Applied Materials" to
        # applied_digital_q3_2026.txt — so we re-check the company token strictly here:
        # one token must be a prefix of the other in full ("micron" ~ "microntechnology").
        hit = find_document_for_label(label, filename_docs)
        if hit is not None and same_company(label_company(label), hit.company_token):
            doc = next((d for d in all_docs if d.path == hit.path), None)
        else:
            m = re.match(r"^(?P<company>.+?)\s+Q(?P<q>[1-4])\s+FY(?P<y>20\d\d)", label)
            if m:
                lc = normalize_company(m.group("company"))
                for fd in filename_docs:
                    if fd.quarter == int(m.group("q")) and fd.year == int(m.group("y"))                             and same_company(lc, fd.company_token) and fd.is_full_transcript:
                        doc = next((d for d in all_docs if d.path == fd.path), None)
                        break
    if doc is None:
        # Strategy 3: loose match for events/notes. Filename tokens (minus the year)
        # must all appear in the label, and the company token must match.
        #   nvda_gtc_taipei_2026.txt  <->  "NVIDIA GTC Taipei 2026 (06-01-2026)"
        lab = compact(label)
        lab_company = normalize_company(re.split(r"\s+(Q[1-4]|FY|GTC|DART|\d{4}|\()", label)[0])
        for d in all_docs:
            stem = os.path.basename(d.path)[:-4]
            tokens = stem.split("_")
            if not tokens:
                continue
            if not same_company(lab_company, normalize_company(tokens[0])):
                continue
            rest = [t for t in tokens[1:] if not re.fullmatch(r"(fy)?20\d\d|q[1-4]", t)]
            if rest and all(t in lab for t in rest):
                doc = d
                break
    cache[label] = doc
    return doc


# ---------------------------------------------------------------------------
# 2. Per-entry checks
# ---------------------------------------------------------------------------

def numbers_in(*fields):
    """Pull every number out of the free-text fields ('$107M', '45%', '27조 8,000억원').

    Years (2024-2030) and single digits are skipped — they are too common to prove anything.
    """
    found = []
    for field in fields:
        if not field or not isinstance(field, str):
            continue
        for n in NUMBER.findall(field):
            bare = n.replace(",", "")
            if re.fullmatch(r"20[2-3]\d", bare) or len(bare) < 2:
                continue
            found.append(n)
    return list(dict.fromkeys(found))   # dedupe, keep order


def check_entry(label, doc, fields, counterparty=None):
    """Run SOURCE / NUMBERS / PARTY / HYGIENE on one entry; return (verdict, issues, detail)."""
    issues = []
    detail = {}

    # HYGIENE
    all_text = " ".join(v for v in fields.values() if isinstance(v, str)) + " " + label
    if KOREAN.search(all_text):
        issues.append("korean_characters")
    if not (LABEL_EARNINGS.match(label) or LABEL_OTHER.match(label)):
        issues.append("label_format")

    # SOURCE
    if doc is None:
        issues.append("source_not_found")
        return "fail", issues, detail
    detail["doc"] = doc.path

    # NUMBERS
    nums = numbers_in(fields.get("figure"), fields.get("units"), fields.get("value"))
    missing = [n for n in nums if not doc.has_number(n)]
    detail["numbers"] = nums
    if missing:
        issues.append("number_not_in_source")
        detail["numbers_missing"] = missing

    # PARTY (edges only)
    if counterparty is not None:
        if doc.mentions(counterparty):
            detail["counterparty"] = "mentioned"
        else:
            issues.append("counterparty_not_in_source")
            detail["counterparty"] = "not_found"

    if "korean_characters" in issues or "number_not_in_source" in issues:
        return "fail", issues, detail
    if issues:
        return "warn", issues, detail
    if not nums and counterparty is None:
        return "unchecked", issues, detail
    return "pass", issues, detail


# ---------------------------------------------------------------------------
# 3. Per-edge corroboration
# ---------------------------------------------------------------------------

def label_company(label):
    """'Broadcom Q2 FY2026 (06-03-2026)' -> 'broadcom'; 'Goldman Sachs optical note (…)' -> 'goldmansachs…'."""
    head = re.split(r"\s+(Q[1-4]\s+FY|DART|GTC|Computex|\(|note)", label)[0]
    return normalize_company(head)


def corroborate(edge, docs_by_company, resolved):
    """Classify an edge's evidence: two_sided / multi_source / single_source / no_contracts."""
    contracts = edge.get("contracts", [])
    if not contracts:
        return "no_contracts", {}
    a, b = edge["source"], edge["target"]
    a_docs = docs_by_company.get(normalize_company(a), [])
    b_docs = docs_by_company.get(normalize_company(b), [])
    a_says_b = any(d.mentions(b) for d in a_docs)
    b_says_a = any(d.mentions(a) for d in b_docs)
    source_companies = {label_company(c.get("source", "")) for c in contracts}
    detail = {"a_docs": len(a_docs), "b_docs": len(b_docs),
              "a_mentions_b": a_says_b, "b_mentions_a": b_says_a,
              "source_companies": sorted(source_companies)}
    if a_says_b and b_says_a:
        return "two_sided", detail
    if len(source_companies) >= 2:
        return "multi_source", detail
    return "single_source", detail


def index_docs_by_company(all_docs, node_names):
    """Map each graph node -> the documents that are ABOUT that company.

    A document is 'about' a company when its header label or filename starts with the
    company's token. This is what makes the two_sided check independent: it only uses
    what a company said in its OWN filings, not what others said about it.
    """
    index = defaultdict(list)
    for doc in all_docs:
        token = label_company(doc.label) if doc.label else normalize_company(os.path.basename(doc.path).split("_")[0])
        for name in node_names:
            key = normalize_company(name)
            if key == token or (len(key) >= 5 and (key[:7] == token[:7])):
                index[key].append(doc)
    return index


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def run(company_filter=None, label_filter=None, labels=None):
    """labels: optional list — check only entries whose source label is in it
    (graph_build.py passes the labels of the patches it just applied)."""
    with open(GRAPH_PATH, encoding="utf-8") as f:
        graph = json.load(f)

    by_label, all_docs = load_documents()
    filename_docs = list_documents()          # agent/corpus.py filename index
    node_names = [n["id"] for n in graph["nodes"]]
    docs_by_company = index_docs_by_company(all_docs, node_names)
    cache = {}

    def wanted(company, label):
        if company_filter and compact(company_filter) not in compact(company):
            return False
        if label_filter and label_filter != label:
            return False
        if labels is not None and label not in labels:
            return False
        return True

    entries = []
    # Node-level: quarterly_data
    for node in graph["nodes"]:
        for q in node.get("quarterly_data", []):
            label = q.get("quarter", "")
            if not wanted(node["id"], label):
                continue
            doc = resolve_label(label, by_label, all_docs, filename_docs, cache)
            verdict, issues, detail = check_entry(label, doc, q)
            entries.append({"kind": "quarterly_data", "company": node["id"], "label": label,
                            "signal": (q.get("signal") or "")[:140], "figure": q.get("figure"),
                            "verdict": verdict, "issues": issues, **detail})
    # Edge-level: contracts
    edge_reports = []
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        for c in edge.get("contracts", []):
            label = c.get("source", "")
            if not wanted(a, label) and not wanted(b, label):
                continue
            doc = resolve_label(label, by_label, all_docs, filename_docs, cache)
            # Which side is the document about? The check looks for the OTHER one.
            doc_company = label_company(label)
            other = b if normalize_company(a)[:5] == doc_company[:5] else a
            verdict, issues, detail = check_entry(label, doc, c, counterparty=other)
            entries.append({"kind": "contract", "company": a, "target": b, "label": label,
                            "signal": (c.get("signal") or "")[:140], "value": c.get("value"),
                            "verdict": verdict, "issues": issues, **detail})
        if edge.get("contracts") and (wanted(a, "") or wanted(b, "")) and not label_filter and labels is None:
            tier, detail = corroborate(edge, docs_by_company, cache)
            edge_reports.append({"source": a, "target": b, "chain": edge.get("chain"),
                                 "relationship": edge.get("relationship"),
                                 "contracts": len(edge["contracts"]), "tier": tier, **detail})

    # Which labels never resolved — the single most actionable list
    unresolved = sorted({e["label"] for e in entries if "source_not_found" in e["issues"]})

    summary = {
        "entries_checked": len(entries),
        "verdicts": dict(Counter(e["verdict"] for e in entries)),
        "issues": dict(Counter(i for e in entries for i in e["issues"])),
        "edges_with_contracts": len(edge_reports),
        "edge_tiers": dict(Counter(r["tier"] for r in edge_reports)),
        "unresolved_labels": unresolved,
        "documents_indexed": len(all_docs),
    }
    return summary, entries, edge_reports


def verify_labels(labels):
    """Post-enrichment gate, called by graph_build.py right after a build.

    Checks ONLY the entries that came from `labels` (the patches just applied) and
    prints every fail/warn so the enrichment job can fix its own patch while the
    transcript is still open. Returns the number of failing entries.
    """
    summary, entries, _ = run(labels=labels)
    print("\nverify_graph — %d new entr%s from %d label(s): %s" % (
        summary["entries_checked"], "y" if summary["entries_checked"] == 1 else "ies",
        len(labels), summary["verdicts"]))
    for e in entries:
        if e["verdict"] in ("fail", "warn"):
            who = e["company"] + (" -> %s" % e["target"] if e.get("target") else "")
            extra = "  missing=%s" % e["numbers_missing"] if e.get("numbers_missing") else ""
            print("  [%s] %s | %s | %s%s" % (e["verdict"], who, e["label"], ", ".join(e["issues"]), extra))
            print("          %s" % e["signal"])
    return summary["verdicts"].get("fail", 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--company", help="only entries touching this company (substring)")
    ap.add_argument("--label", help="only entries with exactly this source label")
    ap.add_argument("--fails", action="store_true", help="print every fail/warn entry")
    args = ap.parse_args()

    summary, entries, edges = run(args.company, args.label)

    if not args.company and not args.label:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "entries": entries, "edges": edges}, f,
                      ensure_ascii=False, indent=1)

    print(f"documents indexed : {summary['documents_indexed']}")
    print(f"entries checked   : {summary['entries_checked']}   {summary['verdicts']}")
    print(f"issues            : {summary['issues']}")
    print(f"edges w/ contracts: {summary['edges_with_contracts']}   {summary['edge_tiers']}")
    if summary["unresolved_labels"]:
        print(f"\nunresolved labels ({len(summary['unresolved_labels'])}) — no source file on disk:")
        for lab in summary["unresolved_labels"]:
            print(f"  - {lab}")
    if args.fails or args.company or args.label:
        print()
        for e in entries:
            if e["verdict"] in ("fail", "warn"):
                who = e["company"] + (f" -> {e['target']}" if e.get("target") else "")
                extra = f"  missing={e['numbers_missing']}" if e.get("numbers_missing") else ""
                print(f"[{e['verdict']}] {who} | {e['label']} | {', '.join(e['issues'])}{extra}")
                print(f"        {e['signal']}")
    if not args.company and not args.label:
        print(f"\nreport → {REPORT_PATH}")
    sys.exit(1 if summary["verdicts"].get("fail") else 0)


if __name__ == "__main__":
    main()
