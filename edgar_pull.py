"""Pull company-primary SEC documents for the mapped US tickers into transcripts/edgar/.

Company documents only (the map's rule), saved WHOLE — see the completeness contract in
.claude/skills/enrich/references/edgar.md (every filing is read once and never has to be reopened):
  * 8-K current reports: every relevant Item + EVERY EX-99 exhibit in full (400k safety cap, marked when hit)
  * latest 10-K: <T>_10-K_<date>_customers.txt  = every customer-concentration paragraph + XBRL concentration
                 (us-gaap:ConcentrationRiskPercentage1 by srt:MajorCustomersAxis) and segment revenue facts
                 <T>_10-K_<date>_supplychain.txt = every paragraph of the full text naming a mapped company or a
                 supplier / foundry / contract-manufacturer / supply-agreement / backlog / capex term
  * latest 10-Q: <T>_10-Q_<date>_segments.txt (XBRL segment revenue with YoY) + <T>_10-Q_<date>_supplychain.txt
Nothing here touches chains/ or graph/; the saved text files are enrichment inputs, to be
processed like transcripts (source label e.g. "Lumentum 8-K (08-11-2026)").

    python edgar_pull.py                      # all mapped US tickers, EVERY 8-K since --since (default 120 days) + latest 10-K
    python edgar_pull.py --tickers LITE,SMCI  # a few names
    python edgar_pull.py --since 2026-06-01   # older window
    python edgar_pull.py queue                # build edgar/pending.json = the low-noise `enrich edgar` queue
    python edgar_pull.py done                 # mark the queue as enriched (moves rows to edgar/done.json)
    <TICKER>_10-Q_<date>_segments.txt         # XBRL segment / product revenue with YoY (+ customer % if the 10-Q tags it)
    edgar/STATUS.md                           # generated table: every file -> queued / enriched / dropped (why)

Files carry a "# source label:" header (canonical: "Lumentum 8-K (08-11-2026)", "Lumentum 10-K (08-17-2026)")
so verify_graph.py can resolve entries back to them.

Needs EDGAR_USER_AGENT in .env (a contact e-mail; quote it if it contains spaces).
Library: edgartools (pip install edgartools), MIT, no API key.
"""
import argparse
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "transcripts" / "edgar"
US_EXCHANGES = {"NASDAQ", "NYSE", "NYSE American", "AMEX"}
ITEMS_8K = ("1.01", "1.02", "2.02", "2.05", "5.02", "7.01", "8.01")
# An Item HEADING starts a line (optionally after table-cell pipes). A cross-reference inside a sentence ("as described
# in Item 9.01 below") must not open a new section — it used to, and the rest of the real section was dropped
# whenever the referenced item was not in ITEMS_8K (found 2026-09-11: 169 sections cut mid-sentence).
ITEM_RE = re.compile(r"(?im)^[ \t|]*item\s+(\d\.\d\d)")
EXHIBIT_CAP = 400000      # safety net only (completeness rule: exhibits are saved whole; a cut one is marked + flagged)
FORCE = False
PENDING = ROOT / "edgar" / "pending.json"
DONE = ROOT / "edgar" / "done.json"
STATUS = ROOT / "edgar" / "STATUS.md"

# Queue filter (accuracy first, low noise). An 8-K is queued only when it carries supply-chain
# information; earnings releases (2.02) are NOT queued because the call transcript for that quarter
# is the richer source and is enriched via av.py (the 8-K file stays on disk as a companion document
# for verify_graph.py). Personnel (5.02), credit lines, dividends, buybacks, annual meetings are noise.
KEEP_WORDS = ("supply agreement", "purchase agreement", "master agreement", "manufacturing agreement",
              "license agreement", "collaboration agreement", "development agreement", "design win",
              "customer", "capacity", "backlog", "purchase order", "orders", "guidance", "raises", "lowers",
              "data center", "hyperscaler", "wafer", "hbm", "foundry", "packaging", "substrate", "optical",
              "transceiver", "accelerator", "gpu", "ramp", "expansion", "investment of", "megawatt", "gigawatt")
DROP_WORDS = ("credit agreement", "credit line", "credit facility", "loan agreement", "indenture", "notes due",
              "dividend", "repurchase program", "annual meeting", "employment agreement", "severance",
              "retirement", "resign", "appointed", "amended and restated bylaws", "stockholder rights")


def mapped_us_tickers():
    graph = json.loads((ROOT / "graph" / "merged_graph.json").read_text(encoding="utf-8"))
    out = {}
    for n in graph["nodes"]:
        t = (n.get("ticker") or "").strip().upper()
        if t and n.get("status") == "public" and n.get("exchange") in US_EXCHANGES:
            out[t] = n["id"]
    return out


def split_items(text):
    """{item: text} for an 8-K body, keyed by 'Item 1.01' style numbers."""
    marks = [(m.start(), m.group(1)) for m in ITEM_RE.finditer(text)]
    items = {}
    for i, (pos, item) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        chunk = text[pos:end].strip()
        if item in ITEMS_8K and len(chunk) > 80:
            items[item] = items.get(item, "") + chunk + "\n"
    return items


SENTENCE_END_RE = re.compile(r"[.!?:;\"”’)\]]\s*$")
FURNITURE_RE = re.compile(r"^(\d{1,3}|[ivxlc]{1,6}|table of contents|index)$", re.I)   # page numbers / running headers
BLOCK_TAGS = ["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"]


def html_to_text(html):
    """Plain text from a filing's HTML: one blank line after every block element, table cells kept apart with
    ' | ' so a table row stays on one line, scripts / styles / the hidden inline-XBRL header removed."""
    import unicodedata
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(lambda t: t.name and t.name.lower() == "ix:header"):
        tag.decompose()
    # Line breaks in the HTML SOURCE are not line breaks on the page: a filer's "<td>\n\n1,051,500\n</td>" split one
    # table row into pieces (found 2026-09-11: Vishay's backlog / book-to-bill table was filtered away). Collapse
    # every run of whitespace inside the text to one space; the only newlines left are the structural ones added below.
    from bs4 import NavigableString
    for s in list(soup.find_all(string=True)):
        if isinstance(s, NavigableString) and re.search(r"\s\s|[\n\r\t]", s):
            s.replace_with(re.sub(r"\s+", " ", str(s)))
    for br in soup.find_all("br"):
        br.replace_with("\n")
    # Some releases file whole pages as pictures (found 2026-09-11: Linde's 07-31 EX-99.1 pages 4-10 are
    # lin_ex991img4..14.jpg). An image has no text, so leave a visible marker where it sits — a reader then
    # knows content exists that the text does not hold, instead of the file silently "ending" early.
    for img in soup.find_all("img"):
        img.replace_with(f"\n[image: {img.get('src', '?')} — not text]\n")
    for cell in soup.find_all(["td", "th"]):
        cell.append(" | ")
    for block in soup.find_all(BLOCK_TAGS):
        # A <p>/<div> INSIDE a table cell must not break the row: a blank line there split one row into pieces,
        # so a table stopped looking like a table and was filtered away (found 2026-09-11: Intel's segment
        # operating-income table, Vishay's backlog / book-to-bill table).
        if block.name not in ("tr", "table") and block.find_parent(["td", "th"]) is not None:
            block.append(" ")
        else:
            block.append("\n\n")
    text = unicodedata.normalize("NFKC", soup.get_text())
    return re.sub(r"[ \t]+", " ", text)


def document_text(doc):
    """Full text of a filing or an exhibit, built from its HTML.

    Never edgartools' .text() when HTML exists: its renderer shortens some blocks with "..." (found 2026-09-10:
    Hut 8's "Right of First Offer for up to an additional 1,000 M..."; a Credo EX-99.1 lost ~9% of its text).
    Filings expose .html(); attachments expose .download(). .text() is only the fallback for non-HTML documents."""
    html = None
    try:
        if hasattr(doc, "html"):
            html = doc.html()
        elif hasattr(doc, "download"):
            raw = doc.download()
            if isinstance(raw, bytes) and raw[:5] == b"%PDF-":
                html = None                          # a PDF exhibit is binary: never parse it as HTML
            else:
                html = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    except Exception:
        html = None
    head = html[:5000].lower() if isinstance(html, str) else ""
    if any(tag in head for tag in ("<html", "<body", "<div", "<p", "<table", "<font")):
        return html_to_text(html)
    try:
        return doc.text() or ""
    except Exception:
        return ""


def paragraphs(text):
    """Blank-line paragraphs of a filing, with page-break fragments re-joined.

    The SEC text breaks paragraphs at page boundaries, even mid-sentence ("In February 2026, the Virginia" |
    "Commission denied the reconsideration petition ..."). A fragment that does not end a sentence is joined to the
    next block, so a keyword match on the first half never loses the second half (completeness contract)."""
    merged = []
    for block in re.split(r"\n\s*\n", text):
        flat = " ".join(block.split())
        if not flat or FURNITURE_RE.match(flat):          # page numbers / "Table of Contents" between two halves
            continue
        table_row = " | " in flat or (merged and " | " in merged[-1])   # never glue table rows together
        if merged and not table_row and not SENTENCE_END_RE.search(merged[-1]) and not flat.startswith(("•", "Item ", "ITEM ")):
            merged[-1] = merged[-1] + " " + flat
        else:
            merged.append(flat)
    return merged


def table_blocks(paras):
    """[(is_table, text)] with consecutive table rows joined into ONE block (rows kept on their own lines).

    The HTML text gives every <tr> its own paragraph, so a table arrives as dozens of short rows. Filtering row by row
    dropped every table (found 2026-09-11: segment revenue, segment EBITDA and capex tables vanished from 117 of 135
    10-K supplychain files). A table is judged — and kept or dropped — as a whole."""
    out = []
    for p in paras:
        flat = " ".join(p.split())
        if not flat:
            continue
        is_row = " | " in flat
        if is_row and out and out[-1][0]:
            out[-1] = (True, out[-1][1] + "\n" + flat)
        else:
            out.append((is_row, flat))
    return out


CUSTOMER_TABLE_RE = re.compile(r"(?i)customer|end market|concentration")


def customer_paragraphs(text):
    """Every paragraph of a 10-K that talks about customer concentration or major customers, whole — and every table
    about customers / end markets, whole, with the sentence that introduces it."""
    blocks = table_blocks(paragraphs(text))
    keep = []
    for i, (is_table, flat) in enumerate(blocks):
        low = flat.lower()
        if is_table:
            lead = blocks[i - 1][1] if i and not blocks[i - 1][0] else ""
            if CUSTOMER_TABLE_RE.search(flat) or CUSTOMER_TABLE_RE.search(lead):
                if lead and lead not in keep:
                    keep.append(lead)
                keep.append(flat)
        elif ("customer" in low and ("10%" in low or "ten percent" in low or "concentration" in low
                                     or "largest customer" in low or "accounted for" in low)):
            if flat not in keep:
                keep.append(flat)
    return keep


# Supplier / manufacturing disclosures live in the 10-K Business and Risk Factors sections, not in the
# customer-concentration paragraphs above ("we utilize foundries such as TSMC", "third-party contractors
# such as Amkor and ASE"). They carry the supplier -> filer edges of the map.
SUPPLY_RE = re.compile(r"(?i)sole[- ]source|single[- ]source|limited number of (suppliers|sources|vendors)|"
                       r"contract manufactur|third[- ]party manufactur|foundr(y|ies)|supply agreement|"
                       r"capacity reservation|prepayment|purchase (commitment|obligation)|long[- ]term supply|"
                       r"take[- ]or[- ]pay|subcontract|backlog|remaining performance obligation|"
                       r"capital expenditure|manufacturing capacity|capacity expansion")
BOILERPLATE_RE = re.compile(r"(?i)incorporated by reference|exhibit description|pursuant to the requirements of")
# Tables worth keeping in a supplychain file: segment / revenue / capex / backlog / customer / capacity tables.
TABLE_KEEP_RE = re.compile(r"(?i)segment|revenue|net sales|capital expenditure|purchases of property|backlog|"
                           r"remaining performance|customer|end market|purchase (commitment|obligation)|capacity")


def supply_chain_paragraphs(text, company, names, skip=()):
    """EVERY paragraph of a full 10-K / 10-Q that names another mapped company and/or describes a supply
    dependency, backlog or capex — whole and in document order (completeness rule: no cap, no cut). Tables are
    judged whole (table_blocks): a segment / revenue / capex / backlog / customer table is kept with its lead-in."""
    patterns = [re.compile(r"\b" + re.escape(n) + r"\b") for n in names if n != company and len(n) >= 4]
    blocks = table_blocks(re.split(r"\n\s*\n", text))
    keep = []
    for i, (is_table, flat) in enumerate(blocks):
        if flat in skip or flat in keep or BOILERPLATE_RE.search(flat):
            continue
        if is_table:
            lead = blocks[i - 1][1] if i and not blocks[i - 1][0] else ""
            if (TABLE_KEEP_RE.search(flat) or TABLE_KEEP_RE.search(lead) or SUPPLY_RE.search(flat)
                    or any(rx.search(flat) for rx in patterns)):
                if lead and lead not in keep and lead not in skip:
                    keep.append(lead)
                keep.append(flat)
            continue
        if len(flat) < 120:
            continue
        if SUPPLY_RE.search(flat) or any(rx.search(flat) for rx in patterns):
            keep.append(flat)
    return keep


def label(company, form, d):
    """Canonical source label, same shape as event labels: 'Lumentum 8-K (08-11-2026)'."""
    return f"{company} {form} ({d.strftime('%m-%d-%Y')})"


def relevance(path, company, names):
    """('keep', why) / ('drop', why) for one saved file — the low-noise queue rule."""
    text = path.read_text(encoding="utf-8")
    low = text.lower()
    if path.name.endswith("_supplychain.txt"):
        return "keep", ("10-Q" if "_10-Q_" in path.name else "10-K") + " supplier / manufacturing / backlog paragraphs"
    if "_10-K_" in path.name:
        return ("keep", "10-K customer concentration") if re.search(r"\d+(\.\d+)?\s*%", text) else ("drop", "10-K: no percentages")
    if "_10-Q_" in path.name:
        return ("keep", "10-Q XBRL segment revenue") if "## XBRL segment revenue" in text else ("drop", "10-Q: no segment facts")
    items = set(re.findall(r"^## Item (\d\.\d\d)", text, flags=re.M))
    if items <= {"2.02"}:
        return "drop", "earnings release only (call transcript covers it)"
    if items <= {"5.02", "2.05"}:
        return "drop", "personnel / restructuring only"
    # counterparties: whole-word, case-sensitive ("Nova" must not match "innovation", "nVent" not "inventory")
    partners = sorted(n for n in names if n != company and len(n) >= 4 and re.search(r"\b" + re.escape(n) + r"\b", text))
    kept = [w for w in KEEP_WORDS if w in low]
    dropped = [w for w in DROP_WORDS if w in low]
    if partners:
        return "keep", "names mapped companies: " + ", ".join(partners[:5])
    if len(kept) >= 2 and len(kept) > len(dropped):
        return "keep", "supply-chain terms: " + ", ".join(kept[:5])
    return "drop", "no supply-chain content (" + ", ".join((dropped or kept)[:3] or ["generic"]) + ")"


def build_queue():
    """Rebuild edgar/pending.json from the files on disk, skipping rows already enriched (done.json)."""
    universe = mapped_us_tickers()
    names = set(universe.values())
    done_rows = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else []
    done = {x["file"] for x in done_rows}
    pending, dropped = [], []
    for path in sorted(OUT.glob("*.txt")):
        ticker = path.name.split("_")[0]
        company = universe.get(ticker)
        if not company:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if rel in done:
            continue
        head = path.read_text(encoding="utf-8")[:600]
        m = re.search(r"(?m)^# source label: (.+)$", head)
        if not m:
            continue
        verdict, why = relevance(path, company, names)
        if "[exhibit truncated" in path.read_text(encoding="utf-8"):
            why = "TRUNCATED exhibit (read what exists, report it) - " + why
        row = {"kind": "filing", "company": company, "file": rel, "label": m.group(1).strip(), "why": why}
        (pending if verdict == "keep" else dropped).append(row)
    PENDING.parent.mkdir(exist_ok=True)
    PENDING.write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")
    (PENDING.parent / "dropped.json").write_text(json.dumps(dropped, ensure_ascii=False, indent=1), encoding="utf-8")
    write_status(pending, dropped, done_rows)
    for r in pending:
        print(f"queue  {r['label']:45} {r['why']}")
    print(f"queued {len(pending)} files, dropped {len(dropped)} as noise (edgar/dropped.json) -> {PENDING}; table in {STATUS}")


def write_status(pending, dropped, done):
    """edgar/STATUS.md — every file in transcripts/edgar/ with its state, so an enrichment session can
    see at a glance what is queued, what was enriched, and what was skipped (and why)."""
    rows = [(r["label"], r["file"], "queued", r["why"]) for r in pending]
    rows += [(r["label"], r["file"], "enriched", r.get("why", "")) for r in done]
    rows += [(r["label"], r["file"], "dropped (noise)", r["why"]) for r in dropped]
    rows.sort(key=lambda r: r[1])
    lines = ["# EDGAR filings — enrichment status", "",
             f"Generated by `python edgar_pull.py queue` / `done` on {date.today().isoformat()}. "
             f"queued {len(pending)} · enriched {len(done)} · dropped {len(dropped)}.", "",
             "`dropped (noise)` files were never enriched on purpose: earnings releases (the call transcript covers",
             "them), personnel/financing/dividend items, or 10-K text with no concentration percentages. They stay on",
             "disk as companion documents for verify_graph.py. To force one into the queue, delete its row from",
             "`edgar/dropped.json` is not enough — edit the KEEP/DROP word lists in edgar_pull.py and rerun `queue`.", "",
             "| label | file | status | why |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    STATUS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mark_done(with_dropped=False):
    """Move the queue to done.json. with_dropped=True also marks every noise-filtered file (edgar/dropped.json) as
    read — use it only after a triage pass has read those files (completeness contract, rule 4b)."""
    pending = json.loads(PENDING.read_text(encoding="utf-8")) if PENDING.exists() else []
    done = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else []
    dropped_path = PENDING.parent / "dropped.json"
    dropped = json.loads(dropped_path.read_text(encoding="utf-8")) if dropped_path.exists() else []
    known = {x["file"] for x in done}
    rows = pending + (dropped if with_dropped else [])
    done += [r for r in rows if r["file"] not in known]
    DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    PENDING.write_text("[]", encoding="utf-8")
    if with_dropped:
        dropped_path.write_text("[]", encoding="utf-8")
        dropped = []
    write_status([], dropped, done)
    print(f"marked {len(rows)} files as read / enriched ({len(pending)} queued"
          + (f" + {len(rows) - len(pending)} triaged from dropped" if with_dropped else "") + "); queue is empty")


REV_RE = r"^us-gaap:(Revenues|RevenueFromContractWithCustomer(Excluding|Including)AssessedTax|SalesRevenueNet)$"
SEG_AXES = ("dim_us-gaap_StatementBusinessSegmentsAxis", "dim_srt_ProductOrServiceAxis")
GENERIC_MEMBERS = ("reportable segment", "operating segment", "segments")


def _money(v):
    return f"${v / 1e6:,.1f}M" if abs(v) < 1e9 else f"${v / 1e9:,.2f}B"


def _pct(v):
    """Percent as filed, one decimal kept: a filed 9.6% must never print as "10%" (found 2026-09-10 — the 10%
    customer-concentration threshold is exactly where rounding changes the meaning)."""
    pct = v * 100 if v <= 1.5 else v
    return f"{pct:.1f}".rstrip("0").rstrip(".") + "%"


def xbrl_sections(filing, form):
    """Markdown sections built from the filing's XBRL facts: customer concentration and segment revenue.
    Numbers are copied as filed (no derivation except the YoY % between two filed values)."""
    try:
        df = filing.xbrl().facts.to_dataframe()
    except Exception as exc:
        print(f"  {form} XBRL unavailable ({exc})")
        return ""
    if df is None or df.empty or "concept" not in df.columns:
        return ""
    dim_cols = [c for c in df.columns if c.startswith("dim_")]
    out = []
    # 1) customer concentration: percentage of revenue / receivables per (named or anonymous) customer
    cust_ax = [c for c in dim_cols if c.endswith("MajorCustomersAxis")]
    if cust_ax:
        sub = df[df["concept"].str.contains("ConcentrationRiskPercentage", na=False) & df[cust_ax[0]].notna()]
        rows = []
        for _, r in sub.iterrows():
            bench = str(r.get("dim_us-gaap_ConcentrationRiskByBenchmarkAxis", "") or "")
            kind = ("revenue" if ("Revenue" in bench or "Sales" in bench) else
                    "accounts receivable" if "Receivable" in bench else bench.split(":")[-1].replace("Member", "") or "?")
            try:
                rows.append((re.sub(r"\s*\[Member\[?\s*$", "", str(r["dimension_member_label"])), kind, str(r["period_start"]), str(r["period_end"]), float(r["numeric_value"])))
            except (TypeError, ValueError):
                continue
        rows = sorted(set(rows), key=lambda x: (x[0], x[1], x[3]))
        if rows:
            out += [f"## XBRL customer concentration ({form}; us-gaap:ConcentrationRiskPercentage1 by srt:MajorCustomersAxis)"]
            lines = [f"- {who}: {_pct(v)} of {kind}, period {ps} to {pe}" for who, kind, ps, pe, v in rows]
            out += list(dict.fromkeys(lines))                  # same fact tagged under two axes -> one line
    # 2) segment / product-line revenue: latest period per member with the year-ago comparison
    want_days = (80, 100) if form == "10-Q" else (350, 380)
    seg_lines = []
    for ax in SEG_AXES:
        if ax not in df.columns:
            continue
        others = [c for c in dim_cols if c != ax]
        sub = df[df["concept"].str.match(REV_RE, na=False) & df[ax].notna() & (df["period_type"] == "duration")]
        if others:
            sub = sub[sub[others].isna().all(axis=1)]          # this axis only (no segment x geography cross rows)
        recs = []
        for _, r in sub.iterrows():
            try:
                ps, pe = date.fromisoformat(str(r["period_start"])[:10]), date.fromisoformat(str(r["period_end"])[:10])
                recs.append((str(r["dimension_member_label"]), ps, pe, float(r["numeric_value"])))
            except (TypeError, ValueError):
                continue
        recs = [x for x in recs if want_days[0] <= (x[2] - x[1]).days <= want_days[1]
                and not any(g in x[0].lower() for g in GENERIC_MEMBERS)]
        by_member = {}
        for m, ps, pe, v in recs:
            by_member.setdefault(m, []).append((ps, pe, v))
        for m, xs in by_member.items():
            xs.sort(key=lambda x: x[1])
            ps, pe, v = xs[-1]
            prior = [x for x in xs if 350 <= (pe - x[1]).days <= 380]
            line = f"- {m}: {_money(v)} ({'quarter' if form == '10-Q' else 'fiscal year'} {ps} to {pe})"
            if prior and prior[-1][2]:
                pp, pv = prior[-1][1], prior[-1][2]
                line += f", {(v / pv - 1) * 100:+.1f}% YoY vs {_money(pv)} (period ending {pp})"
            seg_lines.append(line)
        if seg_lines:
            break                                              # prefer business segments; product lines only as fallback
    if seg_lines:
        out += ["", f"## XBRL segment revenue ({form}; revenue by {'business segment' if ax == SEG_AXES[0] else 'product line'}, as filed)"] + seg_lines
    return "\n".join(out).strip()


def pull(ticker, company, since, names=()):
    from edgar import Company
    OUT.mkdir(parents=True, exist_ok=True)
    saved = []
    c = Company(ticker)
    if c is None:
        return saved
    for f in c.get_filings(form="8-K"):
        fd = f.filing_date if isinstance(f.filing_date, date) else date.fromisoformat(str(f.filing_date))
        if fd < since:
            break
        path = OUT / f"{ticker}_8-K_{fd.isoformat()}.txt"
        if path.exists() and not FORCE:
            continue
        try:
            text = document_text(f)
        except Exception as exc:
            print(f"  {ticker} 8-K {fd}: text failed ({exc})")
            continue
        items = split_items(text)
        if not items:
            continue
        body = "\n\n".join(f"## Item {k}\n{v}" for k, v in items.items())
        # The substance of Items 2.02 / 7.01 / 8.01 lives in the press-release exhibits (EX-99.x)
        try:
            for a in [a for a in f.attachments if str(a.document_type).upper().startswith("EX-99")]:
                ex_text = document_text(a)
                if ex_text and ex_text.count("�") > len(ex_text) * 0.01:
                    # binary content (e.g. a PDF exhibit) — never save it as text; leave a visible note instead
                    body += f"\n\n## Exhibit {a.document_type} ({a.document})\n[binary exhibit — text not extractable; read it on EDGAR if needed]"
                    continue
                if ex_text and len(ex_text) > 200:
                    flat = " ".join(ex_text.split())
                    cut = f" [exhibit truncated at {EXHIBIT_CAP:,} of {len(flat):,} chars]" if len(flat) > EXHIBIT_CAP else ""
                    body += f"\n\n## Exhibit {a.document_type} ({a.document})\n" + flat[:EXHIBIT_CAP] + cut
        except Exception as exc:
            print(f"  {ticker} 8-K {fd}: exhibit failed ({exc})")
        path.write_text(f"# {company} ({ticker}) 8-K filed {fd.isoformat()}\n# source label: {label(company, '8-K', fd)}\n"
                        f"# {f.homepage_url if hasattr(f, 'homepage_url') else ''}\n\n{body}", encoding="utf-8")
        saved.append(path.name)
    k = c.get_filings(form="10-K").latest(1)
    if k is not None:
        kd = k.filing_date if isinstance(k.filing_date, date) else date.fromisoformat(str(k.filing_date))
        path = OUT / f"{ticker}_10-K_{kd.isoformat()}_customers.txt"
        sc_path = OUT / f"{ticker}_10-K_{kd.isoformat()}_supplychain.txt"
        k_text = None
        if FORCE or not path.exists() or (names and not sc_path.exists()):
            try:
                k_text = document_text(k)
            except Exception as exc:
                print(f"  {ticker} 10-K: text failed ({exc})")
        # Supplier / manufacturing / named-counterparty paragraphs of the FULL 10-K, under the same label
        if k_text and names and (FORCE or not sc_path.exists()):
            sc = supply_chain_paragraphs(k_text, company, names, skip=set(customer_paragraphs(k_text)))
            if sc:
                sc_path.write_text(f"# {company} ({ticker}) 10-K filed {kd.isoformat()} — supplier / manufacturing / named-counterparty paragraphs\n"
                                   f"# source label: {label(company, '10-K', kd)}\n\n" + "\n\n".join(sc), encoding="utf-8")
                saved.append(sc_path.name)
        if not path.exists() or FORCE:
            paras = customer_paragraphs(k_text) if k_text else []
            xb = xbrl_sections(k, "10-K")
            if paras or xb:
                path.write_text(f"# {company} ({ticker}) 10-K filed {kd.isoformat()} — customer concentration paragraphs + XBRL facts\n"
                                f"# source label: {label(company, '10-K', kd)}\n\n"
                                + "\n\n".join(paras) + ("\n\n" + xb if xb else ""), encoding="utf-8")
                saved.append(path.name)
        elif "## XBRL" not in path.read_text(encoding="utf-8"):
            xb = xbrl_sections(k, "10-K")                       # older file: add the XBRL sections once
            if xb:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write("\n\n" + xb)
                saved.append(path.name + " (+XBRL)")
    q = c.get_filings(form="10-Q").latest(1)
    if q is not None:
        qd = q.filing_date if isinstance(q.filing_date, date) else date.fromisoformat(str(q.filing_date))
        path = OUT / f"{ticker}_10-Q_{qd.isoformat()}_segments.txt"
        sc_path = OUT / f"{ticker}_10-Q_{qd.isoformat()}_supplychain.txt"
        if names and (FORCE or not sc_path.exists()):
            try:
                q_text = document_text(q)
            except Exception as exc:
                q_text = None
                print(f"  {ticker} 10-Q: text failed ({exc})")
            sc = supply_chain_paragraphs(q_text, company, names) if q_text else []
            if sc:
                sc_path.write_text(f"# {company} ({ticker}) 10-Q filed {qd.isoformat()} — supplier / manufacturing / named-counterparty paragraphs\n"
                                   f"# source label: {label(company, '10-Q', qd)}\n\n" + "\n\n".join(sc), encoding="utf-8")
                saved.append(sc_path.name)
        if not path.exists() or FORCE:
            xb = xbrl_sections(q, "10-Q")
            if xb:
                path.write_text(f"# {company} ({ticker}) 10-Q filed {qd.isoformat()} — XBRL segment revenue and customer concentration\n"
                                f"# source label: {label(company, '10-Q', qd)}\n\n{xb}", encoding="utf-8")
                saved.append(path.name)
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", default="pull", choices=["pull", "queue", "done"])
    ap.add_argument("--tickers", default="")
    ap.add_argument("--since", default=(date.today() - timedelta(days=120)).isoformat())
    ap.add_argument("--force", action="store_true", help="rewrite files that already exist")
    ap.add_argument("--with-dropped", action="store_true",
                    help="done: also mark the noise-filtered files as read (only after a triage pass read them)")
    args = ap.parse_args()
    global FORCE
    FORCE = args.force
    if args.command == "queue":
        return build_queue()
    if args.command == "done":
        return mark_done(with_dropped=args.with_dropped)
    load_dotenv(ROOT / ".env")
    from edgar import set_identity
    set_identity(os.getenv("EDGAR_USER_AGENT") or "earnings-ai research gijunpark42@gmail.com")
    since = date.fromisoformat(args.since)
    universe = mapped_us_tickers()
    # every node name (US or not) — a US filer's suppliers are often TSMC, SK Hynix, ASE ...
    graph = json.loads((ROOT / "graph" / "merged_graph.json").read_text(encoding="utf-8"))
    names = {n["id"] for n in graph["nodes"]}
    if args.tickers:
        keep = {t.strip().upper() for t in args.tickers.split(",")}
        universe = {t: c for t, c in universe.items() if t in keep}
    total = 0
    for t, company in sorted(universe.items()):
        try:
            saved = pull(t, company, since, names)
        except Exception as exc:
            print(f"{t}: failed ({exc})")
            continue
        total += len(saved)
        if saved:
            print(f"{t}: {', '.join(saved)}")
    print(f"done: {total} new files in {OUT}")


if __name__ == "__main__":
    main()
