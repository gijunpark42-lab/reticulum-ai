import streamlit as st
import base64
import glob
import json
import math
import os
import re
from datetime import datetime
from collections import defaultdict

# The supply-chain vocabulary (13 layers + 4 domains, colors, order, display names)
# lives in ONE place — taxonomy.py — imported here so app.py never hard-codes it.
from taxonomy import (
    LAYERS, DOMAINS, LAYER_ORDER, LAYER_COLORS, DOMAIN_COLORS,
    LAYER_NAMES, DOMAIN_NAMES, GROUP_COLORS, GROUP_NAMES,
)

st.set_page_config(page_title="AI Supply Chain", layout="wide", page_icon="🧬")

# ── Load merged graph ─────────────────────────────────────────────────────────
if not os.path.exists("graph/merged_graph.json"):
    st.error("merged_graph.json not found. Run graph_build.py first.")
    st.stop()

with open("graph/merged_graph.json", encoding="utf-8") as f:
    graph = json.load(f)

# ── Company logos (static/logos/, EMBEDDED as base64 data URIs) ───────────────
# manifest.json maps company name -> {file, bg}. bg says which chip background
# keeps the logo visible: "light" chip for dark logos, "dark" chip for white ones.
# The graph runs inside a Streamlit components.html iframe. On Streamlit Cloud a
# request for /app/static/... from that iframe 303-redirects to an auth page (and the
# iframe can be cross-origin), so <img src="/app/static/..."> fails to load on deploy
# even though the files are present. So we read each logo and inline it as a base64
# data URI: the bytes travel with the node data and render regardless of origin/auth.
LOGOS = {}
if os.path.exists("static/logos/manifest.json"):
    with open("static/logos/manifest.json", encoding="utf-8") as f:
        LOGOS = json.load(f)

# Read static/logos/<file> once and return a "data:<mime>;base64,..." URI (or None
# if the file is missing). Cached so the file read + encode happens once per process,
# not on every rerun. SVG/PNG cover all current logos; others fall back to a generic
# binary mime which browsers still accept in an <img> data URI.
@st.cache_data(show_spinner=False)
def logo_data_uri(filename):
    path = os.path.join("static", "logos", filename)
    if not os.path.exists(path):
        return None
    mime = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"
            }.get(os.path.splitext(filename)[1].lower(), "application/octet-stream")
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return "data:" + mime + ";base64," + b64

# ── Stock reports (company name -> report) ────────────────────────────────────
# The "Stock Report" button in the node-click panel shows the report from here.
# Two sources, both keyed by the node's exact company name:
#   1. reports.json        — a flat {company: "plain text report"} map (simple).
#   2. reports/<name>.json — one structured JSON per company (rich report). The
#      key is the file's "node_name" field, else the filename stem. These win.
REPORTS = {}
if os.path.exists("reports.json"):
    with open("reports.json", encoding="utf-8") as f:
        REPORTS = json.load(f)
    REPORTS.pop("_schema", None)
if os.path.isdir("reports"):
    for _rp in glob.glob(os.path.join("reports", "*.json")):
        # files starting with "_" are meta (e.g. _TEMPLATE.json), not company reports
        if os.path.basename(_rp).startswith("_"):
            continue
        try:
            with open(_rp, encoding="utf-8") as f:
                _rdata = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        _rkey = (_rdata.get("node_name") if isinstance(_rdata, dict) else None) \
            or os.path.splitext(os.path.basename(_rp))[0]
        REPORTS[_rkey] = _rdata

# ── Live market data (price / market cap / 1-year history) ────────────────────
# For any report that has a ticker, pull a live quote + 1y price history from Yahoo
# Finance (via yfinance) so the report can show a live quote card + price chart.
# Fetched SERVER-SIDE (the report renders in a sandboxed iframe that can't fetch
# cross-origin), cached 10 minutes, and fully best-effort: any failure (offline,
# missing yfinance, unknown ticker) just leaves that report on its static figures.
import concurrent.futures
import datetime as _dt

# A few tickers whose bare form Yahoo Finance does not resolve (multi-listed; the
# report stores the local ticker). Map them to the right Yahoo symbol explicitly.
_SYMBOL_OVERRIDE = {"BESI": "BESI.AS"}   # BE Semiconductor — Euronext Amsterdam

def _yahoo_symbol(ticker, exchange=None):
    t = (ticker or "").strip()
    if not t:
        return None
    if t in _SYMBOL_OVERRIDE:
        return _SYMBOL_OVERRIDE[t]
    if "." in t:            # already carries a Yahoo suffix (.HK / .TW / .KS / .AS)
        return t
    if t.isdigit():         # a bare numeric code is a Korea Exchange (KRX/KOSPI) listing
        return t + ".KS"
    return t                # plain US / ADR ticker works as-is

def _series(df):
    """A yfinance history DataFrame -> [[epoch_ms, close], ...] (drops gaps)."""
    if df is None or getattr(df, "empty", True) or "Close" not in df:
        return []
    out = []
    for ts, c in df["Close"].dropna().items():
        try:
            # ts is a pandas Timestamp; .timestamp() -> POSIX seconds. Store ms so the
            # browser can format the date/time on hover with new Date(ms).
            out.append([int(ts.timestamp() * 1000), round(float(c), 2)])
        except Exception:
            pass
    return out

def _fetch_quote(symbol):
    """One ticker -> {price, change_pct, market_cap, 52w, currency, series{}} or None.

    `series` holds one [ts_ms, close] list per selectable range (1D/1W/1M/YTD/1Y) so the
    report chart can switch ranges and show the price/date at any point — all WITHOUT the
    sandboxed report iframe fetching anything (every range is pulled here, server-side)."""
    if not symbol:
        return None
    try:
        import yfinance as yf
        tk = yf.Ticker(symbol)
        fi = tk.fast_info
        last = float(getattr(fi, "last_price", None) or 0)
        if not last:
            return None
        prev = getattr(fi, "previous_close", None)
        prev = float(prev) if prev else None

        # Intraday for the short ranges (best-effort — may be empty when markets are
        # closed/illiquid); one daily pull covers 1M / YTD / 1Y by slicing on date.
        def _hist(**kw):
            try:
                return tk.history(**kw)
            except Exception:
                return None
        s_1d = _series(_hist(period="1d", interval="5m"))
        s_1w = _series(_hist(period="5d", interval="30m"))
        daily = _series(_hist(period="1y", interval="1d"))

        now_ms = int(_dt.datetime.now().timestamp() * 1000)
        jan1_ms = int(_dt.datetime(_dt.datetime.now().year, 1, 1).timestamp() * 1000)
        s_1m = [p for p in daily if p[0] >= now_ms - 31 * 86400 * 1000]
        s_ytd = [p for p in daily if p[0] >= jan1_ms]

        series = {}
        for key, ser in (("1D", s_1d), ("1W", s_1w), ("1M", s_1m), ("YTD", s_ytd), ("1Y", daily)):
            if len(ser) >= 2:
                series[key] = ser
        if not series:
            return None

        mc = getattr(fi, "market_cap", None)
        return {
            "price": round(last, 2),
            "change_pct": round((last - prev) / prev * 100, 2) if prev else None,
            "market_cap": float(mc) if mc else None,
            "year_high": round(float(getattr(fi, "year_high", 0) or 0), 2) or None,
            "year_low": round(float(getattr(fi, "year_low", 0) or 0), 2) or None,
            "currency": getattr(fi, "currency", None),
            "series": series,
        }
    except Exception:
        return None

@st.cache_data(ttl=600, show_spinner="Loading live prices...")
def _live_quotes(symbols):
    """Fetch many tickers in parallel; cached 10 min so it runs at most ~6x/hour."""
    out = {}
    as_of = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_fetch_quote, s): s for s in symbols}
        for fut in concurrent.futures.as_completed(futs):
            try:
                q = fut.result(timeout=20)   # 3 history pulls (intraday + daily) per ticker
            except Exception:
                q = None
            if q:
                q["as_of"] = as_of
                out[futs[fut]] = q
    return out

_live_syms = tuple(sorted({
    _yahoo_symbol(r.get("ticker"), r.get("exchange"))
    for r in REPORTS.values()
    if isinstance(r, dict) and _yahoo_symbol(r.get("ticker"), r.get("exchange"))
}))
_LIVE = _live_quotes(_live_syms) if _live_syms else {}
for _r in REPORTS.values():
    if isinstance(_r, dict) and _r.get("ticker"):
        _q = _LIVE.get(_yahoo_symbol(_r.get("ticker"), _r.get("exchange")))
        if _q:
            _r["live"] = _q

# ── Color maps ────────────────────────────────────────────────────────────────
# Layer + domain colors now come from taxonomy.py (LAYER_COLORS / DOMAIN_COLORS).
# GROUP_COLORS merges both so a node placed in EITHER a layer or a domain can be
# colored from one lookup.

CHAIN_COLORS = {
    "nvidia_vera_rubin":      "#76b900",
    "google_tpu_v7_ironwood": "#4285f4",
    "nvda_b200":              "#ff6b35",
    "optical_networking":     "#8b5cf6",
    "broadcom_custom_asic":   "#f43f5e",
    "hbm_memory":             "#06d6a0",
    "nand_flash":             "#f59e0b",
    "cpu_datacenter":         "#ef4444",
    "mlcc":                   "#0ea5e9",
    "power_cooling":          "#f97316",
    "foundry":                "#a78bfa",
    "amd_mi450_helios":       "#ed1c24",
    "aws_trainium2":          "#ff9900",
    "packaging_substrate":    "#14b8a6",
    "tpu_v8t":                "#1a73e8",
    "tpu_v8i":                "#34a853",
    "amd_mi355":              "#b91c1c",
    "aws_trainium3":          "#cc7a00",
    "neocloud":               "#2dd4bf",
    "power_semiconductor":    "#eab308",
}


# ── Per-chain source files (for the 2D chain view) ────────────────────────────
# The merged graph flattens tier ORDER away; the original chain JSONs keep the
# curated flow order (equipment → … → ai_lab), so the 2D view reads them directly.
@st.cache_data
def load_chain_files():
    out = {}
    for p in glob.glob(os.path.join("chains", "**", "*.json"), recursive=True):
        stem = os.path.splitext(os.path.basename(p))[0]
        with open(p, encoding="utf-8") as f:
            out[stem] = json.load(f)
    return out

# ── Compute degree (total edge count per node) across full graph ──────────────
# Degree = number of edges touching a node (in + out).
# Used for node size: more connections → bigger sphere.
degree = defaultdict(int)
for edge in graph["edges"]:
    degree[edge["source"]] += 1
    degree[edge["target"]] += 1

# ── Status badges + data freshness (precomputed once per run) ────────────────
# Same keyword heuristics as the click panel, run over each node's grounded
# signal text. Result rides on the node object so the graph render loop only
# ever READS precomputed values — no runtime text matching.
BADGE_PATTERNS = {
    "tight":   re.compile(r"sold out|fully allocated|fully booked|booked out|almost fully|nearly fully subscribed|exceed.{0,12}(production )?capacity|demand.{0,20}outpac|demand.{0,20}exceed|capacity.{0,15}constrain|allocated through|supply.{0,20}tight|very tight|capacity.{0,12}tight|tight (into|through|beyond)", re.I),
    "guideup": re.compile(r"rais(ed|ing)\s[^.;]{0,45}(guidance|outlook|target|growth|forecast|guide)|guidance raised|raised guidance|outlook raised|raised to|increase[sd]? (our |its )?(full[- ]year|fy|annual)", re.I),
    "lta":     re.compile(r"\bLTA|long[- ]term (supply )?(agreement|contract|offtake)|multi[- ]?year (supply |purchase |contract|agreement|commitment)|supply agreement|\bNBM|\bSCA\b|build[- ]to[- ]order contract|purchase commitment", re.I),
    "capex":   re.compile(r"capacity expansion|expand(ing)? (our |its )?(manufacturing |production )?capacity|new (fab|facility|factory|plant|cleanroom|building)|additional capacity|capacity invest|broke ground|increase[sd]? capacity", re.I),
}
BADGE_EMOJI = {"tight": "⚡", "guideup": "📈", "lta": "📜", "capex": "🏗️"}

LABEL_DATE = re.compile(r"\((\d{2})-(\d{2})-(\d{4})\)")
TODAY = datetime.now()
STALE_DAYS = 180

def node_signal_meta(node):
    """Badges + freshness for one node, from its quarterly_data labels/text."""
    text_parts, latest = [], None
    for q in node.get("quarterly_data", []):
        text_parts.append((q.get("signal") or "") + " " + (q.get("figure") or ""))
        m = LABEL_DATE.search(q.get("quarter") or "")
        if m:
            try:
                d = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                if latest is None or d > latest:
                    latest = d
            except ValueError:
                pass
    text = " ".join(text_parts)
    badges = [k for k, pat in BADGE_PATTERNS.items() if pat.search(text)]
    stale = latest is None or (TODAY - latest).days > STALE_DAYS
    return badges, (latest.strftime("%Y-%m-%d") if latest else None), stale

# ── Incoming-edge index (who supplies INTO each company) ─────────────────────
# Precomputed in Python so the click panel never has to scan all edges in JS.
# Contract signals are truncated to keep the HTML payload small.
incoming_index = defaultdict(list)
for edge in graph["edges"]:
    short_contracts = [
        {
            "signal": (c.get("signal") or "")[:220],
            "units":  c.get("units"),
            "value":  c.get("value"),
        }
        for c in edge["contracts"][:2]
    ]
    incoming_index[edge["target"]].append({
        "source":       edge["source"],
        "relationship": edge["relationship"],
        "contracts":    short_contracts,
    })

# ── Build full node + link lists ──────────────────────────────────────────────
all_nodes_js = []
for node in graph["nodes"]:
    # A node's color comes from its FIRST layer (top-most role); domain-only nodes
    # (power/thermal/…) fall back to their domain color.
    layers  = node.get("layers", [])
    domains = node.get("domains", [])
    primary = layers[0] if layers else (domains[0] if domains else "unknown")
    deg = degree[node["id"]]
    val = max(4, int(deg ** 1.5))  # non-linear scaling — hubs grow much bigger
    badges, last_data, stale = node_signal_meta(node)
    badge_str = "".join(BADGE_EMOJI[b] for b in badges)
    # Hover tooltip: name + badge emojis only (freshness lives in the panel)
    hover = node["id"] + ((" " + badge_str) if badge_str else "")
    logo = LOGOS.get(node["id"])
    all_nodes_js.append({
        "id":             node["id"],
        "primary":        primary,
        "layers":         layers,
        "domains":        domains,
        "sectors":        node.get("sectors", []),
        "chains":         node["chains"],
        "products":       node["products"],
        "quarterly_data": node["quarterly_data"],
        "incoming":       incoming_index.get(node["id"], []),
        "color":          GROUP_COLORS.get(primary, "#94a3b8"),
        "val":            val,
        "ticker":         node.get("ticker"),
        "exchange":       node.get("exchange"),
        "country":        node.get("country"),
        "status":         node.get("status", "public"),
        "badges":         badges,
        "lastData":       last_data,
        "stale":          stale,
        "hover":          hover,
        "logo":           logo_data_uri(logo["file"]) if logo else None,
        "logoBg":         logo["bg"] if logo else None,
        "report":         REPORTS.get(node["id"]),
    })

all_links_js = []
for edge in graph["edges"]:
    all_links_js.append({
        "source":       edge["source"],
        "target":       edge["target"],
        "relationship": edge["relationship"],
        "contracts":    edge["contracts"][:3],
        "chain":        edge["chain"],
        "color":        CHAIN_COLORS.get(edge["chain"], "#8b949e"),
    })

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.title("AI Supply Chain")

    st.markdown("---")
    st.markdown("**Chains**")
    chain_checks = {}
    for chain, color in CHAIN_COLORS.items():
        label = chain.replace("_", " ")
        col_dot, col_box = st.columns([0.12, 0.88])
        with col_dot:
            st.markdown(f'<span style="color:{color}; font-size:16px; line-height:2">●</span>', unsafe_allow_html=True)
        with col_box:
            chain_checks[chain] = st.checkbox(label, value=True, key=f"chain_{chain}")

    st.markdown("---")
    with st.expander("**Layers**", expanded=False):
        layer_checks = {}
        for slug, name, color in LAYERS:   # canonical top→bottom order
            col_dot, col_box = st.columns([0.12, 0.88])
            with col_dot:
                st.markdown(f'<span style="color:{color}; font-size:16px; line-height:2">●</span>', unsafe_allow_html=True)
            with col_box:
                layer_checks[slug] = st.checkbox(name, value=True, key=f"layer_{slug}")

    with st.expander("**Domains**", expanded=False):
        domain_checks = {}
        for slug, name, color in DOMAINS:
            col_dot, col_box = st.columns([0.12, 0.88])
            with col_dot:
                st.markdown(f'<span style="color:{color}; font-size:16px; line-height:2">●</span>', unsafe_allow_html=True)
            with col_box:
                domain_checks[slug] = st.checkbox(name, value=True, key=f"domain_{slug}")

    st.markdown("---")
    dim_stale = st.checkbox(
        f"Dim stale nodes (no data in {STALE_DAYS}d)",
        value=False,
        help="Grey out companies whose newest signal is older than 6 months — or that have no signals at all. Hover a node to see its last-data date.",
    )
    st.markdown("---")

# ── Apply filters ─────────────────────────────────────────────────────────────
selected_chains  = [c for c, v in chain_checks.items() if v]
selected_layers  = [s for s, v in layer_checks.items() if v]
selected_domains = [s for s, v in domain_checks.items() if v]

# A node is visible if it belongs to at least one selected chain AND
# (one selected layer OR one selected domain). Nodes with no placement are always shown.
visible_nodes = [
    n for n in all_nodes_js
    if (not n["chains"] or any(c in selected_chains for c in n["chains"]))
    and ((not n["layers"] and not n["domains"])
         or any(s in selected_layers for s in n["layers"])
         or any(s in selected_domains for s in n["domains"]))
]
visible_ids = {n["id"] for n in visible_nodes}

# An edge is visible only if its chain is selected and both endpoints are visible.
visible_links = [
    l for l in all_links_js
    if l["chain"] in selected_chains
    and l["source"] in visible_ids
    and l["target"] in visible_ids
]

# Stale-node dimming: applied here (Python, per rerun) so the JS render loop
# just reads the final color — toggling reruns the script, not the simulation.
if dim_stale:
    for n in visible_nodes:
        if n["stale"]:
            n["color"] = "#3a3f46"

# ── Serialize for injection into HTML ────────────────────────────────────────
# (focus_node_json is built later, inside the Graph tab where the search box lives)
# `</` is escaped so report/signal free-text can never close the <script> early.
graph_data_json   = json.dumps({"nodes": visible_nodes, "links": visible_links}).replace("</", "<\\/")
# One color/name map covering both layers and domains, for node badges in the JS panel.
group_colors_json = json.dumps(GROUP_COLORS)
group_names_json  = json.dumps(GROUP_NAMES)
chain_colors_json = json.dumps(CHAIN_COLORS)

# ── HTML (JS braces left unescaped — injected via str.replace) ────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; font-family: system-ui, sans-serif; overflow: hidden; }
  #graph { width: 100vw; height: 800px; }

  #panel {
    display: none;
    position: fixed;
    top: 10px; left: 50%;
    transform: translateX(-50%);
    width: min(1200px, 95vw);
    max-height: 780px;
    overflow-y: auto;
    background: rgba(13,17,23,0.985);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px 24px;
    color: #e6edf3;
    font-size: 13px;
    z-index: 999;
    line-height: 1.55;
    scrollbar-width: thin;
    box-shadow: 0 8px 40px rgba(0,0,0,0.6);
  }
  .ph  { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
  .pt  { font-size:22px; font-weight:700; display:flex; align-items:center; gap:12px; }
  .logochip { display:inline-flex; align-items:center; justify-content:center;
              width:96px; height:44px; border-radius:8px; padding:5px 9px; flex:0 0 auto; }
  .logochip.light { background:#f5f7fa; border:1px solid #d0d7de; }
  .logochip.dark  { background:#1c2430; border:1px solid #30363d; }
  .logochip img { max-width:100%; max-height:100%; object-fit:contain; }

  /* Logo badges centered ON graph nodes, sized to the sphere's screen size */
  #nodelogos { position:fixed; inset:0; pointer-events:none; z-index:5; }
  .nlogo { position:absolute; display:none; transform:translate(-50%,-50%);
           background:rgba(245,247,250,0.95); border:1px solid #d0d7de;
           border-radius:999px; box-shadow:0 1px 6px rgba(0,0,0,0.45); }
  .nlogo.dk { background:rgba(28,36,48,0.95); border-color:#30363d; }
  .nlogo img { display:block; width:100%; }
  .repwrap { margin: 2px 0 12px; }
  .repbtn  { background:#1f6feb; border:none; color:#fff; cursor:pointer; font-size:13px;
             font-weight:700; border-radius:7px; padding:8px 16px; margin-right:8px; }
  .repbtn:hover { background:#388bfd; }
  .repbtn-pdf { background:#21262d; border:1px solid #30363d; }
  .repbtn-pdf:hover { background:#2d333b; }
  .repbox  { display:none; margin-top:10px; background:#0d1117; border:1px solid #21262d;
             border-radius:8px; padding:12px 16px; font-size:12.5px; color:#c9d1d9;
             line-height:1.6; max-height:60vh; overflow-y:auto; }
  .repempty { color:#8b949e; }
  /* structured-report rendering */
  .rp-h1 { font-size:15px; font-weight:800; color:#e6edf3; margin:2px 0 10px; }
  .rp-h2 { font-size:11.5px; font-weight:700; color:#58a6ff; text-transform:uppercase;
           letter-spacing:.05em; margin:14px 0 6px; border-top:1px solid #21262d; padding-top:10px; }
  .rp-h3 { font-size:12px; font-weight:700; color:#adbac7; margin:9px 0 3px; }
  .rp-txt { font-size:12.5px; color:#c9d1d9; line-height:1.6; margin:3px 0; }
  .rp-ul  { margin:4px 0 6px 18px; color:#c9d1d9; font-size:12.5px; line-height:1.55; }
  .rp-ul li { margin:3px 0; }
  .rp-card { background:#11151c; border:1px solid #21262d; border-radius:6px; padding:8px 11px; margin:6px 0; }
  .rp-kv  { font-size:12.5px; color:#c9d1d9; line-height:1.7; margin:3px 0; }
  .rp-k   { color:#8b949e; font-weight:700; }
  /* report v2 — richer report styling. IMPORTANT: every .rp-* class added here must also be
     mirrored in PDF_CSS (the light print theme further down) or the PDF export loses it. */
  .rp-mast { display:flex; gap:14px; align-items:center; margin:2px 0 14px; padding-bottom:12px; border-bottom:2px solid #30363d; }
  .rp-mast-body { min-width:0; }
  .rp-eyebrow { font-size:9.5px; letter-spacing:.18em; color:#58a6ff; font-weight:700; text-transform:uppercase; }
  .rp-mast-meta { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:4px; }
  .rp-date { font-size:11px; color:#8b949e; text-decoration:none; }
  .rp-lead { font-size:13.5px; color:#e6edf3; line-height:1.7; margin:6px 0 10px; }
  .rp-note { font-size:12px; color:#8b949e; font-style:italic; margin:6px 0; line-height:1.55; }
  .rp-note-acc { font-size:12px; color:#8b949e; margin:6px 0; }
  .rp-note-acc summary { cursor:pointer; color:#8b949e; font-style:italic; }
  .rp-callout { background:#11151c; border-left:3px solid #58a6ff; border-radius:0 6px 6px 0; padding:8px 12px; margin:8px 0; }
  .rp-callout-h { font-size:10.5px; font-weight:700; color:#58a6ff; text-transform:uppercase; letter-spacing:.05em; margin-bottom:3px; }
  .rp-cite { font-size:11px; color:#8b949e; margin:3px 0 6px; }
  .rp-money { color:#3fb950; font-weight:700; }
  .rp-pct   { color:#e6edf3; font-weight:700; }
  .rp-facts, .rp-asm { list-style:none; margin:4px 0 6px; padding:0; }
  .rp-facts li { border-left:3px solid #3fb950; padding:2px 0 2px 9px; margin:4px 0; color:#c9d1d9; font-size:12.5px; }
  .rp-asm li { border-left:3px solid #d29922; padding:2px 0 2px 9px; margin:4px 0; color:#c9d1d9; font-size:12.5px; }
  .rp-asm-tag { color:#d29922; font-weight:700; }
  .rp-acc { border:1px solid #21262d; border-radius:6px; margin:5px 0; background:#11151c; }
  .rp-acc summary { cursor:pointer; padding:7px 11px; font-weight:700; color:#adbac7; font-size:12.5px; list-style:none; }
  .rp-acc summary::-webkit-details-marker { display:none; }
  .rp-acc summary::before { content:'+ '; color:#58a6ff; font-weight:700; }
  .rp-acc[open] summary::before { content:'- '; }
  .rp-acc > .rp-txt { padding:0 11px 9px; }
  .rp-seg-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  @media (max-width:760px){ .rp-seg-grid, .rp-scen-grid { grid-template-columns:1fr; } }
  .rp-seg-name { font-weight:700; color:#e6edf3; font-size:13px; margin-bottom:4px; }
  .rp-seg-metrics { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:5px; }
  .rp-metric { background:#0d1117; border:1px solid #21262d; border-radius:5px; padding:2px 7px; font-size:11.5px; color:#c9d1d9; }
  .rp-risk-head { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
  .rp-risk-title { font-weight:700; color:#e6edf3; font-size:12.5px; }
  .rp-sev { display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:700; background:#161b22; border:1px solid #8b949e; color:#8b949e; text-transform:uppercase; letter-spacing:.04em; flex:0 0 auto; }
  .rp-sev-very-high, .rp-sev-high { color:#f85149; border-color:#f85149; }
  .rp-sev-medium { color:#d29922; border-color:#d29922; }
  .rp-sev-low { color:#3fb950; border-color:#3fb950; }
  .rp-scen-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  .rp-scen { background:#11151c; border:1px solid #21262d; border-top:3px solid #8b949e; border-radius:6px; padding:9px 11px; }
  .rp-scen-bull { border-top-color:#3fb950; } .rp-scen-base { border-top-color:#58a6ff; } .rp-scen-bear { border-top-color:#f85149; }
  .rp-scen-head { font-weight:800; font-size:12.5px; color:#e6edf3; margin-bottom:4px; }
  .rp-src { margin:4px 0 6px 0; padding-left:18px; font-size:12px; color:#c9d1d9; }
  .rp-src a { color:#58a6ff; text-decoration:none; } .rp-src a:hover { text-decoration:underline; }
  .rp-src-date { color:#6e7681; font-size:10.5px; }
  /* report v2 charts — inline, dependency-free. Bar/stack colors are passed inline so
     they look identical in the dark UI and the light PDF; mirror the layout in PDF_CSS. */
  .rp-accent { height:3px; border-radius:3px; margin:0 0 12px; background:linear-gradient(90deg,#58a6ff,#a371f7,#3fb950); }
  .rp-chart { background:#0d1117; border:1px solid #21262d; border-radius:8px; padding:11px 13px; margin:8px 0 11px; }
  .rp-chart-title { font-size:11px; font-weight:700; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; margin-bottom:9px; }
  .rp-bar-row { display:flex; align-items:center; gap:9px; margin:5px 0; }
  .rp-bar-label { flex:0 0 36%; font-size:11.5px; color:#c9d1d9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .rp-bar-track { flex:1; background:#161b22; border-radius:4px; height:16px; overflow:hidden; }
  .rp-bar-fill { height:100%; border-radius:4px; min-width:2px; }
  .rp-bar-val { flex:0 0 auto; font-size:11px; color:#e6edf3; font-weight:700; font-family:monospace; }
  .rp-stack { display:flex; height:18px; border-radius:5px; overflow:hidden; margin:2px 0 9px; background:#161b22; }
  .rp-stack-seg { height:100%; }
  .rp-legend { display:flex; flex-wrap:wrap; gap:14px; font-size:11px; color:#c9d1d9; }
  .rp-legend-item { display:flex; align-items:center; gap:5px; }
  .rp-legend-dot { width:9px; height:9px; border-radius:2px; display:inline-block; }
  .rp-quote { background:linear-gradient(180deg,#11151c,#0d1117); border:1px solid #21262d; border-radius:10px; padding:12px 14px; margin:4px 0 14px; }
  .rp-q-top { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  .rp-q-price { font-size:26px; font-weight:800; color:#e6edf3; }
  .rp-q-chg { font-size:14px; font-weight:700; }
  .rp-q-chg.up { color:#3fb950; } .rp-q-chg.down { color:#f85149; }
  .rp-q-live { margin-left:auto; font-size:10px; font-weight:700; color:#8b949e; letter-spacing:.04em; }
  .rp-q-stats { display:flex; flex-wrap:wrap; gap:18px; margin:8px 0 2px; font-size:12px; color:#c9d1d9; }
  .rp-q-lbl { color:#8b949e; font-weight:700; margin-right:5px; }
  .rp-spark { width:100%; height:120px; display:block; margin:0; }
  /* interactive price chart: range buttons + hover/touch readout + crosshair overlay */
  .rp-range { display:flex; gap:4px; margin:10px 0 4px; }
  .rp-rbtn { background:#161b22; border:1px solid #30363d; color:#8b949e; font:700 11px monospace;
             padding:3px 9px; border-radius:6px; cursor:pointer; }
  .rp-rbtn:hover { color:#e6edf3; border-color:#3fb950; }
  .rp-rbtn.active { background:#1f6feb; border-color:#1f6feb; color:#fff; }
  .rp-rbtn:disabled { opacity:.35; cursor:default; }
  .rp-read { display:flex; align-items:baseline; gap:10px; min-height:18px; margin:2px 0 4px; }
  .rp-rd-price { font:700 14px monospace; color:#e6edf3; }
  .rp-rd-meta { font:11px monospace; color:#8b949e; }
  .rp-cwrap { position:relative; width:100%; }
  .rp-cross { position:absolute; top:0; bottom:0; width:1px; background:#8b949e; opacity:.55; display:none; pointer-events:none; }
  .rp-dot { position:absolute; width:9px; height:9px; border-radius:50%; border:2px solid #0d1117; transform:translate(-50%,-50%); display:none; pointer-events:none; }
  .rp-hit { position:absolute; inset:0; cursor:crosshair; }
  .pgrid { display:grid; grid-template-columns: 1.15fr 1fr; gap:0 22px; align-items:start; }
  @media (max-width: 900px) { .pgrid { grid-template-columns: 1fr; } }
  .pcol  { min-width:0; }
  .xb  { background:none; border:none; color:#8b949e; cursor:pointer; font-size:18px; }
  .badge  { display:inline-block; padding:2px 7px; border-radius:10px; font-size:10px; font-weight:700; color:#0d1117; margin:2px; }
  .sbadge { display:inline-block; padding:4px 11px; border-radius:12px; font-size:12px; font-weight:700; background:#161b22; border:1px solid; margin:3px 4px 3px 0; }
  .tlrow  { display:flex; gap:10px; margin:6px 0; align-items:flex-start; background:#11151c; border-radius:6px; padding:6px 9px; }
  .tlwhen { flex:0 0 96px; color:#58a6ff; font-size:11.5px; font-weight:700; font-family:monospace; padding-top:1px; }
  .tltext { flex:1; font-size:12.5px; color:#c9d1d9; }
  .cbadge { display:inline-block; padding:1px 6px; border-radius:6px; font-size:10px; background:#161b22; color:#8b949e; margin:2px; border-left:2px solid; }
  .sec { color:#8b949e; font-size:11px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin:14px 0 7px; padding-top:10px; border-top:1px solid #21262d; }
  .card { background:#161b22; border-radius:8px; padding:9px 12px; margin:6px 0; font-size:12.5px; }
  .sig-hidden { display:none; }
  .morebtn { background:#161b22; border:1px solid #30363d; color:#58a6ff; cursor:pointer;
             font-size:12px; border-radius:6px; padding:6px 10px; margin:6px 0; width:100%; }
  .qtr { color:#58a6ff; font-size:10.5px; margin-bottom:3px; }
  .fig { color:#3fb950; font-weight:600; margin-top:3px; font-size:12px; }
  .rel { color:#8b949e; font-size:11px; display:block; margin-top:2px; }
  .ctract { background:#0d1117; border-radius:5px; padding:6px 9px; margin:4px 0; border-left:2px solid #21262d; font-size:12px; }
  .cv { color:#3fb950; }
  .meta { display:flex; align-items:center; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
  .ticker { font-family:monospace; font-size:13px; font-weight:700; color:#58a6ff; }
  .exchange { font-size:10px; color:#8b949e; }
  .country { font-size:12px; }
  .private-tag { font-size:10px; color:#8b949e; background:#21262d; padding:2px 7px; border-radius:8px; }
</style>
</head>
<body>
<div id="graph"></div>

<div id="panel">
  <div class="ph">
    <span class="pt" id="ptitle"></span>
    <button class="xb" onclick="document.getElementById('panel').style.display='none';focusLogoId=null;">&#x2715;</button>
  </div>
  <div id="pbody"></div>
</div>

<script src="https://unpkg.com/3d-force-graph@1.73.0/dist/3d-force-graph.min.js"></script>

<script>
const GDATA   = __GRAPH_DATA__;
const GCOLORS = __GROUP_COLORS__;   // layer + domain slug -> color
const GNAMES  = __GROUP_NAMES__;    // layer + domain slug -> display name
const CCOLORS = __CHAIN_COLORS__;
const FOCUS   = __FOCUS_NODE__;

// Parse the canonical (MM-DD-YYYY) suffix on a source label into a sortable
// YYYYMMDD integer so signals can be ordered newest-first. Labels without a
// recognizable date sort last (return -1).
function sigDate(label) {
  const m = /\((\d{2})-(\d{2})-(\d{4})\)/.exec(label || '');
  return m ? (+m[3]) * 10000 + (+m[1]) * 100 + (+m[2]) : -1;
}

// Status badges derived from the clicked company's own signals (O(#signals),
// runs only on click — never in the render loop). Keyword heuristics over the
// grounded signal text; a badge links back to the sentence that triggered it.
const BADGE_RULES = [
  { key: 'tight',    label: '⚡ Supply tight',     color: '#f85149',
    re: /sold out|fully allocated|fully booked|booked out|almost fully|nearly fully subscribed|exceed.{0,12}(production )?capacity|demand.{0,20}outpac|demand.{0,20}exceed|capacity.{0,15}constrain|allocated through|supply.{0,20}tight|very tight|capacity.{0,12}tight|tight (into|through|beyond)/i },
  { key: 'guideup',  label: '📈 Guidance raised', color: '#3fb950',
    re: /rais(ed|ing)\s[^.;]{0,45}(guidance|outlook|target|growth|forecast|guide)|guidance raised|raised guidance|outlook raised|raised to|increase[sd]? (our |its )?(full[- ]year|fy|annual)/i },
  { key: 'lta',      label: '📜 Long-term contracts', color: '#a371f7',
    re: /\\bLTA|long[- ]term (supply )?(agreement|contract|offtake)|multi[- ]?year (supply |purchase |contract|agreement|commitment)|supply agreement|\\bNBM|\\bSCA\\b|build[- ]to[- ]order contract|purchase commitment/i },
  { key: 'capex',    label: '🏗️ Capacity expanding', color: '#d29922',
    re: /capacity expansion|expand(ing)? (our |its )?(manufacturing |production )?capacity|new (fab|facility|factory|plant|cleanroom|building)|additional capacity|capacity invest|broke ground|increase[sd]? capacity/i },
];

function buildBadges(sigs) {
  const hits = {};
  sigs.forEach(q => {
    const text = (q.signal || '') + ' ' + (q.figure || '');
    BADGE_RULES.forEach(r => {
      if (!hits[r.key] && r.re.test(text)) hits[r.key] = r;
    });
  });
  return BADGE_RULES.filter(r => hits[r.key]);
}

// Product / capacity timeline: pull date-bearing sentences out of the clicked
// company's signals and order them chronologically. Heuristic extraction —
// the full signal text below stays the source of truth.
const DATE_RE = /\\b(Q[1-4]\s*(?:FY\s*)?20\d\d|[12]H\s*20\d\d|H[12]\s*(?:FY\s*)?20\d\d|(?:early|mid|late|end of|exiting|through|by)\s*(?:calendar |CY|fiscal |FY)?\s*20\d\d|CY20\d\d|FY20\d\d|20\d\d)\\b/i;

function dateKey(s) {
  // Rough chronological key: year*10 + quarter/half hint (for ordering only).
  const y = /20(\d\d)/.exec(s);
  if (!y) return 99999;
  let k = (+('20' + y[1])) * 10;
  const q = /Q([1-4])/i.exec(s);
  const h = /([12])H|H([12])/.exec(s);
  if (q) k += +q[1] * 2;
  else if (h) k += (+(h[1] || h[2])) * 4;
  else if (/late|end|exiting|H2/i.test(s)) k += 8;
  else if (/mid/i.test(s)) k += 5;
  else if (/early|H1/i.test(s)) k += 2;
  return k;
}

function buildTimeline(sigs) {
  const items = [];
  const seen = new Set();
  sigs.forEach(q => {
    (q.signal || '').split(/(?<=[.;])\s+/).forEach(sent => {
      const t = sent.trim();
      if (t.length < 25 || t.length > 240) return;
      const m = DATE_RE.exec(t);
      if (!m) return;
      const dedup = t.slice(0, 60);
      if (seen.has(dedup)) return;
      seen.add(dedup);
      items.push({ when: m[1], key: dateKey(m[1]), text: t });
    });
  });
  items.sort((a, b2) => a.key - b2.key);
  return items.slice(0, 10);
}

// ── Stock-report renderer ────────────────────────────────────────────────────
// reports/<company>.json holds a structured report (nested objects/arrays). This
// turns ANY such JSON into readable HTML so new reports render without code
// changes: primitive fields → "Key: value" lines, string arrays → bullets,
// object arrays → cards, nested objects → labelled sections. A plain-string
// report (from reports.json) is shown as-is with line breaks preserved.
function rEsc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function rKey(k) {
  // underscores -> spaces, then Title Case the first letter of each word.
  // (matches start-or-space + word char rather than a word boundary: a real word
  //  boundary uses backslash-b, which the non-raw Python template turns into a
  //  literal backspace and would silently break this.)
  return String(k).replace(/_/g, ' ').replace(/(^| )\w/g, m => m.toUpperCase());
}
function rIsPrim(v) {
  return v === null || ['string', 'number', 'boolean'].includes(typeof v);
}
// Keys whose value (when short) becomes a card's bold title instead of a "Key: value" line.
const TITLE_KEYS = ['name', 'segment', 'trend', 'driver', 'risk', 'company', 'scenario', 'term'];

function sectionHead(label) { return `<div class="rp-h2">${rEsc(label)}</div>`; }

// Highlight money ($81.4M), percents (+154% YoY) and multiples (~12x) inside an
// ALREADY HTML-escaped string so the numbers pop out of the prose. Patterns are
// conservative (must contain $, % or digit+x) so ordinary words are never touched.
// NB: no \b word boundaries — the non-raw Python template would turn \b into a
// literal backspace and silently break the regex.
function emphasizeMetric(s) {
  if (!s) return s;
  return String(s)
    .replace(/(\$\s?\d[\d,.]*\s?(?:billion|million|thousand|trillion|[MBKT])?)/g, '<span class="rp-money">$1</span>')
    .replace(/([+\-]?\d[\d,.]*\s?%(?:\s?(?:YoY|QoQ|CAGR))?)/g, '<span class="rp-pct">$1</span>')
    .replace(/(~?\d+(?:\.\d+)?x)/g, '<span class="rp-money">$1</span>');
}

function renderNote(s) {
  const esc = emphasizeMetric(rEsc(s));
  // very long legal text collapses so it does not dominate the panel.
  if (String(s).length > 280)
    return `<details class="rp-note-acc"><summary>Disclaimer / note</summary><div class="rp-note">${esc}</div></details>`;
  return `<div class="rp-note">${esc}</div>`;
}

function renderAnalystView(k, val) {
  let label = 'Analyst View';
  const pre = k.replace(/_?analyst_view$/, '');
  if (pre) label = rKey(pre) + ' — Analyst View';
  let body;
  if (Array.isArray(val))
    body = '<ul class="rp-ul">' + val.map(x => `<li>${emphasizeMetric(rEsc(x))}</li>`).join('') + '</ul>';
  else if (rIsPrim(val))
    body = `<div class="rp-txt">${emphasizeMetric(rEsc(val))}</div>`;
  else
    body = renderVal(val, 2);   // object value (e.g. implied_multiples_analyst_view) → recurse
  return `<div class="rp-callout"><div class="rp-callout-h">${rEsc(label)}</div>${body}</div>`;
}

function renderAccentList(arr, cls) {
  return `<ul class="${cls}">` + arr.map(x => `<li>${emphasizeMetric(rEsc(x))}</li>`).join('') + '</ul>';
}

function renderAssumptionList(arr) {
  return '<ul class="rp-asm">' + arr.map(x => {
    let s = emphasizeMetric(rEsc(x));
    // badge a leading ASSUMPTION:/OPINION:/FACT: label.
    s = s.replace(/^(ASSUMPTION|OPINION|FACT)\s*:/, '<span class="rp-asm-tag">$1:</span>');
    return `<li>${s}</li>`;
  }).join('') + '</ul>';
}

function renderSources(arr) {
  let items = '';
  arr.forEach(s => {
    if (!s) return;
    if (rIsPrim(s)) { items += `<li>${rEsc(s)}</li>`; return; }
    const label = rEsc(s.label || s.url || 'source');
    const date = s.date ? ` <span class="rp-src-date">${rEsc(s.date)}</span>` : '';
    if (s.url && /^https?:/i.test(s.url))
      items += `<li><a href="${rEsc(s.url)}" target="_blank" rel="noopener">${label}</a>${date}</li>`;
    else
      items += `<li>${label}${date}</li>`;
  });
  return '<div class="rp-h3">Sources</div><ul class="rp-src">' + items + '</ul>';
}

function sevSlug(s) { return String(s).toLowerCase().trim().replace(/\s+/g, '-'); }
function sevBadge(s) { return `<span class="rp-sev rp-sev-${sevSlug(s)}">${rEsc(s)}</span>`; }

// ---- tiny inline charts (no chart library; just parse the numbers already in the text) --
// Pull a dollar figure out of a string -> millions (so $1.1B -> 1100). null if none.
function parseMoney(s) {
  if (!s) return null;
  // accept $, €, £, ¥, ₩ so non-US reporters chart too. Bars compare segments WITHIN one
  // report (always the same currency), so the symbol itself does not matter for bar length.
  const m = String(s).match(/[$€£¥₩]\s?([\d,.]+)\s?(billion|trillion|million|thousand|[BMKT])?/i);
  if (!m) return null;
  let n = parseFloat(m[1].replace(/,/g, ''));
  if (isNaN(n)) return null;
  const u = (m[2] || '').toLowerCase();
  if (u === 'b' || u === 'billion') n *= 1000;
  else if (u === 't' || u === 'trillion') n *= 1000000;
  else if (u === 'k' || u === 'thousand') n /= 1000;
  return n;   // value in $M
}

// Horizontal bar chart of revenue per segment (bar length ∝ revenue). Skips segments
// with no parseable figure; needs >= 2 bars to be worth showing, else returns ''.
function renderRevenueChart(segments) {
  if (!Array.isArray(segments)) return '';
  const palette = ['#58a6ff', '#3fb950', '#a371f7', '#d29922', '#ec4899', '#06b6d4'];
  const rows = [];
  segments.forEach((seg, i) => {
    if (!seg || typeof seg !== 'object') return;
    const revKey = Object.keys(seg).find(k => /_revenue$/.test(k));
    if (!revKey) return;
    const val = parseMoney(seg[revKey]);
    if (val === null || val <= 0) return;
    // show just the clean money token (e.g. "$2.6M"), not the whole sentence it sits in.
    const tok = String(seg[revKey]).match(/[$€£¥₩]\s?[\d,.]+\s?(?:billion|trillion|million|thousand|[BMKT])?/i);
    const disp = tok ? tok[0].trim() : String(seg[revKey]).slice(0, 14);
    rows.push({ label: seg.name || seg.segment || 'Segment', value: val, display: rEsc(disp), color: palette[i % palette.length] });
  });
  if (rows.length < 2) return '';
  const max = Math.max.apply(null, rows.map(r => r.value));
  let bars = '';
  rows.forEach(r => {
    const pct = Math.max(2, Math.round(r.value / max * 100));
    bars += `<div class="rp-bar-row"><div class="rp-bar-label" title="${rEsc(r.label)}">${rEsc(r.label)}</div>`
          + `<div class="rp-bar-track"><div class="rp-bar-fill" style="width:${pct}%;background:${r.color}"></div></div>`
          + `<div class="rp-bar-val">${r.display}</div></div>`;
  });
  return `<div class="rp-chart"><div class="rp-chart-title">Revenue by segment</div>${bars}</div>`;
}

// Stacked bar of how many risks fall in each severity tier (very high/high -> red).
function renderRiskChart(risks) {
  if (!Array.isArray(risks) || !risks.length) return '';
  let hi = 0, med = 0, lo = 0;
  risks.forEach(r => {
    const s = r && r.severity ? sevSlug(r.severity) : '';
    if (s === 'very-high' || s === 'high') hi++;
    else if (s === 'medium') med++;
    else if (s === 'low') lo++;
  });
  const total = hi + med + lo;
  if (!total) return '';
  const seg = (n, color) => n ? `<div class="rp-stack-seg" style="width:${Math.round(n / total * 100)}%;background:${color}"></div>` : '';
  const leg = (n, color, label) => n ? `<span class="rp-legend-item"><span class="rp-legend-dot" style="background:${color}"></span>${label}: ${n}</span>` : '';
  return '<div class="rp-chart"><div class="rp-chart-title">Risk profile</div>'
    + '<div class="rp-stack">' + seg(hi, '#f85149') + seg(med, '#d29922') + seg(lo, '#3fb950') + '</div>'
    + '<div class="rp-legend">' + leg(hi, '#f85149', 'High') + leg(med, '#d29922', 'Medium') + leg(lo, '#3fb950', 'Low') + '</div></div>';
}

// ---- live quote card + 1y price sparkline (data injected server-side as report.live) ----
const CUR_SYM = { USD: '$', EUR: '€', GBP: '£', JPY: '¥', KRW: '₩', TWD: 'NT$', HKD: 'HK$', CNY: '¥' };
function curSym(c) { return CUR_SYM[c] || ((c || '') + ' '); }
function fmtComma(n, dec) {
  const parts = Number(n).toFixed(dec).split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');   // thousands separators
  return parts.join('.');
}
function fmtPrice(n, cur) {
  if (n === null || n === undefined) return '';
  const dec = (cur === 'KRW' || cur === 'JPY' || cur === 'TWD') ? 0 : 2;
  return curSym(cur) + fmtComma(n, dec);
}
function fmtCap(n, cur) {
  if (!n) return '';
  const a = Math.abs(n);
  let v = n, u = '';
  if (a >= 1e12) { v = n / 1e12; u = 'T'; }
  else if (a >= 1e9) { v = n / 1e9; u = 'B'; }
  else if (a >= 1e6) { v = n / 1e6; u = 'M'; }
  return curSym(cur) + v.toFixed(2) + u;
}

// ---- interactive multi-range price chart ----
// Data for every range is injected server-side as live.series = { "1D":[[ts_ms,close],...], ... }
// (the report renders in a sandboxed iframe that can't fetch, so nothing is loaded here).
// The chart block is built as a STRING so it also shows statically in the script-less PDF
// window; hover/touch + range switching are layered on via inline handlers that only run
// where this script exists (the live panel). Per-chart state lives in window.__rpCharts[cid].
const RP_RANGES = ['1D', '1W', '1M', 'YTD', '1Y'];
const RP_W = 600, RP_H = 120, RP_PAD = 6;

function rpFmtDate(ts, range) {
  const d = new Date(ts);
  if (range === '1D' || range === '1W')
    return d.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  return d.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
}

// [ts, close] points -> SVG path "d", filled area, and lo/hi. The svg is stretched to the
// container width (preserveAspectRatio="none"), so x is just the index fraction.
function rpPaths(pts) {
  const n = pts.length;
  let lo = Infinity, hi = -Infinity;
  for (const p of pts) { if (p[1] < lo) lo = p[1]; if (p[1] > hi) hi = p[1]; }
  if (hi === lo) hi = lo + 1;
  const xa = i => RP_PAD + (n < 2 ? 0 : i / (n - 1)) * (RP_W - 2 * RP_PAD);
  const ya = v => RP_PAD + (1 - (v - lo) / (hi - lo)) * (RP_H - 2 * RP_PAD);
  let d = '';
  pts.forEach((p, i) => { d += (i ? 'L' : 'M') + xa(i).toFixed(1) + ' ' + ya(p[1]).toFixed(1) + ' '; });
  const area = d + 'L' + xa(n - 1).toFixed(1) + ' ' + (RP_H - RP_PAD) + ' L' + xa(0).toFixed(1) + ' ' + (RP_H - RP_PAD) + ' Z';
  return { d, area, lo, hi };
}

// Build the full chart block (range buttons + readout + svg + crosshair overlay).
function rpChartHtml(cid, series, cur, defRange) {
  const avail = RP_RANGES.filter(r => (series[r] || []).length >= 2);
  if (!avail.length) return '';
  const range = avail.indexOf(defRange) >= 0 ? defRange : avail[0];
  (window.__rpCharts = window.__rpCharts || {})[cid] = { series, cur, range };
  const pts = series[range], g = rpPaths(pts);
  const up = pts[pts.length - 1][1] >= pts[0][1];
  const col = up ? '#3fb950' : '#f85149';
  const gid = cid + '-grad';
  const btns = RP_RANGES.map(r => {
    const on = (series[r] || []).length >= 2;
    return '<button class="rp-rbtn' + (r === range ? ' active' : '') + '" id="' + cid + '-b-' + r + '"'
      + (on ? ` onclick="rpSet('` + cid + `','` + r + `')"` : ' disabled') + '>' + r + '</button>';
  }).join('');
  const last = pts[pts.length - 1], first = pts[0];
  const chg = (last[1] - first[1]) / first[1] * 100;
  const svg = '<svg class="rp-spark" id="' + cid + '-svg" viewBox="0 0 ' + RP_W + ' ' + RP_H + '" preserveAspectRatio="none" role="img" aria-label="price chart">'
    + '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">'
    + '<stop offset="0%" stop-color="' + col + '" stop-opacity="0.30"/><stop offset="100%" stop-color="' + col + '" stop-opacity="0"/></linearGradient></defs>'
    + '<path id="' + cid + '-area" d="' + g.area + '" fill="url(#' + gid + ')"/>'
    + '<path id="' + cid + '-line" d="' + g.d + '" fill="none" stroke="' + col + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
    + '</svg>';
  const readout = '<div class="rp-read">'
    + '<span class="rp-rd-price" id="' + cid + '-rp">' + fmtPrice(last[1], cur) + '</span>'
    + '<span class="rp-rd-meta" id="' + cid + '-rm">' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '% · ' + range + '</span></div>';
  return '<div class="rp-range">' + btns + '</div>' + readout
    + '<div class="rp-cwrap" id="' + cid + '-wrap">' + svg
    + '<div class="rp-cross" id="' + cid + '-cx"></div>'
    + '<div class="rp-dot" id="' + cid + '-dot" style="background:' + col + '"></div>'
    + `<div class="rp-hit" onmousemove="rpMove(event,'` + cid + `')" onmouseleave="rpLeave('` + cid + `')"`
    + ` ontouchstart="rpMove(event,'` + cid + `')" ontouchmove="rpMove(event,'` + cid + `')" ontouchend="rpLeave('` + cid + `')"></div>`
    + '</div>';
}

// Switch range: redraw line/area, recolor, reset the readout to the latest point.
function rpSet(cid, range) {
  const c = window.__rpCharts[cid]; if (!c) return;
  const pts = c.series[range]; if (!pts || pts.length < 2) return;
  c.range = range;
  const g = rpPaths(pts);
  const up = pts[pts.length - 1][1] >= pts[0][1];
  const col = up ? '#3fb950' : '#f85149';
  const line = document.getElementById(cid + '-line'), area = document.getElementById(cid + '-area');
  line.setAttribute('d', g.d); line.setAttribute('stroke', col); area.setAttribute('d', g.area);
  const grad = document.getElementById(cid + '-grad');
  if (grad) grad.querySelectorAll('stop').forEach(s => s.setAttribute('stop-color', col));
  document.getElementById(cid + '-dot').style.background = col;
  RP_RANGES.forEach(r => { const b = document.getElementById(cid + '-b-' + r); if (b) b.classList.toggle('active', r === range); });
  rpLeave(cid);
}

// Pointer move -> nearest data point: position crosshair + dot, update price/date readout.
function rpMove(evt, cid) {
  const c = window.__rpCharts[cid]; if (!c) return;
  const pts = c.series[c.range]; if (!pts || pts.length < 2) return;
  const wrap = document.getElementById(cid + '-wrap'), rect = wrap.getBoundingClientRect();
  const clientX = evt.touches && evt.touches[0] ? evt.touches[0].clientX : evt.clientX;
  let f = (clientX - rect.left) / rect.width;
  f = Math.max(0, Math.min(1, f));
  const i = Math.round(f * (pts.length - 1)), p = pts[i];
  let lo = Infinity, hi = -Infinity;
  for (const q of pts) { if (q[1] < lo) lo = q[1]; if (q[1] > hi) hi = q[1]; }
  if (hi === lo) hi = lo + 1;
  const xF = i / (pts.length - 1);
  const yF = (RP_PAD + (1 - (p[1] - lo) / (hi - lo)) * (RP_H - 2 * RP_PAD)) / RP_H;
  const cx = document.getElementById(cid + '-cx'), dot = document.getElementById(cid + '-dot');
  cx.style.left = (xF * 100) + '%'; cx.style.display = 'block';
  dot.style.left = (xF * 100) + '%'; dot.style.top = (yF * 100) + '%'; dot.style.display = 'block';
  document.getElementById(cid + '-rp').textContent = fmtPrice(p[1], c.cur);
  document.getElementById(cid + '-rm').textContent = rpFmtDate(p[0], c.range);
  if (evt.cancelable && evt.touches) evt.preventDefault();   // stop page-scroll while scrubbing
}

// Pointer leave: hide crosshair, reset readout to the latest point + range change.
function rpLeave(cid) {
  const c = window.__rpCharts[cid]; if (!c) return;
  const pts = c.series[c.range]; if (!pts || !pts.length) return;
  const cx = document.getElementById(cid + '-cx'), dot = document.getElementById(cid + '-dot');
  if (cx) cx.style.display = 'none';
  if (dot) dot.style.display = 'none';
  const last = pts[pts.length - 1], first = pts[0], chg = (last[1] - first[1]) / first[1] * 100;
  const rp = document.getElementById(cid + '-rp'), rm = document.getElementById(cid + '-rm');
  if (rp) rp.textContent = fmtPrice(last[1], c.cur);
  if (rm) rm.textContent = (chg >= 0 ? '+' : '') + chg.toFixed(2) + '% · ' + c.range;
}

function renderLiveQuote(live, opts) {
  if (!live || live.price === null || live.price === undefined) return '';
  const cur = live.currency || 'USD';
  const up = (live.change_pct || 0) >= 0;
  const chg = (live.change_pct === null || live.change_pct === undefined) ? ''
    : '<span class="rp-q-chg ' + (up ? 'up' : 'down') + '">' + (up ? '▲' : '▼') + ' ' + Math.abs(live.change_pct).toFixed(2) + '%</span>';
  let stats = '';
  if (live.market_cap) stats += '<span class="rp-q-stat"><span class="rp-q-lbl">Mkt cap</span>' + fmtCap(live.market_cap, cur) + '</span>';
  if (live.year_low && live.year_high)
    stats += '<span class="rp-q-stat"><span class="rp-q-lbl">52-wk</span>' + fmtPrice(live.year_low, cur) + ' – ' + fmtPrice(live.year_high, cur) + '</span>';
  // 1D is the default live view; the PDF print view is a static snapshot, so default it to 1Y.
  const cid = 'rpc' + (window.__rpSeq = (window.__rpSeq || 0) + 1);
  const chart = (live.series && Object.keys(live.series).length)
    ? rpChartHtml(cid, live.series, cur, (opts && opts.pdf) ? '1Y' : '1D') : '';
  return '<div class="rp-quote"><div class="rp-q-top">'
    + '<div class="rp-q-price">' + fmtPrice(live.price, cur) + '</div>' + chg
    + '<div class="rp-q-live"><span style="color:#3fb950">●</span> LIVE' + (live.as_of ? ' · ' + rEsc(live.as_of) : '') + '</div></div>'
    + (stats ? '<div class="rp-q-stats">' + stats + '</div>' : '')
    + chart
    + '</div>';
}

// Recurring field names get one consistent treatment everywhere (used by both the
// generic renderer and the section handlers). Returns HTML, or null if k is not a
// known convention so the caller falls back to its default rendering.
function renderByConvention(k, val) {
  if (val === null || val === undefined || val === '') return null;
  if (k.endsWith('analyst_view')) return renderAnalystView(k, val);
  if (k === 'facts' && Array.isArray(val)) return renderAccentList(val, 'rp-facts');
  if ((k === 'assumptions' || k === 'what_is_assumption_or_opinion') && Array.isArray(val))
    return renderAssumptionList(val);
  if (k === 'sources' && Array.isArray(val)) return renderSources(val);
  if (k === 'evidence' && rIsPrim(val)) return `<div class="rp-cite">${emphasizeMetric(rEsc(val))}</div>`;
  if (k === 'severity' && rIsPrim(val)) return `<div class="rp-kv">${sevBadge(val)}</div>`;
  if (rIsPrim(val) && (k === 'disclaimer' || k === 'note' || k === 'reminder' || /_(disclaimer|note|reminder)$/.test(k)))
    return renderNote(val);
  return null;
}

// Generic JSON -> HTML. Unknown shapes still render (so new report fields never
// break), but recurring field names and prose/scalars now get distinct styling.
function renderVal(v, depth) {
  if (v === null || v === undefined || v === '') return '';
  if (rIsPrim(v)) return `<div class="rp-txt">${emphasizeMetric(rEsc(v))}</div>`;
  if (Array.isArray(v)) {
    if (v.every(rIsPrim))
      return '<ul class="rp-ul">' + v.map(x => `<li>${emphasizeMetric(rEsc(x))}</li>`).join('') + '</ul>';
    return v.map(x => `<div class="rp-card">${renderVal(x, depth + 1)}</div>`).join('');
  }
  const keys = Object.keys(v).filter(k => k !== '_schema' && k !== 'node_name');
  // optional bold title for card-like objects (trends, drivers, competitors, ...)
  let titleHtml = '', titleKey = null;
  for (let i = 0; i < TITLE_KEYS.length && titleKey === null; i++) {
    const tk = TITLE_KEYS[i];
    if (keys.indexOf(tk) !== -1 && rIsPrim(v[tk]) && v[tk] !== null && v[tk] !== '') {
      titleKey = tk;
      titleHtml = `<div class="rp-seg-name">${emphasizeMetric(rEsc(v[tk]))}</div>`;
    }
  }
  const kv = [];   // short scalars grouped into one key/value block
  let h = '';      // conventions, long prose and nested sections, in JSON order
  keys.forEach(k => {
    if (k === titleKey) return;
    const val = v[k];
    if (val === null || val === undefined || val === '') return;
    const conv = renderByConvention(k, val);
    if (conv !== null) { h += conv; return; }
    if (rIsPrim(val)) {
      if (String(val).length > 140)
        h += `<div class="rp-h3">${rEsc(rKey(k))}</div><div class="rp-txt">${emphasizeMetric(rEsc(val))}</div>`;
      else
        kv.push(`<span class="rp-k">${rEsc(rKey(k))}:</span> ${emphasizeMetric(rEsc(val))}`);
      return;
    }
    h += `<div class="${depth <= 1 ? 'rp-h2' : 'rp-h3'}">${rEsc(rKey(k))}</div>`;
    h += renderVal(val, depth + 1);
  });
  const kvBlock = kv.length ? '<div class="rp-kv">' + kv.join('<br>') + '</div>' : '';
  return titleHtml + kvBlock + h;
}

// Render one not-yet-consumed key inside a section handler (keeps data that a
// handler did not explicitly lay out — nothing is ever dropped).
function renderLeftover(k, val) {
  if (val === null || val === undefined || val === '') return '';
  const conv = renderByConvention(k, val);
  if (conv !== null) return conv;
  if (rIsPrim(val)) {
    if (String(val).length > 140)
      return `<div class="rp-h3">${rEsc(rKey(k))}</div><div class="rp-txt">${emphasizeMetric(rEsc(val))}</div>`;
    return `<div class="rp-kv"><span class="rp-k">${rEsc(rKey(k))}:</span> ${emphasizeMetric(rEsc(val))}</div>`;
  }
  return `<div class="rp-h3">${rEsc(rKey(k))}</div>` + renderVal(val, 2);
}

function renderSection(k, val) { return sectionHead(rKey(k)) + renderVal(val, 1); }

// ---- dedicated section handlers (structurally stable across reports) --------
function renderGlossary(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return renderSection('beginner_glossary', obj);
  let items = '';
  Object.keys(obj).forEach(term => {
    if (!obj[term]) return;
    items += `<details class="rp-acc"><summary>${rEsc(term)}</summary>`
           + `<div class="rp-txt">${emphasizeMetric(rEsc(obj[term]))}</div></details>`;
  });
  return sectionHead('Beginner Glossary') + items;
}

function renderSegment(seg) {
  if (!seg || typeof seg !== 'object' || Array.isArray(seg)) return `<div class="rp-card">${renderVal(seg, 2)}</div>`;
  const name = seg.name || seg.segment || 'Segment';
  const revKey = Object.keys(seg).find(k => /_revenue$/.test(k));   // key spelling varies by report
  const chips = [];
  if (revKey && seg[revKey]) chips.push(seg[revKey]);
  if (seg.growth) chips.push(seg.growth);
  if (seg.share_of_total) chips.push(seg.share_of_total);
  let card = `<div class="rp-card"><div class="rp-seg-name">${rEsc(name)}</div>`;
  if (chips.length)
    card += '<div class="rp-seg-metrics">' + chips.map(c => `<span class="rp-metric">${emphasizeMetric(rEsc(c))}</span>`).join('') + '</div>';
  const used = { name: 1, segment: 1, growth: 1, share_of_total: 1 };
  if (revKey) used[revKey] = 1;
  ['what_it_is', 'within_segment_mix', 'notes'].forEach(k => {
    if (seg[k]) { card += `<div class="rp-txt">${emphasizeMetric(rEsc(seg[k]))}</div>`; used[k] = 1; }
  });
  Object.keys(seg).forEach(k => { if (!used[k] && seg[k]) card += renderLeftover(k, seg[k]); });
  return card + '</div>';
}

function renderRevenue(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return renderSection('revenue_streams', obj);
  let h = sectionHead('Revenue Streams');
  if (obj.note) h += renderNote(obj.note);
  const totKey = Object.keys(obj).find(k => /total_revenue$/.test(k));
  if (totKey && rIsPrim(obj[totKey]))
    h += `<div class="rp-kv"><span class="rp-k">Total revenue:</span> ${emphasizeMetric(rEsc(obj[totKey]))}</div>`;
  if (Array.isArray(obj.segments)) h += renderRevenueChart(obj.segments);   // bar chart, then the detail cards
  if (Array.isArray(obj.segments) && obj.segments.length)
    h += '<div class="rp-seg-grid">' + obj.segments.map(renderSegment).join('') + '</div>';
  const used = { note: 1, segments: 1 };
  if (totKey) used[totKey] = 1;
  Object.keys(obj).forEach(k => { if (!used[k] && obj[k]) h += renderLeftover(k, obj[k]); });
  return h;
}

function renderRisks(arr) {
  if (!Array.isArray(arr)) return renderSection('risks', arr);
  let h = sectionHead('Risks');
  h += renderRiskChart(arr);   // severity distribution, then the detail cards
  arr.forEach(r => {
    if (!r || typeof r !== 'object' || Array.isArray(r)) { h += `<div class="rp-card">${renderVal(r, 2)}</div>`; return; }
    const title = r.risk || r.name || '';
    const sev = r.severity ? sevBadge(r.severity) : '';
    h += '<div class="rp-card"><div class="rp-risk-head">' + sev
       + `<span class="rp-risk-title">${rEsc(title)}</span></div>`;
    if (r.why_it_matters) h += `<div class="rp-txt">${emphasizeMetric(rEsc(r.why_it_matters))}</div>`;
    const used = { risk: 1, name: 1, severity: 1, why_it_matters: 1 };
    Object.keys(r).forEach(k => { if (!used[k] && r[k]) h += renderLeftover(k, r[k]); });
    h += '</div>';
  });
  return h;
}

function renderScenarios(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return renderSection('scenarios', obj);
  let h = sectionHead('Scenarios');
  if (obj.disclaimer) h += renderNote(obj.disclaimer);
  const cases = [['bull_case', 'Bull Case', 'bull'], ['base_case', 'Base Case', 'base'], ['bear_case', 'Bear Case', 'bear']];
  let cols = '';
  cases.forEach(row => {
    const c = obj[row[0]];
    if (!c || typeof c !== 'object') return;
    let inner = `<div class="rp-scen-head">${row[1]}</div>`;
    if (c.thesis) inner += `<div class="rp-txt">${emphasizeMetric(rEsc(c.thesis))}</div>`;
    if (Array.isArray(c.key_drivers) && c.key_drivers.length)
      inner += '<div class="rp-h3">Key Drivers</div><ul class="rp-ul">' + c.key_drivers.map(d => `<li>${emphasizeMetric(rEsc(d))}</li>`).join('') + '</ul>';
    if (c.what_to_watch) inner += `<div class="rp-h3">What To Watch</div><div class="rp-txt">${emphasizeMetric(rEsc(c.what_to_watch))}</div>`;
    const used = { thesis: 1, key_drivers: 1, what_to_watch: 1 };
    Object.keys(c).forEach(k => { if (!used[k] && c[k]) inner += renderLeftover(k, c[k]); });
    cols += `<div class="rp-scen rp-scen-${row[2]}">${inner}</div>`;
  });
  if (cols) h += `<div class="rp-scen-grid">${cols}</div>`;
  const usedTop = { disclaimer: 1, bull_case: 1, base_case: 1, bear_case: 1 };
  Object.keys(obj).forEach(k => { if (!usedTop[k] && obj[k]) h += renderLeftover(k, obj[k]); });
  return h;
}

function renderSummary(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return renderSection('final_research_summary', obj);
  let h = sectionHead('Final Research Summary');
  if (obj.one_paragraph) h += `<div class="rp-lead">${emphasizeMetric(rEsc(obj.one_paragraph))}</div>`;
  if (Array.isArray(obj.what_is_fact) && obj.what_is_fact.length)
    h += '<div class="rp-h3">What Is Fact</div>' + renderAccentList(obj.what_is_fact, 'rp-facts');
  if (Array.isArray(obj.what_is_assumption_or_opinion) && obj.what_is_assumption_or_opinion.length)
    h += '<div class="rp-h3">What Is Assumption / Opinion</div>' + renderAssumptionList(obj.what_is_assumption_or_opinion);
  if (Array.isArray(obj.what_to_watch_next) && obj.what_to_watch_next.length)
    h += '<div class="rp-h3">What To Watch Next</div><ul class="rp-ul">' + obj.what_to_watch_next.map(x => `<li>${emphasizeMetric(rEsc(x))}</li>`).join('') + '</ul>';
  if (obj.no_recommendation_reminder) h += renderNote(obj.no_recommendation_reminder);
  const used = { one_paragraph: 1, what_is_fact: 1, what_is_assumption_or_opinion: 1, what_to_watch_next: 1, no_recommendation_reminder: 1 };
  Object.keys(obj).forEach(k => { if (!used[k] && obj[k]) h += renderLeftover(k, obj[k]); });
  return h;
}

function renderMeta(meta) {
  if (!meta || typeof meta !== 'object') return '';
  const m = Object.assign({}, meta);
  delete m.title;        // shown in the masthead instead
  delete m.report_date;  // shown in the masthead instead
  return renderSection('about_this_report', m);
}

// Report header: logo chip + "Equity Research" eyebrow + company + ticker/exchange/date.
function reportMasthead(rep, node) {
  const name = rEsc((rep && rep.company) || (node && node.id) || 'Company');
  let chip = '';
  if (node && node.logo)
    chip = `<span class="logochip ${node.logoBg || 'light'}"><img src="${rEsc(node.logo)}" alt=""></span>`;
  const ticker = (rep && rep.ticker) || (node && node.ticker);
  const exch = (rep && rep.exchange) || (node && node.exchange);
  const date = rep && rep.report_meta && rep.report_meta.report_date;
  const web = rep && rep.website;
  let meta = '';
  if (ticker) meta += `<span class="ticker">${rEsc(ticker)}</span>`;
  if (exch) meta += `<span class="exchange">${rEsc(exch)}</span>`;
  if (date) meta += `<span class="rp-date">${rEsc(date)}</span>`;
  if (web && /^https?:/i.test(web))
    meta += `<a class="rp-date" href="${rEsc(web)}" target="_blank" rel="noopener">${rEsc(String(web).replace(/^https?:\/\//, ''))}</a>`;
  return `<div class="rp-mast">${chip}<div class="rp-mast-body">`
       + '<div class="rp-eyebrow">Equity Research</div>'
       + `<div class="rp-h1">${name}</div>`
       + `<div class="rp-mast-meta">${meta}</div></div></div>`;
}

// section name -> dedicated handler; sections without one use the generic renderer.
const SECTION_HANDLERS = {
  beginner_glossary: renderGlossary,
  revenue_streams: renderRevenue,
  risks: renderRisks,
  scenarios: renderScenarios,
  final_research_summary: renderSummary
};
const MAST_KEYS = { company: 1, node_name: 1, ticker: 1, exchange: 1, website: 1 };

function renderReport(rep, withTitle, node, opts) {
  // Plain-string reports (from reports.json) are shown as-is with line breaks kept.
  if (typeof rep === 'string')
    return `<div class="rp-txt" style="white-space:pre-wrap">${rEsc(rep)}</div>`;
  // Structured reports: a thin accent bar, a masthead, then every top-level section in
  // JSON order — a dedicated handler when one exists, else the generic section renderer.
  let h = '<div class="rp-accent"></div>' + reportMasthead(rep, node);
  if (rep.live) h += renderLiveQuote(rep.live, opts);   // live price card + interactive chart (server-injected)
  Object.keys(rep).forEach(k => {
    if (MAST_KEYS[k] || k === 'live') return;   // masthead / live-quote card shown above
    const val = rep[k];
    if (val === null || val === undefined || val === '') return;
    if (k === 'report_meta') { h += renderMeta(val); return; }
    const handler = SECTION_HANDLERS[k];
    h += handler ? handler(val) : renderSection(k, val);
  });
  return h;
}

// Open a clean, light-themed print view of the report in a new tab and trigger
// the browser print dialog → "Save as PDF" gives a crisp, brokerage-style PDF
// from the SAME report JSON (no server/library needed).
const PDF_CSS = `
  * { box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  body { font-family:Georgia,'Times New Roman',serif; color:#1a1a1a; background:#fff;
         margin:0; padding:34px 44px; line-height:1.5; font-size:11.5pt; }
  .pdf-head { border-bottom:3px solid #1f3a5f; padding-bottom:12px; margin-bottom:20px; }
  .pdf-eyebrow { font-size:9pt; letter-spacing:.18em; color:#1f6feb; font-weight:700;
                 font-family:Arial,Helvetica,sans-serif; }
  .pdf-title { font-size:20pt; font-weight:800; color:#10243f; margin-top:4px; }
  .pdf-sub { color:#555; font-size:10pt; margin-top:6px; }
  .pdf-foot { margin-top:26px; padding-top:10px; border-top:1px solid #cdd6e0;
              color:#777; font-size:8.5pt; font-style:italic; }
  .rp-h1 { font-size:16pt; font-weight:800; color:#10243f; margin:4px 0 10px; }
  .rp-h2 { font-size:12pt; font-weight:800; color:#1f3a5f; text-transform:uppercase;
           letter-spacing:.04em; margin:18px 0 6px; border-bottom:1px solid #cdd6e0;
           padding-bottom:4px; page-break-after:avoid; }
  .rp-h3 { font-size:11pt; font-weight:700; color:#333; margin:11px 0 3px; page-break-after:avoid; }
  .rp-txt { margin:4px 0; }
  .rp-ul { margin:5px 0 9px 22px; } .rp-ul li { margin:3px 0; }
  .rp-card { border:1px solid #d8dee4; border-radius:5px; padding:9px 12px; margin:8px 0;
             background:#f7f9fb; page-break-inside:avoid; }
  .rp-kv { margin:3px 0; } .rp-k { font-weight:700; color:#444; }
  /* report v2 — light mirror of the new rp-* classes (keep in sync with the dark <style> block). */
  .rp-mast { display:flex; gap:14px; align-items:center; border-bottom:3px solid #1f3a5f; padding-bottom:12px; margin-bottom:18px; }
  .rp-mast-body { min-width:0; }
  .rp-eyebrow { font-size:9pt; letter-spacing:.18em; color:#1f6feb; font-weight:700; font-family:Arial,Helvetica,sans-serif; }
  .rp-mast-meta { display:flex; gap:10px; flex-wrap:wrap; margin-top:4px; align-items:center; }
  .rp-date { color:#555; font-size:10pt; text-decoration:none; }
  .ticker { font-family:Arial,Helvetica,sans-serif; font-weight:700; color:#1f6feb; font-size:11pt; }
  .exchange { color:#777; font-size:9pt; }
  .logochip { display:inline-flex; align-items:center; justify-content:center; width:104px; height:48px; padding:4px 8px; border:1px solid #d8dee4; border-radius:8px; background:#fff; flex:0 0 auto; }
  .logochip img { max-width:100%; max-height:100%; object-fit:contain; }
  .rp-lead { font-size:12pt; line-height:1.6; margin:6px 0 10px; color:#10243f; }
  .rp-note { color:#666; font-style:italic; font-size:10pt; margin:6px 0; }
  .rp-note-acc { font-size:10pt; color:#666; margin:6px 0; } .rp-note-acc summary { cursor:pointer; font-style:italic; }
  .rp-callout { background:#eef4fb; border-left:3px solid #1f6feb; padding:8px 12px; margin:8px 0; page-break-inside:avoid; }
  .rp-callout-h { font-size:9pt; font-weight:700; color:#1f3a5f; text-transform:uppercase; letter-spacing:.05em; margin-bottom:3px; }
  .rp-cite { font-size:9pt; color:#777; margin:3px 0 6px; }
  .rp-money { color:#0a7d33; font-weight:700; } .rp-pct { color:#10243f; font-weight:700; }
  .rp-facts, .rp-asm { list-style:none; margin:4px 0 8px; padding:0; }
  .rp-facts li { border-left:3px solid #0a7d33; padding:2px 0 2px 9px; margin:4px 0; }
  .rp-asm li { border-left:3px solid #b8860b; padding:2px 0 2px 9px; margin:4px 0; }
  .rp-asm-tag { color:#b8860b; font-weight:700; }
  .rp-acc { border:1px solid #d8dee4; border-radius:5px; margin:5px 0; background:#f7f9fb; page-break-inside:avoid; }
  .rp-acc summary { cursor:pointer; padding:7px 11px; font-weight:700; font-size:11pt; }
  .rp-acc > .rp-txt { padding:0 11px 9px; }
  .rp-seg-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .rp-seg-name { font-weight:700; font-size:11.5pt; margin-bottom:4px; }
  .rp-seg-metrics { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:5px; }
  .rp-metric { background:#fff; border:1px solid #d8dee4; border-radius:4px; padding:2px 7px; font-size:9.5pt; }
  .rp-risk-head { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
  .rp-risk-title { font-weight:700; }
  .rp-sev { display:inline-block; padding:2px 8px; border-radius:10px; font-size:8pt; font-weight:700; background:#fff; border:1px solid #888; color:#555; text-transform:uppercase; }
  .rp-sev-very-high, .rp-sev-high { color:#c5221f; border-color:#c5221f; }
  .rp-sev-medium { color:#b8860b; border-color:#b8860b; }
  .rp-sev-low { color:#0a7d33; border-color:#0a7d33; }
  .rp-scen-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  .rp-scen { border:1px solid #d8dee4; border-top:3px solid #888; border-radius:5px; padding:9px 11px; background:#f7f9fb; page-break-inside:avoid; }
  .rp-scen-bull { border-top-color:#0a7d33; } .rp-scen-base { border-top-color:#1f6feb; } .rp-scen-bear { border-top-color:#c5221f; }
  .rp-scen-head { font-weight:800; font-size:11.5pt; margin-bottom:4px; }
  .rp-src { margin:4px 0 8px; padding-left:18px; font-size:10pt; }
  .rp-src a { color:#1f6feb; text-decoration:none; } .rp-src-date { color:#888; font-size:8.5pt; }
  .rp-accent { height:3px; border-radius:3px; margin:0 0 12px; background:linear-gradient(90deg,#1f6feb,#7c3aed,#0a7d33); }
  .rp-chart { background:#f7f9fb; border:1px solid #d8dee4; border-radius:6px; padding:10px 12px; margin:8px 0 11px; page-break-inside:avoid; }
  .rp-chart-title { font-size:9pt; font-weight:700; color:#555; text-transform:uppercase; letter-spacing:.05em; margin-bottom:8px; }
  .rp-bar-row { display:flex; align-items:center; gap:9px; margin:5px 0; }
  .rp-bar-label { flex:0 0 36%; font-size:9.5pt; color:#333; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .rp-bar-track { flex:1; background:#e7ecf1; border-radius:4px; height:15px; overflow:hidden; }
  .rp-bar-fill { height:100%; border-radius:4px; min-width:2px; }
  .rp-bar-val { flex:0 0 auto; font-size:9pt; color:#10243f; font-weight:700; font-family:Arial,Helvetica,sans-serif; }
  .rp-stack { display:flex; height:17px; border-radius:5px; overflow:hidden; margin:2px 0 9px; background:#e7ecf1; }
  .rp-stack-seg { height:100%; }
  .rp-legend { display:flex; flex-wrap:wrap; gap:14px; font-size:9pt; color:#333; }
  .rp-legend-item { display:flex; align-items:center; gap:5px; }
  .rp-legend-dot { width:9px; height:9px; border-radius:2px; display:inline-block; }
  .rp-quote { background:#f7f9fb; border:1px solid #d8dee4; border-radius:8px; padding:12px 14px; margin:4px 0 14px; page-break-inside:avoid; }
  .rp-q-top { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  .rp-q-price { font-size:20pt; font-weight:800; color:#10243f; font-family:Arial,Helvetica,sans-serif; }
  .rp-q-chg { font-size:12pt; font-weight:700; }
  .rp-q-chg.up { color:#0a7d33; } .rp-q-chg.down { color:#c5221f; }
  .rp-q-live { margin-left:auto; font-size:8pt; font-weight:700; color:#777; }
  .rp-q-stats { display:flex; flex-wrap:wrap; gap:18px; margin:8px 0 2px; font-size:10pt; color:#333; }
  .rp-q-lbl { color:#777; font-weight:700; margin-right:5px; }
  .rp-spark { width:100%; height:110px; display:block; margin:0; }
  .rp-range { display:flex; gap:4px; margin:8px 0 4px; }
  .rp-rbtn { background:#fff; border:1px solid #d8dee4; color:#555; font:700 9pt Arial,sans-serif;
             padding:2px 8px; border-radius:5px; }
  .rp-rbtn.active { background:#1f6feb; border-color:#1f6feb; color:#fff; }
  .rp-read { display:flex; align-items:baseline; gap:10px; min-height:16px; margin:2px 0 4px; }
  .rp-rd-price { font:700 11pt Arial,sans-serif; color:#10243f; }
  .rp-rd-meta { font:9pt Arial,sans-serif; color:#777; }
  .rp-cwrap { position:relative; width:100%; }
  .rp-cross, .rp-dot, .rp-hit { display:none; }
  @page { margin:16mm 14mm; }
`;

function openReportPdf(node) {
  if (!node.report) return;
  // Logo is a base64 data URI (self-contained) so it loads as-is in the blank print
  // window; only a legacy "/path" form would need the origin prepended.
  const pnode = Object.assign({}, node, { logo: (node.logo && node.logo.charAt(0) === '/') ? (location.origin + node.logo) : node.logo });
  const body = renderReport(node.report, true, pnode, { pdf: true });   // masthead is rendered inside the report
  const html = '<!doctype html><html><head><meta charset="utf-8"><title>'
    + rEsc(node.id) + ' — Stock Report</title><style>' + PDF_CSS + '</style></head><body>'
    + body
    + '<div class="pdf-foot">Generated from this app for educational use — not investment advice.</div>'
    + '</body></html>';
  const w = window.open('', '_blank');
  if (!w) { alert('Allow pop-ups for this page to download the PDF.'); return; }
  w.document.open(); w.document.write(html); w.document.close();
  w.focus();
  setTimeout(function () { try { w.print(); } catch (e) {} }, 450);
}

function showPanel(node) {
  const outLinks = GDATA.links.filter(l => (l.source.id || l.source) === node.id);
  let b = '';

  const FLAG = { US:'🇺🇸', TW:'🇹🇼', KR:'🇰🇷', JP:'🇯🇵', NL:'🇳🇱', DE:'🇩🇪', CN:'🇨🇳', CA:'🇨🇦', ID:'🇮🇩', PH:'🇵🇭' };
  b += '<div class="meta">';
  if (node.status === 'private') {
    b += `<span class="private-tag">Private</span>`;
  } else if (node.ticker) {
    b += `<span class="ticker">${node.ticker}</span>`;
    if (node.exchange) b += `<span class="exchange">${node.exchange}</span>`;
  }
  if (node.country) b += `<span class="country" title="${node.country}">${FLAG[node.country] || node.country}</span>`;
  if (node.lastData) {
    b += `<span class="private-tag" style="${node.stale ? 'color:#f85149' : ''}">last data ${node.lastData}${node.stale ? ' · stale' : ''}</span>`;
  } else {
    b += `<span class="private-tag" style="color:#f85149">no signals yet</span>`;
  }
  b += '</div>';

  // Stock Report button (toggles inline report) + Download PDF button (print view).
  // The PDF button only appears when this company actually has a report.
  b += '<div class="repwrap"><button class="repbtn" id="repbtn">📊 Stock Report</button>'
     + (node.report ? '<button class="repbtn repbtn-pdf" id="reppdf">📄 Download PDF</button>' : '')
     + '<div class="repbox" id="repbox"></div></div>';

  // Status badges (supply tight / guidance raised / LTA / capacity expanding)
  const sigsRaw = node.quarterly_data || [];
  const statusBadges = buildBadges(sigsRaw);
  if (statusBadges.length) {
    b += '<div style="margin-bottom:8px">';
    statusBadges.forEach(r =>
      b += `<span class="sbadge" style="border-color:${r.color}; color:${r.color}">${r.label}</span>`
    );
    b += '</div>';
  }

  b += '<div style="margin-bottom:8px">';
  // layer badges first (filled), then domain badges — both via the merged GCOLORS/GNAMES maps
  [...(node.layers || []), ...(node.domains || [])].forEach(s =>
    b += `<span class="badge" style="background:${GCOLORS[s] || '#94a3b8'}">${GNAMES[s] || s}</span>`
  );
  b += '</div>';

  b += '<div style="margin-bottom:8px">';
  (node.chains || []).forEach(c =>
    b += `<span class="cbadge" style="border-color:${CCOLORS[c] || '#8b949e'}">${c.replace(/_/g,' ')}</span>`
  );
  b += '</div>';

  if ((node.products || []).length) {
    b += '<div class="sec">Products</div>';
    node.products.forEach(p =>
      b += `<div class="card"><span class="cbadge" style="border-color:${CCOLORS[p.chain]||'#8b949e'}">${p.chain.replace(/_/g,' ')}</span> ${p.product}</div>`
    );
  }

  // Two-column body: left = timeline + signals, right = deal board.
  let col1 = '', col2 = '';

  // Product / capacity timeline — date-bearing sentences, chronological
  const tl = buildTimeline(sigsRaw);
  if (tl.length) {
    col1 += '<div class="sec">Product / Capacity Timeline</div>';
    tl.forEach(it =>
      col1 += `<div class="tlrow"><span class="tlwhen">${it.when}</span><span class="tltext">${it.text}</span></div>`
    );
  }

  // Signals: newest-first, render the first 8, hide the rest behind a "show more"
  // toggle. All signals stay in the data — this only controls display order/volume
  // (hub nodes like NVIDIA carry 60+ signals and are unreadable otherwise).
  const sigs = sigsRaw.slice().sort((a, b2) => sigDate(b2.quarter) - sigDate(a.quarter));
  if (sigs.length) {
    col1 += '<div class="sec">Signals</div><div id="sigwrap">';
    sigs.forEach((q, i) =>
      col1 += `<div class="card${i >= 8 ? ' sig-hidden' : ''}"><div class="qtr">${q.quarter}</div>${q.signal}<div class="fig">${q.figure}</div></div>`
    );
    if (sigs.length > 8)
      col1 += `<button class="morebtn" onclick="this.parentNode.querySelectorAll('.sig-hidden').forEach(e=>e.classList.remove('sig-hidden'));this.remove();">Show ${sigs.length - 8} more</button>`;
    col1 += '</div>';
  }

  // Deal board — both directions. The merged graph keeps one edge PER CHAIN,
  // so the same counterparty can appear many times; integrate by company:
  // one card per counterparty, distinct relationships merged, contracts deduped.
  function groupByCompany(list, nameOf) {
    const map = new Map();
    list.forEach(e => {
      const k = nameOf(e);
      if (!map.has(k)) map.set(k, { name: k, rels: [], relSeen: new Set(), contracts: [], cSeen: new Set() });
      const g = map.get(k);
      const rel = e.relationship || '';
      if (rel && !g.relSeen.has(rel)) { g.relSeen.add(rel); g.rels.push(rel); }
      (e.contracts || []).forEach(c => {
        const ck = (c.signal || '').slice(0, 80);
        if (!g.cSeen.has(ck)) { g.cSeen.add(ck); g.contracts.push(c); }
      });
    });
    return [...map.values()];
  }

  function renderGroup(g) {
    let h = `<div class="card"><b>${g.name}</b>`;
    g.rels.slice(0, 3).forEach(r => h += `<span class="rel">${r}</span>`);
    if (g.rels.length > 3) h += `<span class="rel" style="color:#6e7681">+${g.rels.length - 3} more roles</span>`;
    g.contracts.forEach(c => {
      const extras = [c.units, c.value].filter(v => v && v !== 'no specific figure').join(' \xB7 ');
      h += `<div class="ctract">${c.signal}${extras ? `<span class="cv">  ${extras}</span>` : ''}</div>`;
    });
    return h + '</div>';
  }

  const customers = groupByCompany(outLinks, e => e.target.id || e.target);
  if (customers.length) {
    // Counterparties with contract detail first
    customers.sort((a, b2) => b2.contracts.length - a.contracts.length);
    col2 += '<div class="sec">Customers &#8594;</div>';
    customers.forEach(g => col2 += renderGroup(g));
  }

  const inc = node.incoming || [];
  if (inc.length) {
    const suppliers = groupByCompany(inc, e => e.source);
    const withC = suppliers.filter(g => g.contracts.length);
    const plain = suppliers.filter(g => !g.contracts.length);
    col2 += '<div class="sec">&#8592; Suppliers</div>';
    withC.sort((a, b2) => b2.contracts.length - a.contracts.length);
    withC.forEach(g => col2 += renderGroup(g));
    if (plain.length) {
      const names = plain.map(g => g.name);
      const head = names.slice(0, 18).join(', ');
      col2 += `<div class="card" style="color:#8b949e">${head}${names.length > 18 ? ` +${names.length - 18} more` : ''}</div>`;
    }
  }

  b += `<div class="pgrid"><div class="pcol">${col1}</div><div class="pcol">${col2}</div></div>`;

  focusLogoId = node.id;   // keep this node's logo visible while its panel is open
  const titleEl = document.getElementById('ptitle');
  titleEl.textContent = '';
  if (node.logo) {
    const chip = document.createElement('span');
    chip.className = 'logochip ' + (node.logoBg || 'light');
    const img = document.createElement('img');
    img.src = node.logo;
    img.alt = '';
    img.onerror = () => chip.remove();
    chip.appendChild(img);
    titleEl.appendChild(chip);
  }
  titleEl.appendChild(document.createTextNode(node.id));
  document.getElementById('pbody').innerHTML = b;
  document.getElementById('panel').style.display = 'block';

  // Stock Report toggle: show this company's report (from reports.json) or a placeholder.
  const repBtn = document.getElementById('repbtn');
  const repBox = document.getElementById('repbox');
  if (repBtn) repBtn.onclick = () => {
    if (repBox.style.display === 'block') { repBox.style.display = 'none'; return; }
    if (node.report) {
      repBox.classList.remove('repempty');
      repBox.innerHTML = renderReport(node.report, true, node);
    } else {
      repBox.classList.add('repempty');
      repBox.textContent = 'No stock report for this company yet.';
    }
    repBox.style.display = 'block';
  };
  const repPdf = document.getElementById('reppdf');
  if (repPdf) repPdf.onclick = () => openReportPdf(node);
}

// Streamlit mounts this iframe inside a HIDDEN tab panel on first load (0x0 size).
// If the WebGL graph is created while hidden, the camera controls are born with a
// broken screen-rect and rotate/right-click-pan never recover (only zoom works).
// So: DEFER the entire graph initialization until the container actually has size
// — that way renderer, camera and controls all start from correct dimensions.
const gEl = document.getElementById('graph');
let Graph = null;
// Which node's logo is force-shown regardless of zoom (hover + clicked node).
let hoverLogoId = null, focusLogoId = null;

function initGraph() {
  Graph = ForceGraph3D()(gEl)
    .backgroundColor('#0d1117')
    .graphData(GDATA)
    .nodeLabel('hover')
    .nodeColor(n => n.color)
    .nodeVal(n => n.val)
    .nodeOpacity(0.9)
    .onNodeClick(n => showPanel(n))
    .onNodeHover(n => { hoverLogoId = n ? n.id : null; })
    .onBackgroundClick(() => { document.getElementById('panel').style.display = 'none'; focusLogoId = null; })
    .linkColor(l => l.color)
    .linkOpacity(0.2)
    .linkWidth(l => (l.contracts && l.contracts.length) ? 1.5 : 0.5)
    .linkDirectionalArrowLength(4)
    .linkDirectionalArrowRelPos(1)
    .linkDirectionalArrowColor(l => l.color)
    .linkDirectionalParticles(l => (l.contracts && l.contracts.length) ? 2 : 0)
    .linkDirectionalParticleSpeed(0.005)
    .linkDirectionalParticleColor(l => l.color);

  Graph.d3Force('charge').strength(-400);
  Graph.d3Force('link').distance(150);

  // Touch devices: damp the camera controls so a small swipe doesn't fling the graph.
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
    const c = Graph.controls();
    c.rotateSpeed = 0.35;
    c.zoomSpeed   = 0.5;
    c.panSpeed    = 0.25;
  }

  if (FOCUS) {
    setTimeout(() => {
      const node = GDATA.nodes.find(n => n.id === FOCUS);
      if (node) {
        Graph.cameraPosition({ x: (node.x||0) + 80, y: (node.y||0), z: (node.z||0) + 80 }, node, 1500);
        setTimeout(() => showPanel(node), 1600);
      }
    }, 3500);
  }

  // Logo badges centered ON each logo'd node. Every frame: project the node to
  // screen coords and compute the sphere's APPARENT radius (world radius =
  // nodeRelSize 4 * cbrt(val), projected through the camera) so the badge scales
  // 1:1 with the sphere as you zoom. LEVEL-OF-DETAIL: a badge only shows once the
  // sphere is big enough on screen to be legible (MIN_R px) — so at default zoom
  // only the big hubs carry logos, and zooming into a cluster resolves the rest
  // in. The hovered node and the clicked (panel-open) node always show, at a
  // readable minimum size, regardless of zoom.
  const MIN_R = 9;          // sphere on-screen radius (px) below which logos hide
  const logoLayer = document.createElement('div');
  logoLayer.id = 'nodelogos';
  document.body.appendChild(logoLayer);
  const logoNodes = [];
  GDATA.nodes.forEach(n => {
    if (!n.logo) return;
    const chip = document.createElement('div');
    chip.className = 'nlogo' + (n.logoBg === 'dark' ? ' dk' : '');
    const img = document.createElement('img');
    img.src = n.logo;
    img.alt = '';
    chip.appendChild(img);
    logoLayer.appendChild(chip);
    const o = { n, chip, img, rWorld: 4 * Math.cbrt(n.val) };
    img.onerror = () => { chip.remove(); o._dead = true; };  // hide if file 404s
    logoNodes.push(o);
  });
  if (logoNodes.length) (function logoTick() {
    const cam = Graph.camera();
    const halfH = gEl.clientHeight / 2;
    const perPx = halfH / Math.tan((cam.fov / 2) * Math.PI / 180);  // world->px at d=1
    logoNodes.forEach(o => {
      if (o._dead) return;
      const n = o.n;
      if (n.x === undefined) { o.chip.style.display = 'none'; return; }
      const p = Graph.graph2ScreenCoords(n.x, n.y, n.z);
      if (p.x < -80 || p.y < -80 || p.x > window.innerWidth + 80 || p.y > window.innerHeight + 80) {
        o.chip.style.display = 'none'; return;
      }
      const c = cam.position;
      const d = Math.hypot(c.x - n.x, c.y - n.y, c.z - n.z);
      const rPx = o.rWorld * perPx / d;            // sphere's on-screen radius
      const forced = (n.id === hoverLogoId || n.id === focusLogoId);
      if (rPx < MIN_R && !forced) { o.chip.style.display = 'none'; return; }
      let w = Math.min(rPx * 1.8, 240);            // badge width ~ sphere diameter
      if (forced) w = Math.max(w, 40);             // hovered/clicked: always readable
      o.img.style.width = w + 'px';
      o.chip.style.padding = (w * 0.07) + 'px ' + (w * 0.11) + 'px';
      o.chip.style.left = p.x + 'px';
      o.chip.style.top = p.y + 'px';
      o.chip.style.zIndex = forced ? 6 : 5;
      o.chip.style.display = 'block';
    });
    requestAnimationFrame(logoTick);
  })();
}

// Visibility helpers. Streamlit hides inactive tab panels in ways that can fool
// a plain clientWidth check (visibility:hidden keeps layout; display:none kills
// it), so "really visible" = has layout AND has an offsetParent AND non-zero size.
function reallyVisible() {
  return gEl.offsetParent !== null && gEl.clientWidth > 0 && gEl.clientHeight > 0;
}

// Re-fit the canvas + camera controls to the container (safe to call repeatedly).
let _gw = 0, _gh = 0;
function fitGraph(force) {
  if (!Graph) return;
  const w = gEl.clientWidth, h = gEl.clientHeight;
  if (w > 0 && h > 0 && (force || Math.abs(w - _gw) > 2 || Math.abs(h - _gh) > 2)) {
    _gw = w; _gh = h;
    Graph.width(w);
    Graph.height(h);
    const c = Graph.controls();
    if (c && typeof c.handleResize === 'function') c.handleResize();
  }
}

// Boot ONLY when the tab is truly visible; afterwards, every time the panel
// becomes visible again (tab switch back), kick a re-fit so the canvas can
// never stay blank. IntersectionObserver fires on real visibility changes;
// the poll is a fallback for browsers/embeds where IO doesn't fire.
function bootOrKick() {
  if (!reallyVisible()) return;
  if (!Graph) initGraph();
  fitGraph(true);
}
if (window.IntersectionObserver) {
  new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting)) bootOrKick();
  }).observe(gEl);
}
setInterval(() => { if (!Graph) bootOrKick(); }, 250);

// Keep the canvas matched to the container on real size changes
// (window resize, sidebar open/close) — guarded so it never loops.
if (window.ResizeObserver) new ResizeObserver(() => fitGraph(false)).observe(gEl);
</script>
</body>
</html>"""

# ── 2D chain-view template (simple per-chain tier map, no 3D) ─────────────────
# Tiers = columns in curated flow order, companies = pills, edges = bezier paths.
# Solid edge = has contract data, dashed = skeleton structure only.
# Hover a pill → its suppliers/customers stay lit, everything else dims.
# ── 2D chain-view template: fixed tier columns + ripple highlighting ─────────
# Tiers = columns in curated flow order, companies = pills, edges = bezier paths.
# Solid edge = has contract data, dashed = skeleton structure only.
# Hover = direct neighbors; CLICK = ripple (full downstream amber / upstream blue).
CHAIN2D_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  body { margin:0; background:#0b0e13; font-family:-apple-system,'Segoe UI',Roboto,sans-serif; }
  #wrap { overflow:auto; }
  .pill { cursor:pointer; }
  .pill rect { fill:#141a23; }
  .pill text { fill:#e5e7eb; font-size:11.5px; }
  .hdr { font-size:12px; font-weight:700; letter-spacing:.4px; }
  .cnt { font-size:10px; fill:#64748b; }
  .edge { fill:none; }
  .dim { opacity:0.08; transition:opacity .12s; }
  .rself rect { stroke:#ffffff !important; stroke-width:2.4 !important; }
  .rdown rect { stroke:#fbbf24 !important; stroke-width:2 !important; }
  .rup   rect { stroke:#60a5fa !important; stroke-width:2 !important; }
  .edown { stroke:#fbbf24 !important; opacity:1 !important; }
  .eup   { stroke:#60a5fa !important; opacity:0.95 !important; }
  #tip { position:fixed; display:none; background:#1c2430; color:#e5e7eb; border:1px solid #334155;
         border-radius:6px; padding:6px 9px; font-size:11.5px; max-width:300px; pointer-events:none;
         z-index:10; line-height:1.45; }
  /* edge-detail panel: opens when an edge (or two connected companies) is selected */
  #epanel { position:fixed; top:10px; right:10px; width:360px; max-width:46vw; max-height:86%;
            overflow:auto; background:#11161f; color:#e5e7eb; border:1px solid #334155;
            border-radius:9px; padding:10px 12px; font-size:12px; z-index:20; display:none;
            box-shadow:0 8px 30px rgba(0,0,0,.5); line-height:1.5; }
  .ep-h { display:flex; justify-content:space-between; align-items:center; font-size:13px; margin-bottom:4px; }
  .ep-x { cursor:pointer; color:#94a3b8; font-size:18px; line-height:1; padding:0 4px; }
  .ep-x:hover { color:#e5e7eb; }
  .ep-rel { color:#9aa6b2; font-size:11.5px; margin-bottom:8px; }
  .ep-n { color:#7dd3fc; font-size:11px; margin-bottom:4px; }
  .ep-c { border-top:1px solid #1f2937; padding:7px 0; }
  .ep-src { color:#fbbf24; font-size:11px; font-weight:600; }
  .ep-sig { margin:2px 0; }
  .ep-meta { color:#7dd3fc; font-size:11px; }
  .ep-empty { color:#64748b; font-style:italic; }
  .esel { stroke:#34d399 !important; stroke-width:3 !important; opacity:1 !important; stroke-dasharray:none !important; }
  .epin rect { stroke:#34d399 !important; stroke-width:2.6 !important; }
  .epin { opacity:1 !important; }
</style></head><body>
<div id="wrap"><svg id="sv"></svg></div><div id="tip"></div><div id="epanel"></div>
<script>
const DATA = __CHAIN2D_DATA__;
const NS = 'http://www.w3.org/2000/svg';

// ── flatten into node/edge lists keyed by "colIdx|playerIdx" ─────────────────
// Each column is a LAYER (or domain); `row` is the player's visual slot in that
// column (accounting for sector sub-header rows), while `j` stays the flat player
// index so the edge model is still (column, playerIndex). `color` rides on the column.
const nodes = [], idx = {};
DATA.columns.forEach((col, ci) => col.players.forEach((p, pi) => {
  const k = ci + '|' + pi;
  const n = { k, ti: ci, j: pi, row: p.row, color: col.color, c: p.c, p: p.p, qd: p.qd, ext: p.ext || 0 };
  nodes.push(n); idx[k] = n;
}));
const edges = DATA.edges.map(e => ({ s: e.ci + '|' + e.pi, t: e.cj + '|' + e.pj, rel: e.rel, nc: e.nc, cn: e.contracts || [] }));
const outs = {}, ins = {};
edges.forEach((e, i) => {
  (outs[e.s] = outs[e.s] || []).push(i);
  (ins[e.t]  = ins[e.t]  || []).push(i);
});

// ── geometry: TWO regions side-by-side. LEFT = the main 13-layer stack (+ external),
// each layer a horizontal BAND stacked top→bottom, companies flowing left→right and
// wrapping. RIGHT = a narrower panel holding the cross-cutting DOMAIN bands (power/
// thermal/security/edge_ai) BESIDE the stack — each domain a band with a header line.
const GUT = 140, padX = 14, padT = 8, pillW = 150, pillH = 26;
const gapX = 10, gapY = 10, secH = 14, rowGap = 6, hdrH = 18, divW = 18;
const isDomain = col => col.kind === 'domain';
const hasDom = DATA.columns.some(isDomain);
const totalW = Math.max(900, window.innerWidth - 24);
// right panel sized to fit `rightCols` pills per row; 0 when the chain has no domains
const rightCols = 3;
const RW = hasDom ? (rightCols * (pillW + gapX) - gapX + 2 * padX) : 0;
const DIV = hasDom ? divW : 0;
const leftW = totalW - RW - DIV;
const leftPerRow  = Math.max(1, Math.floor((leftW - GUT - 2 * padX + gapX) / (pillW + gapX)));
const rightPerRow = Math.max(1, Math.floor((RW - 2 * padX + gapX) / (pillW + gapX)));
const rightX0 = leftW + DIV + padX;
// walk LEFT bands and RIGHT bands with independent running tops (side-by-side regions)
let topL = padT, topR = padT;
DATA.columns.forEach(col => {
  const dom = isDomain(col);
  col._dom = dom;
  col._perRow = dom ? rightPerRow : leftPerRow;
  const np = col.players.length;
  const rows = np === 0 ? 0 : Math.ceil(np / col._perRow);
  col._hasSec = (col.headers || []).some(h => !h.sub);   // has a real (non-sub) sector header
  col._stripH = (col._hasSec && np > 0) ? secH : 0;       // thin sector-label strip
  col._hdrH = dom ? hdrH : 0;                             // domains show a header line above pills
  col._x0 = dom ? rightX0 : (GUT + padX);
  if (dom) { col._top = topR; col._pillTop = topR + col._hdrH + col._stripH; }
  else     { col._top = topL; col._pillTop = topL + col._stripH; }
  const bandH = col._hdrH + col._stripH + Math.max(1, rows) * pillH + Math.max(0, rows - 1) * rowGap;
  if (dom) topR += bandH + gapY; else topL += bandH + gapY;
});
const W = totalW + 10;
const H = Math.max(topL, topR) + 8;
const sv = document.getElementById('sv');
sv.setAttribute('width', W); sv.setAttribute('height', H);
// place each pill within its band's region: `j` is the gap-free index (NOT `row`,
// which leaves holes for sector header rows). cc = column in band, rr = wrapped row.
nodes.forEach(n => {
  const col = DATA.columns[n.ti];
  const s = n.j, rr = Math.floor(s / col._perRow), cc = s % col._perRow;
  n.x = col._x0 + cc * (pillW + gapX);
  n.y = col._pillTop + rr * (pillH + rowGap);
});

function esc(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
const tipEl = document.getElementById('tip');
function tip(ev, html) {
  tipEl.innerHTML = html; tipEl.style.display = 'block';
  tipEl.style.left = Math.min(ev.clientX + 14, window.innerWidth - 310) + 'px';
  tipEl.style.top  = (ev.clientY + 12) + 'px';
}
function hideTip() { tipEl.style.display = 'none'; }

// ── edges (drawn first so pills sit on top) ──────────────────────────────────
const gE = document.createElementNS(NS, 'g'); sv.appendChild(gE);
const edgeEls = [];
edges.forEach((e, i) => {
  const a = idx[e.s], b = idx[e.t];
  // edges flow VERTICALLY within the layer stack (down to a lower band / up to an upper
  // one); a CROSS-REGION edge (layer ↔ domain panel) instead flows sideways; same band
  // arcs out the side.
  const ar = DATA.columns[a.ti]._dom, br = DATA.columns[b.ti]._dom;
  const cxa = a.x + pillW / 2, cxb = b.x + pillW / 2;
  let d;
  if (ar !== br) {                 // CROSS-REGION (layer ↔ domain): connect sideways
    const ax = ar ? a.x : a.x + pillW, bx = br ? b.x : b.x + pillW;
    const ya = a.y + pillH / 2, yb = b.y + pillH / 2, mx = (ax + bx) / 2;
    d = `M ${ax} ${ya} C ${mx} ${ya}, ${mx} ${yb}, ${bx} ${yb}`;
  } else if (b.ti > a.ti) {        // DOWN: a bottom-center → b top-center
    const y1 = a.y + pillH, y2 = b.y, mid = (y1 + y2) / 2;
    d = `M ${cxa} ${y1} C ${cxa} ${mid}, ${cxb} ${mid}, ${cxb} ${y2}`;
  } else if (b.ti < a.ti) {        // UP: a top-center → b bottom-center
    const y1 = a.y, y2 = b.y + pillH, mid = (y1 + y2) / 2;
    d = `M ${cxa} ${y1} C ${cxa} ${mid}, ${cxb} ${mid}, ${cxb} ${y2}`;
  } else {                         // SAME band: arc out the right side
    const ya = a.y + pillH / 2, yb = b.y + pillH / 2, xr = Math.max(a.x, b.x) + pillW + 30;
    d = `M ${a.x + pillW} ${ya} C ${xr} ${ya}, ${xr} ${yb}, ${b.x + pillW} ${yb}`;
  }
  const p = document.createElementNS(NS, 'path');
  p.setAttribute('d', d); p.classList.add('edge');
  p.setAttribute('stroke', e.nc > 0 ? '#7dd3fc' : '#475569');
  p.setAttribute('stroke-width', e.nc > 0 ? 1.8 : 1);
  if (e.nc === 0) p.setAttribute('stroke-dasharray', '4 4');
  p.setAttribute('opacity', e.nc > 0 ? 0.85 : 0.5);
  p.style.pointerEvents = 'none';            // the wide hit path below catches hover/click
  gE.appendChild(p); edgeEls.push(p);
  // a fat transparent path makes the thin line easy to hover/click
  const hit = document.createElementNS(NS, 'path');
  hit.setAttribute('d', d); hit.setAttribute('fill', 'none');
  hit.setAttribute('stroke', 'transparent'); hit.setAttribute('stroke-width', 14);
  hit.style.cursor = 'pointer';
  hit.addEventListener('mousemove', ev => tip(ev,
    `<b>${esc(a.c)} → ${esc(b.c)}</b><br>${esc(e.rel)}<br>` +
    `<span style="color:#7dd3fc">${e.nc} signal${e.nc === 1 ? '' : 's'}</span> · ` +
    `<span style="color:#64748b">click = detail</span>`));
  hit.addEventListener('mouseleave', hideTip);
  hit.addEventListener('click', ev => { ev.stopPropagation(); showEdge(i); });
  gE.appendChild(hit);
});

// ── band labels: LEFT layers get a gutter name; RIGHT domains get a header line ──
DATA.columns.forEach(col => {
  const cnt = col.players.length + (col.players.length === 1 ? ' company' : ' companies');
  if (col._dom) {                  // domain panel: one header line above the pills
    const t = document.createElementNS(NS, 'text');
    t.setAttribute('x', col._x0); t.setAttribute('y', col._top + 13); t.classList.add('hdr');
    t.setAttribute('fill', col.color || '#94a3b8');
    t.textContent = '▸ ' + (col.name || col.slug).toUpperCase() + '  ·  ' + cnt;
    sv.appendChild(t);
  } else {                         // layer stack: name + count in the left gutter
    const ty = col._pillTop + pillH / 2;
    const tx = document.createElementNS(NS, 'text');
    tx.setAttribute('x', 12); tx.setAttribute('y', ty - 4); tx.classList.add('hdr');
    tx.setAttribute('fill', col.color || '#94a3b8');
    tx.textContent = (col.name || col.slug).toUpperCase();
    sv.appendChild(tx);
    const c = document.createElementNS(NS, 'text');
    c.setAttribute('x', 12); c.setAttribute('y', ty + 11); c.classList.add('cnt');
    c.setAttribute('fill', col.color || '#64748b');
    c.textContent = cnt;
    sv.appendChild(c);
  }
});
// vertical divider between the layer stack (left) and the domain panel (right)
if (hasDom) {
  const dl = document.createElementNS(NS, 'line');
  dl.setAttribute('x1', leftW + DIV / 2); dl.setAttribute('y1', padT);
  dl.setAttribute('x2', leftW + DIV / 2); dl.setAttribute('y2', H - 8);
  dl.setAttribute('stroke', '#1e293b'); dl.setAttribute('stroke-width', 2);
  sv.appendChild(dl);
}
// ── sector labels: a faint tag above the FIRST pill of each sector run ───────
// (players of one sector are contiguous, so a label appears once per sector group)
DATA.columns.forEach((col, ci) => {
  if (!col._hasSec) return;
  let prev = null;
  col.players.forEach((p, pi) => {
    if (p.sec && p.sec !== prev) {
      const n = idx[ci + '|' + pi];
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', n.x); t.setAttribute('y', n.y - 4);
      t.setAttribute('fill', '#9aa6b2'); t.setAttribute('font-size', '10px');
      t.textContent = p.sec; sv.appendChild(t);
    }
    prev = p.sec;
  });
});

// ── ripple reachability (kept from v2 — the lights) ─────────────────────────
function reach(k, adj, next) {
  const seen = new Set(), q = [k];
  while (q.length) {
    const cur = q.pop();
    (adj[cur] || []).forEach(i => {
      const nx = next(edges[i]);
      if (!seen.has(nx)) { seen.add(nx); q.push(nx); }
    });
  }
  seen.delete(k); return seen;
}
const downOf = k => reach(k, outs, e => e.t);
const upOf   = k => reach(k, ins,  e => e.s);

let pinned = null;
const pillEls = {};
function clearAll() {
  Object.values(pillEls).forEach(el => el.classList.remove('dim', 'rself', 'rdown', 'rup'));
  edgeEls.forEach(el => el.classList.remove('dim', 'edown', 'eup'));
}
function applyRipple(k) {
  const D = downOf(k), U = upOf(k);
  clearAll();
  nodes.forEach(n => {
    const el = pillEls[n.k];
    if (n.k === k) el.classList.add('rself');
    else if (D.has(n.k)) el.classList.add('rdown');
    else if (U.has(n.k)) el.classList.add('rup');
    else el.classList.add('dim');
  });
  edgeEls.forEach((el, i) => {
    const e = edges[i];
    const sD = (e.s === k || D.has(e.s)), tD = D.has(e.t);
    const sU = U.has(e.s), tU = (e.t === k || U.has(e.t));
    if (sD && tD) el.classList.add('edown');
    else if (sU && tU) el.classList.add('eup');
    else el.classList.add('dim');
  });
}
function hoverHl(k) {            // direct neighbors only (when nothing pinned)
  const keep = new Set([k]), keepE = new Set();
  (outs[k] || []).forEach(i => { keep.add(edges[i].t); keepE.add(i); });
  (ins[k]  || []).forEach(i => { keep.add(edges[i].s); keepE.add(i); });
  Object.entries(pillEls).forEach(([kk, el]) => el.classList.toggle('dim', !keep.has(kk)));
  edgeEls.forEach((el, i) => el.classList.toggle('dim', !keepE.has(i)));
}

// ── edge-detail panel: the relationship + the contract SIGNALS that drew the line ──
let selEdge = null;
function clearSel() {
  if (selEdge !== null && edgeEls[selEdge]) edgeEls[selEdge].classList.remove('esel');
  Object.values(pillEls).forEach(el => el.classList.remove('epin'));
  selEdge = null;
}
function edgeBetween(k1, k2) {     // indices of edges directly linking two companies
  const res = [];
  (outs[k1] || []).forEach(i => { if (edges[i].t === k2) res.push(i); });
  (outs[k2] || []).forEach(i => { if (edges[i].t === k1) res.push(i); });
  return res;
}
function renderPanel(i) {
  const e = edges[i], a = idx[e.s], b = idx[e.t];
  let h = `<div class="ep-h"><span><b>${esc(a.c)}</b> &rarr; <b>${esc(b.c)}</b></span>`
        + `<span class="ep-x" id="ep-x">&times;</span></div>`
        + `<div class="ep-rel">${esc(e.rel) || 'supply relationship'}</div>`;
  if (e.cn && e.cn.length) {
    h += `<div class="ep-n">${e.cn.length} signal${e.cn.length === 1 ? '' : 's'} on this link</div>`;
    e.cn.forEach(c => {
      const meta = [c.units, c.value, c.date_signed, c.type]
        .filter(x => x && x !== 'no specific figure' && x !== 'not stated').join('  ·  ');
      h += `<div class="ep-c">`
         + (c.source ? `<div class="ep-src">${esc(c.source)}</div>` : '')
         + (c.signal ? `<div class="ep-sig">${esc(c.signal)}</div>` : '')
         + (meta ? `<div class="ep-meta">${esc(meta)}</div>` : '')
         + `</div>`;
    });
  } else {
    h += `<div class="ep-empty">Structure only — no deal/contract data on this link yet.</div>`;
  }
  const ep = document.getElementById('epanel');
  ep.innerHTML = h; ep.style.display = 'block';
  document.getElementById('ep-x').addEventListener('click', ev => { ev.stopPropagation(); closePanel(); });
}
function showEdge(i) {             // spotlight one edge + its endpoints, open the panel
  clearSel();
  selEdge = i;
  edgeEls[i].classList.add('esel');
  pillEls[edges[i].s].classList.add('epin');
  pillEls[edges[i].t].classList.add('epin');
  renderPanel(i);
}
function closePanelSoft() { document.getElementById('epanel').style.display = 'none'; clearSel(); }
function closePanel()     { closePanelSoft(); pinned = null; clearAll(); }

// ── company pills ─────────────────────────────────────────────────────────────
nodes.forEach(n => {
  const g = document.createElementNS(NS, 'g'); g.classList.add('pill');
  const r = document.createElementNS(NS, 'rect');
  r.setAttribute('x', n.x); r.setAttribute('y', n.y);
  r.setAttribute('width', pillW); r.setAttribute('height', pillH);
  r.setAttribute('rx', 13);
  r.setAttribute('stroke', n.ext ? '#475569' : (n.color || '#94a3b8'));
  r.setAttribute('stroke-width', 1.2);
  if (n.ext) { r.setAttribute('stroke-dasharray', '4 3'); r.setAttribute('fill-opacity', 0.55); }
  g.appendChild(r);
  if (n.qd > 0) {
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', n.x + 12); dot.setAttribute('cy', n.y + pillH / 2);
    dot.setAttribute('r', 3); dot.setAttribute('fill', '#34d399');
    g.appendChild(dot);
  }
  const tx = document.createElementNS(NS, 'text');
  tx.setAttribute('x', n.x + (n.qd > 0 ? 20 : 10));
  tx.setAttribute('y', n.y + pillH / 2 + 4);
  let nm = n.c;
  const maxC = Math.floor((pillW - (n.qd > 0 ? 26 : 16)) / 6.4);
  if (nm.length > maxC) nm = nm.slice(0, maxC - 1) + '…';
  tx.textContent = nm;
  g.appendChild(tx);
  g.addEventListener('mouseenter', () => { if (!pinned) hoverHl(n.k); });
  g.addEventListener('mousemove', ev => {
    const nd = downOf(n.k).size, nu = upOf(n.k).size;
    tip(ev, `<b>${esc(n.c)}</b><br>${esc(n.p)}` +
      (n.qd > 0 ? `<br><span style="color:#34d399">${n.qd} data point${n.qd === 1 ? '' : 's'}</span>` : '') +
      `<br><span style="color:#fbbf24">▼ downstream ${nd}</span> · ` +
      `<span style="color:#60a5fa">▲ upstream ${nu}</span>` +
      `<br><span style="color:#64748b">click = ripple</span>`);
  });
  g.addEventListener('mouseleave', () => { if (!pinned) clearAll(); hideTip(); });
  g.addEventListener('click', ev => {
    ev.stopPropagation();
    // A→B: if a company is pinned and you click a directly-linked one, show their signals
    if (pinned && pinned !== n.k) {
      const es = edgeBetween(pinned, n.k);
      if (es.length) { showEdge(es[0]); return; }
    }
    closePanelSoft();                       // otherwise: plain pin + ripple
    pinned = (pinned === n.k) ? null : n.k;
    if (pinned) applyRipple(n.k); else clearAll();
  });
  sv.appendChild(g); pillEls[n.k] = g;
});
sv.addEventListener('click', () => { pinned = null; clearAll(); closePanelSoft(); });
</script></body></html>"""

# Top-level tabs. Graph FIRST: the WebGL canvas must initialize inside a VISIBLE
# container — when it boots inside a hidden tab panel its camera controls are born
# with a broken screen-rect and rotate/pan never work. Making Graph the default
# tab guarantees a visible, correctly-sized init. The Quant tab only appears when
# quant/results.json exists (it is produced locally by quant/event_study.py).
_has_quant = os.path.exists("quant/results.json")
_tab_labels = ["🧬 Graph", "🗺️ Chain 2D", "📈 Timelines", "🔎 Screener"] + (["🧪 Quant"] if _has_quant else [])
_all_tabs = st.tabs(_tab_labels)
_tab_graph, _tab_chain2d, _tab_tl, _tab_screener = _all_tabs[0], _all_tabs[1], _all_tabs[2], _all_tabs[3]
_tab_quant = _all_tabs[4] if _has_quant else None

with _tab_graph:
    # Search lives directly above the graph (phones never open the sidebar).
    _sc1, _sc2 = st.columns([0.6, 0.4])
    with _sc1:
        filtered_names = sorted(n["id"] for n in visible_nodes)
        search = st.selectbox("Search company", [""] + filtered_names)
    with _sc2:
        st.caption(f"{len(visible_nodes)} companies · {len(visible_links)} edges")
        st.caption("Click node → details. Drag to rotate. Scroll to zoom.")

    html = (HTML_TEMPLATE
        .replace("__GRAPH_DATA__",   graph_data_json)
        .replace("__GROUP_COLORS__", group_colors_json)
        .replace("__GROUP_NAMES__",  group_names_json)
        .replace("__CHAIN_COLORS__", chain_colors_json)
        .replace("__FOCUS_NODE__",   json.dumps(search))
    )
    st.components.v1.html(html, height=800, scrolling=False)

# ── Chain 2D (one chain at a time, layer map) ─────────────────────────────────
# Reads the original chain JSONs (not the merged graph) because only they keep the
# curated nesting (layer → sector → players). One selectbox → one chain → companies
# grouped into layer columns with sector sub-headers (and domain columns at the right).
_chain_files = load_chain_files()
with _tab_chain2d:
    _c2c1, _c2c2 = st.columns([0.45, 0.55])
    with _c2c1:
        _c2d_sel = st.selectbox(
            "Chain", sorted(_chain_files.keys()),
            format_func=lambda k: k.replace("_", " "), key="c2d_chain",
        )
    _c2d_chain = _chain_files[_c2d_sel]
    with _c2c2:
        st.caption(f"**{_c2d_chain.get('company', '')}** — {_c2d_chain.get('chain_focus', '')}")
        st.caption("Layers (top→bottom) flow down the LEFT; cross-cutting domains "
                   "(power/thermal/…) sit in the RIGHT panel beside the stack. Left gutter / "
                   "right header = band name; faint strip = sectors. Hover = direct neighbors · "
                   "CLICK = full ripple (▼ downstream amber / ▲ upstream blue) · solid = has deal "
                   "data · dashed = structure only · green dot = earnings data.")

    # Build one column per layer (then per domain), preserving the canonical order.
    # Within a column, players are flattened under sector (and sub-sector) headers; each
    # player keeps a FLAT index (pi) for the edge model and a visual `row` slot for layout.
    def _c2d_build_column(slug, name, color, kind, group):
        players, headers, raw, row = [], [], [], 0
        for _sec in group.get("sectors", []):
            headers.append({"label": _sec.get("sector", ""), "sub": 0, "row": row}); row += 1
            for _ss in _sec.get("sub_sectors", []):
                headers.append({"label": _ss.get("sub_sector", ""), "sub": 1, "row": row}); row += 1
                for _p in _ss.get("players", []):
                    players.append({"c": _p["company"], "p": _p.get("product", ""),
                                    "qd": len(_p.get("quarterly_data", [])), "ext": 0, "row": row,
                                    "sec": _sec.get("sector", ""), "sub": _ss.get("sub_sector", "")})
                    raw.append(_p); row += 1
            for _p in _sec.get("players", []):
                players.append({"c": _p["company"], "p": _p.get("product", ""),
                                "qd": len(_p.get("quarterly_data", [])), "ext": 0, "row": row,
                                "sec": _sec.get("sector", ""), "sub": ""})
                raw.append(_p); row += 1
        return ({"slug": slug, "name": name, "color": color, "kind": kind,
                 "players": players, "headers": headers, "nrows": row}, raw)

    _c2d_cols, _c2d_raw = [], []   # _c2d_raw[ci] = list of original player dicts for column ci
    _layer_groups = {g["layer"]: g for g in _c2d_chain.get("flow", []) if "layer" in g}
    for _slug in sorted(_layer_groups, key=lambda s: LAYER_ORDER.get(s, 999)):
        _col, _raw = _c2d_build_column(_slug, LAYER_NAMES.get(_slug, _slug),
                                       LAYER_COLORS.get(_slug, "#94a3b8"), "layer", _layer_groups[_slug])
        _c2d_cols.append(_col); _c2d_raw.append(_raw)
    _dom_order = {s: i for i, (s, *_rest) in enumerate(DOMAINS)}
    _domain_groups = {g["domain"]: g for g in _c2d_chain.get("domains", []) if "domain" in g}
    for _slug in sorted(_domain_groups, key=lambda s: _dom_order.get(s, 999)):
        _col, _raw = _c2d_build_column(_slug, DOMAIN_NAMES.get(_slug, _slug),
                                       DOMAIN_COLORS.get(_slug, "#94a3b8"), "domain", _domain_groups[_slug])
        _c2d_cols.append(_col); _c2d_raw.append(_raw)

    # company → (colIdx, playerIdx) of FIRST occurrence (edge TARGETS resolve here)
    _c2d_pos = {}
    for _ci, _col in enumerate(_c2d_cols):
        for _pi, _pl in enumerate(_col["players"]):
            _c2d_pos.setdefault(_pl["c"], (_ci, _pi))

    # Edge targets in ANOTHER chain become ghost pills in an extra "external" column.
    _c2d_ext, _c2d_edges = {}, []
    _c2d_pending = []
    for _ci, _raw in enumerate(_c2d_raw):
        for _pi, _p in enumerate(_raw):
            for _e in _p.get("connects_to", []):
                _tgt_co = _e.get("company")
                if _tgt_co == _p["company"]:
                    continue
                _tgt = _c2d_pos.get(_tgt_co)
                if _tgt is None:
                    if _tgt_co not in _c2d_ext:
                        _c2d_ext[_tgt_co] = len(_c2d_ext)
                    _tgt = ("EXT", _c2d_ext[_tgt_co])
                _c2d_pending.append((_ci, _pi, _tgt, _e))
    if _c2d_ext:
        _ext_players = [{"c": _co, "p": "appears in another chain", "qd": 0, "ext": 1, "row": _i,
                         "sec": "", "sub": ""}
                        for _co, _i in sorted(_c2d_ext.items(), key=lambda kv: kv[1])]
        _c2d_cols.append({"slug": "external", "name": "External", "color": "#475569",
                          "kind": "external", "players": _ext_players, "headers": [],
                          "nrows": len(_ext_players)})
    _ext_ci = len(_c2d_cols) - 1
    for _ci, _pi, _tgt, _e in _c2d_pending:
        _tcj, _tpj = (_ext_ci, _tgt[1]) if _tgt[0] == "EXT" else _tgt
        _contracts = _e.get("contracts", [])
        _c2d_edges.append({
            "ci": _ci, "pi": _pi, "cj": _tcj, "pj": _tpj,
            "rel": _e.get("relationship", ""), "nc": len(_contracts),
            "contracts": _contracts,   # full deal detail, shown when the edge is clicked
        })

    _c2d_html = (CHAIN2D_TEMPLATE
        .replace("__CHAIN2D_DATA__", json.dumps({"columns": _c2d_cols, "edges": _c2d_edges}, ensure_ascii=False))
    )
    # Height = the TALLER of the two side-by-side regions (left layer stack vs right
    # domain panel), not their sum. perRow depends on client width (unknown server-side),
    # so estimate ~6 pills/row left, ~3 right; the SVG sizes itself exactly and
    # #wrap overflow:auto absorbs any slack.
    def _band_h(_c, _per):
        _rows = max(1, math.ceil(len(_c["players"]) / _per)) if _c["players"] else 1
        _hdr = 18 if _c.get("kind") == "domain" else 0
        return _hdr + 14 + _rows * 32 + 10
    _left_h = sum(_band_h(_c, 6) for _c in _c2d_cols if _c.get("kind") != "domain")
    _right_h = sum(_band_h(_c, 3) for _c in _c2d_cols if _c.get("kind") == "domain")
    st.components.v1.html(_c2d_html, height=min(1700, 90 + max(_left_h, _right_h)), scrolling=True)
    st.caption(f"{sum(len(_c['players']) for _c in _c2d_cols)} companies · {len(_c2d_edges)} edges in this chain")

# ── Company Screener (data-driven from company_metrics.json) ──────────────────
# Curated metrics layer — independent of the graph, maintained alongside each
# transcript enrichment (one row of headline numbers per company).
if os.path.exists("company_metrics.json"):
    with open("company_metrics.json", encoding="utf-8") as _f:
        _metrics = json.load(_f)
    _metrics.pop("_schema", None)

    # Map each metrics company to its layers/sectors/chains from the graph for filtering.
    _node_lookup = {n["id"]: n for n in graph["nodes"]}
    # Layers offered in canonical order (then any domains a node carries); label by display name.
    _present = {s for n in graph["nodes"] for s in n.get("layers", []) + n.get("domains", [])}
    _all_groups = [s for s, *_ in LAYERS if s in _present] + [s for s, *_ in DOMAINS if s in _present]
    _all_sectors = sorted({s for n in graph["nodes"] for s in n.get("sectors", [])})
    _all_chains = sorted({c for n in graph["nodes"] for c in n["chains"]})

    with _tab_screener:
        st.markdown("### 🔎 Company Screener")
        st.caption(
            "Headline metrics per company, curated from the same earnings calls that feed the graph. "
            "No share prices — operational signals only. Filter by layer, sector or chain; click a column header to sort."
        )
        _fc1, _fc2, _fc3 = st.columns(3)
        with _fc1:
            _f_layer = st.selectbox("Layer / Domain", ["All"] + _all_groups,
                                    format_func=lambda s: GROUP_NAMES.get(s, s) if s != "All" else "All",
                                    key="scr_layer")
        with _fc2:
            _f_sector = st.selectbox("Sector", ["All"] + _all_sectors, key="scr_sector")
        with _fc3:
            _f_chain = st.selectbox("Chain", ["All"] + [c.replace("_", " ") for c in _all_chains], key="scr_chain")

        _rows = []
        for _co, _m in _metrics.items():
            _n = _node_lookup.get(_co)
            if _f_layer != "All" and (not _n or _f_layer not in (_n.get("layers", []) + _n.get("domains", []))):
                continue
            if _f_sector != "All" and (not _n or _f_sector not in _n.get("sectors", [])):
                continue
            if _f_chain != "All" and (not _n or _f_chain.replace(" ", "_") not in _n["chains"]):
                continue
            _rows.append({
                "Company":        _co,
                "Ticker":         (_n.get("ticker") if _n else None) or "—",
                "Growth":         _m.get("revenue_growth", "—"),
                "Guidance":       _m.get("guidance", "—"),
                "Backlog / B2B":  _m.get("backlog_or_b2b", "—"),
                "Supply status":  _m.get("supply_status", "—"),
                "Next catalyst":  _m.get("next_catalyst", "—"),
                "As of":          _m.get("asof", "—"),
            })
        if _rows:
            _rows.sort(key=lambda r: r["As of"], reverse=True)
            st.dataframe(_rows, hide_index=True, use_container_width=True, height=min(620, 60 + 35 * len(_rows)))
            st.caption(f"{len(_rows)} companies with curated metrics · {len(_metrics)} total in company_metrics.json")
        else:
            st.caption("No curated metrics for this filter yet — metrics are added as each company's call is enriched.")

# ── Technology & Product timelines (data-driven from timelines/*.json) ─────────
# Separate layer: timelines/ affects ONLY these tables; chains/ affects ONLY the
# supply graph above. The two pipelines are independent and meet only here.
_TL_ORDER = ["cpo", "optical_speed", "silicon_photonics", "ocs", "hbm", "nand_storage", "cpu", "foundry", "power_cooling", "product_launches"]
_tl_files = {}
if os.path.isdir("timelines"):
    for _fn in sorted(os.listdir("timelines")):
        if _fn.endswith(".json"):
            _tl_files[_fn[:-5]] = os.path.join("timelines", _fn)
_tl_keys = [k for k in _TL_ORDER if k in _tl_files] + [k for k in _tl_files if k not in _TL_ORDER]

if _tl_keys:
    _timelines = {}
    for _k in _tl_keys:
        with open(_tl_files[_k], encoding="utf-8") as _f:
            _timelines[_k] = json.load(_f)
    with _tab_tl:
        st.markdown("### 📈 Technology & Product Timelines")
        st.caption(
            "Forward market-size, adoption and launch views — when each technology ramps, how big it "
            "gets, and which models adopt it. Separate layer from the supply graph."
        )
        # group timelines by `category` → one tab per category; topics become sub-sections.
        # (Data stays modular — one JSON per topic. A new topic auto-joins its category tab.)
        _CAT_ORDER = ["transitions", "supply", "optical", "memory", "compute", "manufacturing", "infrastructure", "products"]
        _CAT_LABEL = {"transitions": "🔀 Transitions", "supply": "🌡️ Supply Tightness",
                      "optical": "Optical", "memory": "Memory", "compute": "Compute",
                      "manufacturing": "Manufacturing", "infrastructure": "Infrastructure", "products": "Products"}
        _by_cat = {}
        for _k in _tl_keys:
            _by_cat.setdefault(_timelines[_k].get("category", "other"), []).append(_k)
        _cats = [c for c in _CAT_ORDER if c in _by_cat] + [c for c in _by_cat if c not in _CAT_ORDER]

        _cat_tabs = st.tabs([_CAT_LABEL.get(c, c.title()) for c in _cats])
        for _ctab, _cat in zip(_cat_tabs, _cats):
            with _ctab:
                for _i, _k in enumerate(_by_cat[_cat]):
                    _tl = _timelines[_k]
                    if _i > 0:
                        st.markdown("---")
                    st.markdown("#### " + _tl.get("name", _k))
                    if _tl.get("source"):
                        st.caption("Source: " + _tl["source"])
                    if _tl.get("note"):
                        st.caption(_tl["note"])
                    for _tbl in _tl.get("tables", []):
                        if _tbl.get("title"):
                            st.markdown("**" + _tbl["title"] + "**")
                        _rows = [dict(zip(_tbl["columns"], _r)) for _r in _tbl["rows"]]
                        st.dataframe(_rows, hide_index=True, use_container_width=True)
                        if _tbl.get("note"):
                            st.caption(_tbl["note"])

# ── Quant tab (data-driven from quant/results.json — computed OFFLINE) ────────
# The event study runs locally (quant/event_study.py); the app only READS the
# result files, so this tab adds zero compute to the page.
if _tab_quant is not None:
    with open("quant/results.json", encoding="utf-8") as _f:
        _qr = json.load(_f)

    with _tab_quant:
        st.markdown("### 🧪 Earnings-Call Event Study")
        st.caption(
            "Per-call abnormal returns over every US-listed earnings call in the graph "
            "(no signal classification — the v1 keyword taxonomy was tested and REJECTED: "
            "no sector-adjusted edge). Entry = close of t+1, the first trading day after "
            "the call; the announcement jump is reported separately because it is not "
            "buyable. Abnormal return = stock minus benchmark (SOXX = semiconductor "
            "sector, SPY = market). Computed offline by quant/event_study.py; "
            "full write-up in RESEARCH_LOG.docx."
        )

        def _pct(x):
            return f"{x*100:+.1f}%" if x is not None else "—"

        st.markdown("#### Baseline — the average call in this universe")
        _base_rows = []
        for _metric, _s in _qr.get("baseline", {}).items():
            if _s:
                _base_rows.append({
                    "Metric": _metric.replace("_vs_", " vs "),
                    "N": _s["n"],
                    "Mean": _pct(_s["mean"]),
                    "Median": _pct(_s["median"]),
                    "Hit rate": f"{_s['hit_rate']*100:.0f}%",
                    "t-stat": _s["t_stat"],
                })
        st.dataframe(_base_rows, hide_index=True, use_container_width=True)
        st.caption(
            "Reading: this universe (mid/small-cap supply-chain names) LAGS the mega-cap "
            "led SOXX while beating SPY — any future signal must beat this baseline, "
            "not zero."
        )

        if os.path.exists("quant/results_events.csv"):
            import csv as _csv
            with open("quant/results_events.csv", encoding="utf-8-sig") as _f:
                _call_rows = list(_csv.DictReader(_f))
            st.markdown("#### Per-call returns (sort any column)")
            st.dataframe(_call_rows, hide_index=True, use_container_width=True,
                         height=min(620, 60 + 35 * len(_call_rows)))

        _excl = _qr.get("excluded", {})
        if _excl:
            st.caption("Exclusions: " + " · ".join(f"{k}: {v}" for k, v in _excl.items()) +
                       " — recent calls back-fill automatically as time passes.")
