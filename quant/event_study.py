# event_study.py — binary FULL-CAPACITY event study.
#
# SIGNAL (binary, owner-classified)
#   flag = 1 : the company itself said its capacity is full / sold out /
#              demand exceeds its supply, in chain signals from its own
#              earnings call. Every flag was approved company-by-company by
#              the project owner (quant/signal_full_capacity.csv, with the
#              evidence quote and the owner's ruling).
#   flag = 0 : every other earnings call in the universe.
#
# UNIVERSE
#   quant/calls.csv — all 71 US-listed earnings calls in the graph.
#
# METHODOLOGY (owner's decisions)
#   t0       = the earnings-call date
#   ENTRY    = close of t+1 (the announcement jump is not buyable; it is
#              reported separately as context)
#   WINDOWS  = entry -> +5, +10, +20 trading days. If a recent call lacks
#              +20d data, its +5d/+10d are still computed — each window
#              keeps every call that has complete data for THAT window.
#   ABNORMAL = stock return minus benchmark return (SOXX, SPY, QQQ)
#   STATS    = N, mean, median, hit rate, two-sided p-value
#              (one-sample t-test of the mean against zero)
#
# OUTPUTS
#   quant/results.json          group statistics (flag=1 vs flag=0)
#   quant/results_events.csv    one row per call with all window returns
#   quant/window_companies.csv  which companies are inside each window's N
#
# HOW TO RUN (from the project root)
#   python -X utf8 quant/event_study.py

import json
import os
import csv
from collections import defaultdict

import pandas as pd
from scipy import stats as sps

CALLS_FILE = "quant/calls.csv"
SIGNAL_FILE = "quant/signal_full_capacity.csv"
PRICES_CACHE = "quant/prices.csv"
RESULTS_FILE = "quant/results.json"
DETAIL_FILE = "quant/results_events.csv"
WINDOWS_FILE = "quant/window_companies.csv"

BENCHMARKS = ["SOXX", "SPY", "QQQ"]
PRICE_START = "2026-01-01"
WINDOWS = [5, 10, 20]


def load_calls():
    with open(CALLS_FILE, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_flags():
    """Owner-approved flag=1 companies -> set of names."""
    with open(SIGNAL_FILE, encoding="utf-8-sig") as f:
        return {r["company"] for r in csv.DictReader(f) if r["flag"] == "1"}


def get_prices(tickers):
    """Daily adjusted closes, cached; missing tickers are topped up."""
    all_tickers = sorted(set(tickers) | set(BENCHMARKS))
    if os.path.exists(PRICES_CACHE):
        prices = pd.read_csv(PRICES_CACHE, index_col=0, parse_dates=True)
        missing = [t for t in all_tickers if t not in prices.columns]
        if missing:
            import yfinance as yf
            print(f"Downloading {len(missing)} new tickers: {', '.join(missing)}")
            data = yf.download(missing, start=PRICE_START, auto_adjust=True, progress=False)
            closes = data["Close"]
            if isinstance(closes, pd.Series):
                closes = closes.to_frame(name=missing[0])
            prices = prices.join(closes, how="outer")
            prices.to_csv(PRICES_CACHE)
        print(f"Loaded prices: {prices.shape[1]} tickers x {prices.shape[0]} days")
        return prices
    import yfinance as yf
    print(f"Downloading {len(all_tickers)} tickers from Yahoo Finance...")
    data = yf.download(all_tickers, start=PRICE_START, auto_adjust=True, progress=False)
    prices = data["Close"]
    prices.to_csv(PRICES_CACHE)
    return prices


def window_return(series, i_start, n_days):
    """Return over n_days trading days from index position i_start (None = incomplete)."""
    i_end = i_start + n_days
    if i_end >= len(series):
        return None
    a, b = series.iloc[i_start], series.iloc[i_end]
    if pd.isna(a) or pd.isna(b) or a == 0:
        return None
    return b / a - 1.0


def group_stats(values):
    """N, mean, median, hit rate, two-sided p-value of mean vs 0."""
    n = len(values)
    if n == 0:
        return None
    mean = sum(values) / n
    med = sorted(values)[n // 2]
    hit = sum(1 for v in values if v > 0) / n
    if n > 1:
        t, p = sps.ttest_1samp(values, 0.0)
        p = float(p)
    else:
        p = None
    return {"n": n, "mean": round(mean, 5), "median": round(med, 5),
            "hit_rate": round(hit, 3),
            "p_value": round(p, 4) if p is not None else None}


def main():
    calls = load_calls()
    flagged = load_flags()
    prices = get_prices({c["ticker"] for c in calls})
    trading_days = prices.index

    # values[group][metric] = list of per-call abnormal returns
    values = {"full_capacity": defaultdict(list), "rest": defaultdict(list)}
    # window membership: (window, group) -> [company names included]
    members = defaultdict(list)
    excluded = defaultdict(int)
    rows = []

    for c in calls:
        tkr, co = c["ticker"], c["company"]
        group = "full_capacity" if co in flagged else "rest"
        if tkr not in prices.columns or prices[tkr].dropna().empty:
            excluded["no price data"] += 1
            continue
        s = prices[tkr]
        t0 = pd.Timestamp(c["date"])
        pos = trading_days.searchsorted(t0, side="right") - 1
        if pos < 0:
            excluded["call before price history"] += 1
            continue
        i_t0, i_entry = pos, pos + 1
        if i_entry >= len(trading_days):
            excluded["no entry day yet"] += 1
            continue

        row = {"company": co, "ticker": tkr, "date": c["date"],
               "flag": 1 if group == "full_capacity" else 0}

        jump = window_return(s, i_t0, 1)
        for bench in BENCHMARKS:
            bj = window_return(prices[bench], i_t0, 1)
            if jump is not None and bj is not None:
                row[f"jump_vs_{bench}"] = round(jump - bj, 5)
                values[group][f"jump_vs_{bench}"].append(jump - bj)

        for w in WINDOWS:
            r = window_return(s, i_entry, w)
            if r is None:
                excluded[f"+{w}d window not complete yet"] += 1
                continue   # this window only — shorter windows still counted
            members[(w, group)].append(co)
            for bench in BENCHMARKS:
                br = window_return(prices[bench], i_entry, w)
                if br is not None:
                    row[f"drift{w}_vs_{bench}"] = round(r - br, 5)
                    values[group][f"drift{w}_vs_{bench}"].append(r - br)
        rows.append(row)

    # ── Benchmarks 4-6: the UNIVERSE AVERAGE ──────────────────────────────────
    # For each metric, the mean abnormal return across ALL calls (flag + rest)
    # becomes a benchmark of its own: a group's excess = its value minus the
    # universe average for the same window/benchmark. This asks directly:
    # "did the signal group beat the average call in this universe?"
    all_vals = defaultdict(list)
    for g in values:
        for m, v in values[g].items():
            all_vals[m].extend(v)
    universe_avg = {m: sum(v) / len(v) for m, v in all_vals.items() if v}
    for g in list(values):
        for m in [m for m in values[g] if not m.endswith("_minus_univ")]:
            u = universe_avg.get(m)
            if u is not None:
                values[g][f"{m}_minus_univ"] = [v - u for v in values[g][m]]

    # ── results.json ──────────────────────────────────────────────────────────
    results = {
        "signal": "full_capacity (binary, owner-approved per company; see quant/signal_full_capacity.csv)",
        "universe": f"{len(calls)} US-listed earnings calls",
        "flagged_companies": sorted(flagged),
        "methodology": {
            "entry": "close of t+1 (first trading day after the call)",
            "jump": "close(t0) -> close(t+1), context only (not buyable)",
            "windows_trading_days": WINDOWS,
            "window_rule": "each window keeps every call with complete data for that window",
            "abnormal_return": "stock return minus benchmark return",
            "benchmarks": BENCHMARKS + [f"universe average vs {b} (benchmarks 4-6)" for b in BENCHMARKS],
            "test": "two-sided one-sample t-test p-value of the mean vs zero",
        },
        "universe_avg": {m: round(v, 5) for m, v in sorted(universe_avg.items())},
        "excluded": dict(excluded),
        "groups": {g: {m: group_stats(v) for m, v in sorted(vals.items())}
                   for g, vals in values.items()},
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # ── per-call detail ───────────────────────────────────────────────────────
    cols = ["company", "ticker", "date", "flag"] + \
           [f"jump_vs_{b}" for b in BENCHMARKS] + \
           [f"drift{w}_vs_{b}" for w in WINDOWS for b in BENCHMARKS]
    with open(DETAIL_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)

    # ── per-window company membership ─────────────────────────────────────────
    with open(WINDOWS_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["window_trading_days", "group", "n_companies", "companies"])
        for w in WINDOWS:
            for g in ("full_capacity", "rest"):
                comp = sorted(members.get((w, g), []))
                writer.writerow([w, g, len(comp), "; ".join(comp)])

    # ── console report ────────────────────────────────────────────────────────
    def pct(x): return f"{x*100:+.1f}%" if x is not None else "  —"

    print(f"\nWrote {RESULTS_FILE}, {DETAIL_FILE}, {WINDOWS_FILE}")
    print(f"Flagged (full_capacity): {len(flagged)} companies / universe {len(calls)} calls")
    print(f"Exclusions: {dict(excluded) or 'none'}\n")
    def print_block(title, suffix):
        print(f"=== {title} " + "=" * 38)
        print(f"{'group':15s}{'win':>5s}{'N':>4s}{'mean':>8s}{'median':>9s}{'hit':>6s}{'p-val':>8s}")
        for g in ("full_capacity", "rest"):
            for w in WINDOWS:
                st_ = results["groups"][g].get(f"drift{w}_vs_{suffix}")
                if st_:
                    print(f"{g:15s}{'+'+str(w)+'d':>5s}{st_['n']:>4d}{pct(st_['mean']):>8s}"
                          f"{pct(st_['median']):>9s}{str(round(st_['hit_rate']*100))+'%':>6s}"
                          f"{st_['p_value'] if st_['p_value'] is not None else '—':>8}")
        print()

    for bench in BENCHMARKS:
        print_block(f"Abnormal returns vs {bench} (benchmark 1-3)", bench)
    for bench in BENCHMARKS:
        print_block(f"Excess over UNIVERSE AVERAGE of abnormal-vs-{bench} (benchmark 4-6)",
                    f"{bench}_minus_univ")


if __name__ == "__main__":
    main()
