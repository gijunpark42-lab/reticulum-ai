"""
av.py -- US-listed companies: Alpha Vantage earnings-call transcripts -> transcripts/av/*.txt

Replaces the hand-pasted Motley Fool step for US names. Same shape as dart.py so the
enrichment loop is identical:

    python av.py sync                    # calendar -> which of OUR companies reported since the
                                         #   last sync -> pull each transcript that is now posted
    python av.py pending                 # files saved by sync that are not enriched yet
    python av.py done                    # clear the queue after enriching
    python av.py fetch NVDA 2027Q2       # one transcript by hand (quarter = Alpha Vantage's
                                         #   fiscal "YYYYQN"; the call date is asked for / --date)
    python av.py calendar                # show upcoming calls for our companies (no quota used)

What Alpha Vantage gives (verified on IBM 2024Q1): the WHOLE call as a list of speaker turns
  { "speaker": "Arvind Krishna", "title": "CEO", "content": "...", "sentiment": "0.3" }
prepared remarks and the full analyst Q&A, ~50k characters. Nothing is summarised. We join
the turns back into a plain "Speaker (Title): text" transcript and drop the sentiment number.

Limits (free key): 25 requests per DAY. `sync` spends one request per transcript it tries,
so a busy earnings week may take two or three days to backfill -- the queue survives across
runs and `sync` simply stops when the quota message comes back. The calendar endpoint is a
CSV download that does not count against the quota in practice, but we still call it once.

Latency: transcripts appear on Alpha Vantage usually within a day of the call. A company
that reported today but has no transcript yet is left in the "waiting" list and retried
on the next sync -- so run `sync` again tomorrow morning.

Needs ALPHAVANTAGE_API_KEY in .env  (free key: https://www.alphavantage.co/support/#api-key)
"""

import argparse
import csv
import itertools
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
METADATA = ROOT / "company_metadata.json"
OUT_DIR = ROOT / "transcripts" / "av"
STATE = ROOT / "av" / "sync_state.json"     # last sync date + (symbol, quarter) already saved + waiting list
PENDING = ROOT / "av" / "pending.json"      # files saved by sync but not yet enriched

API = "https://www.alphavantage.co/query"
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

US_EXCHANGES = {"NASDAQ", "NYSE"}
# Nodes whose earnings call carries nothing this graph can use. Shell is a real node
# (thermal -> Immersion, synthetic immersion coolant) but its group call is oil and gas
# only, so enriching it would add noise rather than supply-chain data. Checked on the
# Q2 FY2026 call, 2026-08-31.
SKIP_COMPANIES = {"Shell"}
# How far back a first-ever sync looks. Older calls are already in transcripts/ by hand.
DEFAULT_LOOKBACK_DAYS = 21
# A company's NEXT call covers a quarter ending this many days past our newest label
# => a whole quarter slipped by unenriched. One quarter apart is ~60-75 days; two is ~145+.
GAP_DAYS = 120
# Fallback for companies the earnings calendar does not list at all.
STALE_DAYS = 100


# ---------------------------------------------------------------- universe

def universe():
    """{canonical name: ticker} for every US-listed company in company_metadata.json.

    Names whose ticker carries a suffix (ASML is 'ASML', but '2330.TW' is Taiwan) or whose
    exchange is not NASDAQ/NYSE are skipped -- those have no US call transcript.
    """
    meta = json.loads(METADATA.read_text(encoding="utf-8"))
    out = {}
    for name, info in meta.items():
        ticker = (info.get("ticker") or "").strip()
        if info.get("exchange") in US_EXCHANGES and re.fullmatch(r"[A-Z.]{1,6}", ticker):
            out[name] = ticker
    return out


def slug(name):
    """'Applied Materials' -> 'appliedmaterials' (same rule as dart.py)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ---------------------------------------------------------------- Alpha Vantage calls

def _get(**params):
    if not API_KEY:
        sys.exit("ALPHAVANTAGE_API_KEY missing in .env -- free key: https://www.alphavantage.co/support/#api-key")
    r = requests.get(API, params={**params, "apikey": API_KEY}, timeout=60)
    r.raise_for_status()
    return r


def calendar(horizon="3month"):
    """Upcoming + very recent report dates for OUR companies, from EARNINGS_CALENDAR (CSV).

    Returns [{symbol, name, report_date (date), fiscal_end (date)}] sorted by report_date.
    """
    uni = universe()
    by_ticker = {t: n for n, t in uni.items()}
    r = _get(function="EARNINGS_CALENDAR", horizon=horizon)
    rows = []
    for row in csv.DictReader(io.StringIO(r.text)):
        name = by_ticker.get(row.get("symbol"))
        if not name or not row.get("reportDate"):
            continue
        rows.append({
            "symbol": row["symbol"], "name": name,
            "report_date": datetime.strptime(row["reportDate"], "%Y-%m-%d").date(),
            "fiscal_end": datetime.strptime(row["fiscalDateEnding"], "%Y-%m-%d").date() if row.get("fiscalDateEnding") else None,
        })
    return sorted(rows, key=lambda x: x["report_date"])


class QuotaExceeded(Exception):
    pass


def reported_quarters(symbol):
    """Past calls for one symbol from EARNINGS: [(fiscal_end, reported_date)], newest first.

    EARNINGS_CALENDAR only ever lists FUTURE report dates, so it cannot answer "who
    reported since the last sync". EARNINGS is the other half: it returns every PAST
    quarter with the date the company actually reported, which is the date the canonical
    source label needs. One request covers a company's whole history, however many
    quarters we are behind.
    """
    data = _get(function="EARNINGS", symbol=symbol).json()
    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note")
        if "rate limit" in msg.lower() or "requests per day" in msg.lower() or "premium" in msg.lower():
            raise QuotaExceeded(msg)
        raise RuntimeError(msg)
    out = []
    for row in data.get("quarterlyEarnings", []):
        try:
            out.append((datetime.strptime(row["fiscalDateEnding"], "%Y-%m-%d").date(),
                        datetime.strptime(row["reportedDate"], "%Y-%m-%d").date()))
        except (KeyError, ValueError):
            continue
    return sorted(out, key=lambda x: x[1], reverse=True)


def transcript(symbol, quarter):
    """One EARNINGS_CALL_TRANSCRIPT call. Returns the list of speaker turns, or [] if not posted yet.

    Alpha Vantage answers a missing transcript with an empty "transcript" list, and a
    spent daily quota with an "Information" message -- we turn the latter into an exception
    so `sync` can stop cleanly instead of burning through the queue with empty results.
    """
    data = _get(function="EARNINGS_CALL_TRANSCRIPT", symbol=symbol, quarter=quarter).json()
    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note")
        if "rate limit" in msg.lower() or "requests per day" in msg.lower() or "premium" in msg.lower():
            raise QuotaExceeded(msg)
        raise RuntimeError(msg)
    if "Error Message" in data:
        raise RuntimeError(data["Error Message"])
    return data.get("transcript") or []


# ---------------------------------------------------------------- quarter guessing

_LABEL = re.compile(r"^(?P<name>.+?) Q(?P<q>[1-4]) FY(?P<fy>20\d\d) \((?P<d>\d\d-\d\d-\d{4})\)$")


def graph_nodes():
    """Every company that actually exists as a node in the merged graph.

    The universe in company_metadata.json is wider (logo/screener-only names), and a
    company that is not a node has no player to attach quarterly_data to.
    """
    path = ROOT / "graph" / "merged_graph.json"
    if not path.exists():
        return set()
    return {n["id"] for n in json.loads(path.read_text(encoding="utf-8"))["nodes"]}


def latest_label_in_graph(name):
    """The most recent earnings label this company already has in the graph, as (fy, q, date).

    graph/merged_graph.json is the record of what has been enriched so far. Its labels
    already encode each company's fiscal calendar (NVIDIA Q1 FY2027 = the call on 05-20-2026),
    so the NEXT call is simply Q+1 -- no fiscal-year table to maintain.
    """
    path = ROOT / "graph" / "merged_graph.json"
    if not path.exists():
        return None
    best = None
    for node in json.loads(path.read_text(encoding="utf-8"))["nodes"]:
        if node["id"] != name:
            continue
        for q in node.get("quarterly_data", []):
            m = _LABEL.match(q.get("quarter", ""))
            if m and m.group("name") == name:
                d = datetime.strptime(m.group("d"), "%m-%d-%Y").date()
                if best is None or d > best[2]:
                    best = (int(m.group("fy")), int(m.group("q")), d)
    return best


def fiscal_quarter_candidates(name, fiscal_end):
    """Alpha Vantage keys transcripts by the company's FISCAL 'YYYYQN'. Which one is today's call?

    1. If the graph already has a label for this company, the next quarter after it
       (Q4 FY2026 -> Q1 FY2027). One request, and the label stays consistent with history.
    2. Otherwise -- only when the graph has NO label for this company -- the calendar-year
       guess from the quarter-end date (2026-06-30 -> 2026Q2), then the same quarter number
       one fiscal year ahead. These guesses are last resorts and the resulting label should
       be checked by hand against the company's fiscal calendar before enriching.

    A company WITH history gets exactly one candidate: the successor of its newest label.
    Falling through to a calendar guess would fetch an older call under a new label.
    """
    cands = []
    last = latest_label_in_graph(name)
    if last:
        fy, q, _ = last
        # ONLY the fiscal successor. A calendar-year guess here would silently return an
        # older call for any company whose newest transcript is not posted yet (see docstring).
        return [f"{fy + 1}Q1" if q == 4 else f"{fy}Q{q + 1}"]
    if fiscal_end is not None:
        cal_q = (fiscal_end.month - 1) // 3 + 1
        for c in (f"{fiscal_end.year}Q{cal_q}", f"{fiscal_end.year + 1}Q{cal_q}"):
            if c not in cands:
                cands.append(c)
    return cands


# ---------------------------------------------------------------- writing files

def source_label(name, quarter, call_date):
    """'NVIDIA' + '2027Q2' + 2026-08-26 -> 'NVIDIA Q2 FY2027 (08-26-2026)'  (CLAUDE.md canonical)."""
    fy, q = quarter.split("Q")
    return f"{name} Q{q} FY{fy} ({call_date.strftime('%m-%d-%Y')})"


def write_file(name, symbol, quarter, call_date, turns, label_quarter=None):
    """Save one transcript as plain text with the header the rest of the pipeline expects.

    `quarter` is the key Alpha Vantage stores the transcript under; `label_quarter` is
    what WE call it. They differ whenever Alpha Vantage files a company by calendar
    quarter while the graph tracks it by fiscal quarter (Flex, Arm, ...), so the label
    and the filename always follow `label_quarter`.
    """
    fy, q = (label_quarter or quarter).split("Q")
    label = source_label(name, label_quarter or quarter, call_date)
    path = OUT_DIR / f"{slug(name)}_q{q}_{fy}.txt"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"SOURCE: Alpha Vantage EARNINGS_CALL_TRANSCRIPT ({symbol} {quarter}) -- full call, prepared remarks + Q&A",
        f"CALL DATE: {call_date.strftime('%m-%d-%Y')}",
        f"QUARTER: Q{q} FY{fy}",
        f"# source label: {label}",
        f"# speaker turns: {len(turns)}   characters: {sum(len(t.get('content', '')) for t in turns):,}",
        "", "---", "",
    ]
    for t in turns:
        who = t.get("speaker", "").strip()
        title = (t.get("title") or "").strip()
        head = f"{who} ({title})" if title and title != who else who
        lines.append(f"{head}: {t.get('content', '').strip()}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path, label


def already_have(name, quarter):
    """Is this call already in transcripts/ (from the Motley Fool days)?  Uses the same
    label->file join as verify_graph so 'nvda_q2_2027.txt' counts for NVIDIA 2027Q2."""
    from agent.corpus import find_document_for_label
    return find_document_for_label(source_label(name, quarter, date.today())) is not None


# ---------------------------------------------------------------- sync

def _load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"last_sync": None, "saved": [], "waiting": []}


def _save_state(state):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")


def _queue(saved):
    pending = json.loads(PENDING.read_text(encoding="utf-8")) if PENDING.exists() else []
    known = {(x["file"], x["label"]) for x in pending}
    for name, path, label in saved:
        row = {"kind": "transcript", "company": name,
               "file": str(path.relative_to(ROOT)).replace("\\", "/"), "label": label}
        if (row["file"], row["label"]) not in known:
            pending.append(row)
    PENDING.write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")


def gap_candidates():
    """Which companies MIGHT have reported a quarter we never enriched — decided for free.

    Costs one EARNINGS_CALENDAR request for the whole universe, no per-company request.

    The calendar lists only FUTURE calls, but each row also names the quarter that call
    will cover (`fiscal_end`). If that upcoming quarter-end sits more than GAP_DAYS past
    the newest label we already have for the company, a whole quarter went by unenriched.
    Worked example: TE Connectivity's next call covers the quarter ending 2026-09-30 while
    our newest label is the call of 2026-04-22 — 161 days, so the quarter ending
    2026-06-30 (reported 2026-07-22) was missed. Dell's next call covers 2026-07-31 and
    our newest label is 2026-05-28 — 64 days, one quarter apart, nothing missed.

    Returns {symbol: name}. Companies the calendar does not list fall back to a plain
    staleness check, and companies with no label at all are always included.
    """
    uni = universe()
    nodes = graph_nodes()
    upcoming = {row["symbol"]: row for row in calendar(horizon="12month")}
    out = []
    for name, symbol in uni.items():
        if name not in nodes:
            continue          # in company_metadata.json but not a node — nothing to enrich
        if name in SKIP_COMPANIES:
            continue          # a node, but its call has no usable content
        last = latest_label_in_graph(name)
        if last is None:                       # never enriched — always worth a look
            out.append((date.max, symbol, name))
            continue
        row = upcoming.get(symbol)
        if row is not None and row.get("fiscal_end"):
            if (row["fiscal_end"] - last[2]).days > GAP_DAYS:
                out.append((last[2], symbol, name))
        elif (date.today() - last[2]).days >= STALE_DAYS:
            out.append((last[2], symbol, name))   # not on the calendar; go by age alone
    # Oldest gap first, so the biggest holes close first when the daily quota is tight;
    # never-enriched names (date.max) come last.
    return [(s, n) for _, s, n in sorted(out)]


def missed_calls(since, today):
    """Turn the free gap list into real (symbol, name, report_date, fiscal_end) rows.

    One EARNINGS request per candidate — that request returns the company's whole
    reported history, so it covers however many quarters we are behind. We target the
    OLDEST call newer than what the graph already has, so the label we write is exactly
    "last label + 1 quarter" and history stays in order; a company two quarters behind is
    caught again on the next sync.

    This is a GENERATOR on purpose. Each company costs one EARNINGS request here and one
    transcript request in sync(); yielding lets sync() finish a company end-to-end before
    the next lookup, so a spent daily quota leaves whole saved transcripts behind rather
    than a pile of lookups and nothing to enrich.
    """
    for symbol, name in gap_candidates():
        last = latest_label_in_graph(name)
        floor = (max(last[2], since) if since else last[2]) if last else since
        try:
            history = reported_quarters(symbol)
        except QuotaExceeded:
            print("QUOTA    daily limit reached while looking up report dates — rerun tomorrow")
            return
        except Exception as exc:
            print(f"FAIL     {name} {symbol}: {exc}")
            continue
        time.sleep(1)
        newer = [(fe, rd) for fe, rd in history if rd <= today and (floor is None or rd > floor)]
        if not newer:
            continue
        # Oldest missed call when we have history (keeps labels in order); newest when we
        # have none at all (do not backfill years of an unenriched company).
        fiscal_end, report_date = (newer[-1] if last is not None else newer[0])
        print(f"missed   {name:30s} reported {report_date} for quarter-end {fiscal_end}")
        yield {"symbol": symbol, "name": name,
               "report_date": report_date, "fiscal_end": fiscal_end}


def sync(since=None):
    """Find our companies that reported since the last sync and pull every transcript that
    is posted. Returns [(name, path, label)]. Companies whose transcript is not up yet go to
    state['waiting'] and are retried next time."""
    state = _load_state()
    saved_keys = {tuple(x) for x in state["saved"]}
    # `since` is now only an OPTIONAL extra floor: by default each company's own newest
    # label is the floor, which is what "not yet enriched" actually means.
    today = date.today()

    # 1. Everything still waiting from earlier runs (report date already known, so these
    #    cost only a transcript request), then stream newly discovered gaps.
    retry = [{**w, "report_date": date.fromisoformat(w["report_date"]),
              "fiscal_end": date.fromisoformat(w["fiscal_end"]) if w.get("fiscal_end") else None}
             for w in state["waiting"]]

    seen = set()
    saved, waiting = [], []
    quota_hit = False
    for row in itertools.chain(retry, missed_calls(since, today)):
        symbol, name = row["symbol"], row["name"]
        if symbol in seen:
            continue
        seen.add(symbol)
        if quota_hit:
            waiting.append(row)
            continue
        try:
            got = None
            # What history says this call must be called, regardless of Alpha Vantage's key.
            last = latest_label_in_graph(name)
            label_q = None
            if last:
                lfy, lq, _ = last
                label_q = f"{lfy + 1}Q1" if lq == 4 else f"{lfy}Q{lq + 1}"
            for quarter in fiscal_quarter_candidates(name, row["fiscal_end"]):
                if (symbol, quarter) in saved_keys or already_have(name, label_q or quarter):
                    print(f"skip     {name:32s} {quarter}  (already in transcripts/)")
                    saved_keys.add((symbol, quarter))
                    got = "have"
                    break
                turns = transcript(symbol, quarter)
                time.sleep(1)
                if turns:
                    path, label = write_file(name, symbol, quarter, row["report_date"], turns,
                                             label_quarter=label_q)
                    saved.append((name, path, label))
                    saved_keys.add((symbol, quarter))
                    print(f"saved    {label:45s} -> {path.relative_to(ROOT)}  ({len(turns)} turns)")
                    got = "saved"
                    break
            if got is None:
                print(f"waiting  {name:32s} reported {row['report_date']}, transcript not posted yet")
                waiting.append(row)
        except QuotaExceeded as exc:
            print(f"\nQUOTA    daily limit reached -- rerun tomorrow to continue\n         ({str(exc)[:90]})")
            quota_hit = True
            waiting.append(row)
        except Exception as exc:
            print(f"FAIL     {name} {symbol}: {exc}")
            waiting.append(row)

    # drop anything that has waited more than 30 days -- the call is not coming
    state["waiting"] = [{"symbol": w["symbol"], "name": w["name"],
                         "report_date": w["report_date"].isoformat(),
                         "fiscal_end": w["fiscal_end"].isoformat() if w.get("fiscal_end") else None}
                        for w in waiting if (today - w["report_date"]).days <= 30]
    state["saved"] = sorted(list(k) for k in saved_keys)
    if not quota_hit:
        state["last_sync"] = today.strftime("%Y%m%d")
    _save_state(state)
    _queue(saved)
    return saved


# ---------------------------------------------------------------- CLI

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync", help="pull every newly posted transcript for our US companies")
    s.add_argument("--since", help="YYYY-MM-DD, override the last-sync date")
    f = sub.add_parser("fetch", help="pull one transcript by hand")
    f.add_argument("symbol")
    f.add_argument("quarter", help="Alpha Vantage fiscal quarter, e.g. 2027Q2")
    f.add_argument("--date", help="call date YYYY-MM-DD (goes into the source label); default today")
    f.add_argument("--label-quarter", help="fiscal quarter for the LABEL, e.g. 2027Q1, when Alpha "
                                           "Vantage files this company by calendar quarter")
    sub.add_parser("calendar", help="show upcoming calls for our companies")
    sub.add_parser("pending", help="list files saved by sync that are not enriched yet")
    sub.add_parser("done", help="mark everything in the pending queue as enriched")
    args = parser.parse_args()

    if args.cmd == "sync":
        rows = sync(datetime.strptime(args.since, "%Y-%m-%d").date() if args.since else None)
        print(f"\n{len(rows)} transcript(s) saved; `python av.py pending` shows the enrichment queue")
    elif args.cmd == "fetch":
        by_ticker = {t: n for n, t in universe().items()}
        name = by_ticker.get(args.symbol.upper())
        if not name:
            sys.exit(f"{args.symbol} is not a US-listed ticker in company_metadata.json")
        call_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
        turns = transcript(args.symbol.upper(), args.quarter)
        if not turns:
            sys.exit(f"no transcript on Alpha Vantage for {args.symbol} {args.quarter} (yet)")
        path, label = write_file(name, args.symbol.upper(), args.quarter, call_date, turns,
                                 label_quarter=args.label_quarter)
        _queue([(name, path, label)])
        print(f"saved {label} -> {path.relative_to(ROOT)}  ({len(turns)} turns)")
    elif args.cmd == "calendar":
        today = date.today()
        for row in calendar():
            flag = "past " if row["report_date"] < today else ("TODAY" if row["report_date"] == today else "     ")
            print(f"{flag} {row['report_date']}  {row['symbol']:6s} {row['name']:32s} quarter-end {row['fiscal_end']}")
    elif args.cmd == "pending":
        rows = json.loads(PENDING.read_text(encoding="utf-8")) if PENDING.exists() else []
        for r in rows:
            print(f"{r['company']:32s} {r['label']:45s} {r['file']}")
        print(f"{len(rows)} pending")
    elif args.cmd == "done":
        PENDING.write_text("[]", encoding="utf-8")
        print("queue cleared")
