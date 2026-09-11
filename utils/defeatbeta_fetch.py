"""
utils/defeatbeta_fetch.py -- pull ONE US company's latest earnings-call transcript from
defeatbeta (a free Hugging Face mirror of Yahoo Finance transcripts) and save it in the
exact file format av.py writes, so verify_graph.py / evidence.py treat it like an
Alpha Vantage file.

Why this exists: Alpha Vantage allows 25 requests per DAY. When we add many new US
companies at once, that quota is gone after the first batch. defeatbeta has no quota
(it is a DuckDB read of a public dataset), only a ~1-2 day lag after the call.

Usage (from the repo root):

    python -X utf8 utils/defeatbeta_fetch.py "AAON" AAON
    python -X utf8 utils/defeatbeta_fetch.py "Carrier Global" CARR --fy 2026 --q 2

Prints the source label and the file path on the last two lines:

    LABEL: AAON Q2 FY2026 (08-10-2026)
    FILE: transcripts/av/aaon_q2_2026.txt

This script does NOT touch av/pending.json or any shared state, so several copies can
run in parallel (one per agent) without stepping on each other.
"""

import argparse
import contextlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "transcripts" / "av"


def slug(name):
    """'Applied Materials' -> 'appliedmaterials' (same rule as av.py / dart.py)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="canonical node name, e.g. 'Carrier Global' (goes into the label)")
    parser.add_argument("symbol", help="US ticker, e.g. CARR")
    parser.add_argument("--fy", type=int, help="fiscal year of the call to fetch (default: latest)")
    parser.add_argument("--q", type=int, help="fiscal quarter 1-4 (default: latest)")
    parser.add_argument("--date", help="override the call date in the label, MM-DD-YYYY -- use it when the graph "
                                       "already carries this call under a slightly different date, so the label "
                                       "stays identical and the history does not split in two")
    args = parser.parse_args()

    # defeatbeta prints an ASCII banner on import -- swallow it so our output stays clean.
    with contextlib.redirect_stdout(io.StringIO()):
        from defeatbeta_api.data.ticker import Ticker

    tr = Ticker(args.symbol.upper()).earning_call_transcripts()
    lst = tr.get_transcripts_list()           # columns: symbol, fiscal_year, fiscal_quarter, report_date (OLDEST first)
    if lst is None or len(lst) == 0:
        sys.exit(f"no transcripts on defeatbeta for {args.symbol}")

    if args.fy and args.q:
        row = lst[(lst.fiscal_year == args.fy) & (lst.fiscal_quarter == args.q)]
        if len(row) == 0:
            sys.exit(f"{args.symbol} FY{args.fy} Q{args.q} is not on defeatbeta; available:\n{lst.tail(6).to_string()}")
        row = row.iloc[0]
    else:
        row = lst.iloc[-1]                    # newest call

    fy, q = int(row.fiscal_year), int(row.fiscal_quarter)
    call_date = str(row.report_date)[:10]     # 'YYYY-MM-DD'
    yyyy, mm, dd = call_date.split("-")
    if args.date:                             # keep an existing label's date (see --date help)
        mm, dd, yyyy = args.date.split("-")
    label = f"{args.name} Q{q} FY{fy} ({mm}-{dd}-{yyyy})"

    df = tr.get_transcript(fy, q)             # columns: paragraph_number, speaker, content
    turns = [(str(r.speaker).strip(), str(r.content).strip()) for r in df.itertuples()]
    if not turns:
        sys.exit(f"{args.symbol} FY{fy} Q{q}: transcript is empty on defeatbeta")

    path = OUT_DIR / f"{slug(args.name)}_q{q}_{fy}.txt"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"SOURCE: defeatbeta (Hugging Face mirror of Yahoo Finance transcripts) -- {args.symbol.upper()} {fy}Q{q}",
        f"CALL DATE: {mm}-{dd}-{yyyy}",
        f"QUARTER: Q{q} FY{fy}",
        f"# source label: {label}",
        f"# speaker turns: {len(turns)}   characters: {sum(len(c) for _, c in turns):,}",
        "", "---", "",
    ]
    for who, content in turns:
        lines.append(f"{who}: {content}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

    print(f"LABEL: {label}")
    print(f"FILE: {path.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
