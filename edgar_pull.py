"""Pull company-primary SEC documents for the mapped US tickers into transcripts/edgar/.

Company documents only (the map's rule): 8-K current reports (guidance changes, material
agreements, earnings releases) and the customer-concentration paragraphs of the latest 10-K.
Nothing here touches chains/ or graph/; the saved text files are enrichment inputs, to be
processed like transcripts (source label e.g. "Lumentum 8-K (08-11-2026)").

    python edgar_pull.py                      # all mapped US tickers, 8-Ks from the last 120 days + latest 10-K
    python edgar_pull.py --tickers LITE,SMCI  # a few names
    python edgar_pull.py --since 2026-06-01   # older window

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
ITEM_RE = re.compile(r"(?i)item\s+(\d\.\d\d)")


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
            items[item] = items.get(item, "") + chunk[:6000] + "\n"
    return items


def customer_paragraphs(text, max_paras=12):
    """Paragraphs of a 10-K that talk about customer concentration or major customers."""
    paras = re.split(r"\n\s*\n", text)
    keep = []
    for p in paras:
        low = p.lower()
        if ("customer" in low and ("10%" in low or "ten percent" in low or "concentration" in low
                                   or "largest customer" in low or "accounted for" in low)):
            keep.append(" ".join(p.split())[:1500])
        if len(keep) >= max_paras:
            break
    return keep


def pull(ticker, company, since, max_8k=8):
    from edgar import Company
    OUT.mkdir(parents=True, exist_ok=True)
    saved = []
    c = Company(ticker)
    if c is None:
        return saved
    for f in c.get_filings(form="8-K").latest(max_8k):
        fd = f.filing_date if isinstance(f.filing_date, date) else date.fromisoformat(str(f.filing_date))
        if fd < since:
            continue
        path = OUT / f"{ticker}_8-K_{fd.isoformat()}.txt"
        if path.exists():
            continue
        try:
            text = f.text()
        except Exception as exc:
            print(f"  {ticker} 8-K {fd}: text failed ({exc})")
            continue
        items = split_items(text)
        if not items:
            continue
        body = "\n\n".join(f"## Item {k}\n{v}" for k, v in items.items())
        path.write_text(f"# {company} ({ticker}) 8-K filed {fd.isoformat()}\n# {f.homepage_url if hasattr(f, 'homepage_url') else ''}\n\n{body}", encoding="utf-8")
        saved.append(path.name)
    k = c.get_filings(form="10-K").latest(1)
    if k is not None:
        kd = k.filing_date if isinstance(k.filing_date, date) else date.fromisoformat(str(k.filing_date))
        path = OUT / f"{ticker}_10-K_{kd.isoformat()}_customers.txt"
        if not path.exists():
            try:
                paras = customer_paragraphs(k.text())
            except Exception as exc:
                paras = []
                print(f"  {ticker} 10-K: text failed ({exc})")
            if paras:
                path.write_text(f"# {company} ({ticker}) 10-K filed {kd.isoformat()} — customer concentration paragraphs\n\n"
                                + "\n\n".join(paras), encoding="utf-8")
                saved.append(path.name)
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="")
    ap.add_argument("--since", default=(date.today() - timedelta(days=120)).isoformat())
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    from edgar import set_identity
    set_identity(os.getenv("EDGAR_USER_AGENT") or "earnings-ai research gijunpark42@gmail.com")
    since = date.fromisoformat(args.since)
    universe = mapped_us_tickers()
    if args.tickers:
        keep = {t.strip().upper() for t in args.tickers.split(",")}
        universe = {t: c for t, c in universe.items() if t in keep}
    total = 0
    for t, company in sorted(universe.items()):
        try:
            saved = pull(t, company, since)
        except Exception as exc:
            print(f"{t}: failed ({exc})")
            continue
        total += len(saved)
        if saved:
            print(f"{t}: {', '.join(saved)}")
    print(f"done: {total} new files in {OUT}")


if __name__ == "__main__":
    main()
