import base64
import streamlit as st
import glob
import json
import os
import re
from datetime import datetime
from collections import defaultdict
from urllib.parse import quote

st.set_page_config(page_title="AI Supply Chain", layout="wide", page_icon="🧬")

# ── Load merged graph ─────────────────────────────────────────────────────────
if not os.path.exists("graph/merged_graph.json"):
    st.error("merged_graph.json not found. Run graph_build.py first.")
    st.stop()

with open("graph/merged_graph.json", encoding="utf-8") as f:
    graph = json.load(f)

# ── Company logos (static/logos/, served by Streamlit static serving) ─────────
# manifest.json maps company name -> {file, bg}. bg says which chip background
# keeps the logo visible: "light" chip for dark logos, "dark" chip for white ones.
LOGOS = {}
if os.path.exists("static/logos/manifest.json"):
    with open("static/logos/manifest.json", encoding="utf-8") as f:
        LOGOS = json.load(f)

# Companies whose logo floats next to their node IN the 3D graph (pilot: NVIDIA).
# These logos are inlined as data URIs so they show regardless of server config.
GRAPH_LOGO_COMPANIES = {"NVIDIA"}

@st.cache_data
def logo_data_uri(company):
    info = LOGOS.get(company)
    if not info:
        return None
    path = os.path.join("static", "logos", info["file"])
    mime = "image/svg+xml" if path.endswith(".svg") else "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()

# ── Color maps ────────────────────────────────────────────────────────────────
TIER_COLORS = {
    "equipment":     "#f59e0b",
    "raw_material":  "#84cc16",
    "epiwafer":      "#06b6d4",
    "component":     "#6366f1",
    "packaging":     "#ec4899",
    "switch_system": "#f97316",
    "oem":           "#14b8a6",
    "hyperscaler":   "#3b82f6",
    "ai_lab":        "#a855f7",
    "software":      "#64748b",
}

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
    primary_tier = node["tiers"][0] if node["tiers"] else "unknown"
    deg = degree[node["id"]]
    val = max(4, int(deg ** 1.5))  # non-linear scaling — hubs grow much bigger
    badges, last_data, stale = node_signal_meta(node)
    badge_str = "".join(BADGE_EMOJI[b] for b in badges)
    # Hover tooltip: name + badge emojis only (freshness lives in the panel)
    hover = node["id"] + ((" " + badge_str) if badge_str else "")
    logo = LOGOS.get(node["id"])
    all_nodes_js.append({
        "id":             node["id"],
        "tier":           primary_tier,
        "tiers":          node["tiers"],
        "chains":         node["chains"],
        "products":       node["products"],
        "quarterly_data": node["quarterly_data"],
        "incoming":       incoming_index.get(node["id"], []),
        "color":          TIER_COLORS.get(primary_tier, "#94a3b8"),
        "val":            val,
        "ticker":         node.get("ticker"),
        "exchange":       node.get("exchange"),
        "country":        node.get("country"),
        "status":         node.get("status", "public"),
        "badges":         badges,
        "lastData":       last_data,
        "stale":          stale,
        "hover":          hover,
        "logo":           ("/app/static/logos/" + quote(logo["file"])) if logo else None,
        "logoBg":         logo["bg"] if logo else None,
        "logoData":       logo_data_uri(node["id"]) if node["id"] in GRAPH_LOGO_COMPANIES else None,
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
    with st.expander("**Tiers**", expanded=False):
        tier_checks = {}
        for tier, color in TIER_COLORS.items():
            col_dot, col_box = st.columns([0.12, 0.88])
            with col_dot:
                st.markdown(f'<span style="color:{color}; font-size:16px; line-height:2">●</span>', unsafe_allow_html=True)
            with col_box:
                tier_checks[tier] = st.checkbox(tier, value=True, key=f"tier_{tier}")

    st.markdown("---")
    dim_stale = st.checkbox(
        f"Dim stale nodes (no data in {STALE_DAYS}d)",
        value=False,
        help="Grey out companies whose newest signal is older than 6 months — or that have no signals at all. Hover a node to see its last-data date.",
    )
    st.markdown("---")

# ── Apply filters ─────────────────────────────────────────────────────────────
selected_chains = [c for c, v in chain_checks.items() if v]
selected_tiers  = [t for t, v in tier_checks.items() if v]

# A node is visible if it belongs to at least one selected chain AND one selected tier.
# Nodes with no tier/chain data are always shown.
visible_nodes = [
    n for n in all_nodes_js
    if (not n["chains"] or any(c in selected_chains for c in n["chains"]))
    and (not n["tiers"]  or any(t in selected_tiers  for t in n["tiers"]))
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
graph_data_json   = json.dumps({"nodes": visible_nodes, "links": visible_links})
tier_colors_json  = json.dumps(TIER_COLORS)
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
    <button class="xb" onclick="document.getElementById('panel').style.display='none'">&#x2715;</button>
  </div>
  <div id="pbody"></div>
</div>

<script src="https://unpkg.com/3d-force-graph@1.73.0/dist/3d-force-graph.min.js"></script>

<script>
const GDATA   = __GRAPH_DATA__;
const TCOLORS = __TIER_COLORS__;
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
    re: /\bLTA|long[- ]term (supply )?(agreement|contract|offtake)|multi[- ]?year (supply |purchase |contract|agreement|commitment)|supply agreement|\bNBM|\bSCA\b|build[- ]to[- ]order contract|purchase commitment/i },
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
const DATE_RE = /\b(Q[1-4]\s*(?:FY\s*)?20\d\d|[12]H\s*20\d\d|H[12]\s*(?:FY\s*)?20\d\d|(?:early|mid|late|end of|exiting|through|by)\s*(?:calendar |CY|fiscal |FY)?\s*20\d\d|CY20\d\d|FY20\d\d|20\d\d)\b/i;

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
  (node.tiers || []).forEach(t =>
    b += `<span class="badge" style="background:${TCOLORS[t] || '#94a3b8'}">${t}</span>`
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

  const titleEl = document.getElementById('ptitle');
  titleEl.textContent = '';
  const logoSrc = node.logoData || node.logo;   // data URI (always works) > static URL
  if (logoSrc) {
    const chip = document.createElement('span');
    chip.className = 'logochip ' + (node.logoBg || 'light');
    const img = document.createElement('img');
    img.src = logoSrc;
    img.alt = '';
    img.onerror = () => chip.remove();
    chip.appendChild(img);
    titleEl.appendChild(chip);
  }
  titleEl.appendChild(document.createTextNode(node.id));
  document.getElementById('pbody').innerHTML = b;
  document.getElementById('panel').style.display = 'block';
}

// Streamlit mounts this iframe inside a HIDDEN tab panel on first load (0x0 size).
// If the WebGL graph is created while hidden, the camera controls are born with a
// broken screen-rect and rotate/right-click-pan never recover (only zoom works).
// So: DEFER the entire graph initialization until the container actually has size
// — that way renderer, camera and controls all start from correct dimensions.
const gEl = document.getElementById('graph');
let Graph = null;

function initGraph() {
  Graph = ForceGraph3D()(gEl)
    .backgroundColor('#0d1117')
    .graphData(GDATA)
    .nodeLabel('hover')
    .nodeColor(n => n.color)
    .nodeVal(n => n.val)
    .nodeOpacity(0.9)
    .onNodeClick(n => showPanel(n))
    .onBackgroundClick(() => { document.getElementById('panel').style.display = 'none'; })
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

  // Logo badges centered ON the node: every frame, project the node to screen
  // coords and compute the sphere's APPARENT radius (world radius = nodeRelSize
  // 4 * cbrt(val), projected through the camera) so the badge scales 1:1 with
  // the sphere as you zoom.
  const logoLayer = document.createElement('div');
  logoLayer.id = 'nodelogos';
  document.body.appendChild(logoLayer);
  const logoNodes = [];
  GDATA.nodes.forEach(n => {
    if (!n.logoData) return;
    const chip = document.createElement('div');
    chip.className = 'nlogo' + (n.logoBg === 'dark' ? ' dk' : '');
    const img = document.createElement('img');
    img.src = n.logoData;
    chip.appendChild(img);
    logoLayer.appendChild(chip);
    logoNodes.push({ n, chip, img, rWorld: 4 * Math.cbrt(n.val) });
  });
  if (logoNodes.length) (function logoTick() {
    const cam = Graph.camera();
    const halfH = gEl.clientHeight / 2;
    const perPx = halfH / Math.tan((cam.fov / 2) * Math.PI / 180);  // world->px at d=1
    logoNodes.forEach(o => {
      const n = o.n;
      if (n.x === undefined) { o.chip.style.display = 'none'; return; }
      const p = Graph.graph2ScreenCoords(n.x, n.y, n.z);
      if (p.x < -80 || p.y < -80 || p.x > window.innerWidth + 80 || p.y > window.innerHeight + 80) {
        o.chip.style.display = 'none'; return;
      }
      const c = cam.position;
      const d = Math.hypot(c.x - n.x, c.y - n.y, c.z - n.z);
      const rPx = o.rWorld * perPx / d;            // sphere's on-screen radius
      if (rPx < 5) { o.chip.style.display = 'none'; return; }  // too small to read
      const w = Math.min(rPx * 1.8, 240);          // badge width ~ sphere diameter
      o.img.style.width = w + 'px';
      o.chip.style.padding = (w * 0.07) + 'px ' + (w * 0.11) + 'px';
      o.chip.style.left = p.x + 'px';
      o.chip.style.top = p.y + 'px';
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
</style></head><body>
<div id="wrap"><svg id="sv"></svg></div><div id="tip"></div>
<script>
const DATA = __CHAIN2D_DATA__;
const TIER_COLORS = __TIER_COLORS__;
const NS = 'http://www.w3.org/2000/svg';

// ── flatten into node/edge lists keyed by "tierIdx|playerIdx" ────────────────
const nodes = [], idx = {};
DATA.tiers.forEach((t, ti) => t.players.forEach((p, j) => {
  const k = ti + '|' + j;
  const n = { k, ti, j, tier: t.tier, c: p.c, p: p.p, qd: p.qd, ext: p.ext || 0 };
  nodes.push(n); idx[k] = n;
}));
const edges = DATA.edges.map(e => ({ s: e.si + '|' + e.sj, t: e.ti + '|' + e.tj, rel: e.rel, nc: e.nc }));
const outs = {}, ins = {};
edges.forEach((e, i) => {
  (outs[e.s] = outs[e.s] || []).push(i);
  (ins[e.t]  = ins[e.t]  || []).push(i);
});

// ── geometry: one column per tier, in curated flow order ────────────────────
const pillH = 26, gap = 8, hdrH = 42, padT = 8, padX = 14;
const colW = Math.max(186, Math.floor((window.innerWidth - 20) / Math.max(1, DATA.tiers.length)));
const pillW = colW - 2 * padX;
const maxN = Math.max(1, ...DATA.tiers.map(t => t.players.length));
const H = hdrH + padT + maxN * (pillH + gap) + 16;
const W = colW * DATA.tiers.length + 10;
const sv = document.getElementById('sv');
sv.setAttribute('width', W); sv.setAttribute('height', H);
nodes.forEach(n => { n.x = n.ti * colW + padX; n.y = hdrH + padT + n.j * (pillH + gap); });

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
  const y1 = a.y + pillH / 2, y2 = b.y + pillH / 2;
  let d;
  if (b.ti === a.ti) {              // same-tier: arc out the right side
    const xr = a.x + pillW;
    d = `M ${xr} ${y1} C ${xr + 36} ${y1}, ${xr + 36} ${y2}, ${xr} ${y2}`;
  } else if (b.ti < a.ti) {         // backward: leave left edge, enter right edge
    const xa = a.x, xb = b.x + pillW;
    d = `M ${xa} ${y1} C ${xa - colW * 0.4} ${y1}, ${xb + colW * 0.4} ${y2}, ${xb} ${y2}`;
  } else {                          // forward: right edge → left edge
    const x1 = a.x + pillW, x2 = b.x;
    d = `M ${x1} ${y1} C ${x1 + colW * 0.45} ${y1}, ${x2 - colW * 0.45} ${y2}, ${x2} ${y2}`;
  }
  const p = document.createElementNS(NS, 'path');
  p.setAttribute('d', d); p.classList.add('edge');
  p.setAttribute('stroke', e.nc > 0 ? '#7dd3fc' : '#475569');
  p.setAttribute('stroke-width', e.nc > 0 ? 1.8 : 1);
  if (e.nc === 0) p.setAttribute('stroke-dasharray', '4 4');
  p.setAttribute('opacity', e.nc > 0 ? 0.85 : 0.5);
  p.addEventListener('mousemove', ev => tip(ev,
    `<b>${esc(a.c)} → ${esc(b.c)}</b><br>${esc(e.rel)}<br>` +
    `<span style="color:#7dd3fc">${e.nc} contract${e.nc === 1 ? '' : 's'}</span>`));
  p.addEventListener('mouseleave', hideTip);
  gE.appendChild(p); edgeEls.push(p);
});

// ── tier headers ─────────────────────────────────────────────────────────────
DATA.tiers.forEach((t, ti) => {
  const tx = document.createElementNS(NS, 'text');
  tx.setAttribute('x', ti * colW + padX); tx.setAttribute('y', 22); tx.classList.add('hdr');
  tx.setAttribute('fill', TIER_COLORS[t.tier] || '#94a3b8');
  tx.textContent = t.tier.replace(/_/g, ' ').toUpperCase();
  sv.appendChild(tx);
  const c = document.createElementNS(NS, 'text');
  c.setAttribute('x', ti * colW + padX); c.setAttribute('y', 35); c.classList.add('cnt');
  c.textContent = t.players.length + (t.players.length === 1 ? ' company' : ' companies');
  sv.appendChild(c);
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

// ── company pills ─────────────────────────────────────────────────────────────
nodes.forEach(n => {
  const g = document.createElementNS(NS, 'g'); g.classList.add('pill');
  const r = document.createElementNS(NS, 'rect');
  r.setAttribute('x', n.x); r.setAttribute('y', n.y);
  r.setAttribute('width', pillW); r.setAttribute('height', pillH);
  r.setAttribute('rx', 13);
  r.setAttribute('stroke', n.ext ? '#475569' : (TIER_COLORS[n.tier] || '#94a3b8'));
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
    pinned = (pinned === n.k) ? null : n.k;
    if (pinned) applyRipple(n.k); else clearAll();
  });
  sv.appendChild(g); pillEls[n.k] = g;
});
sv.addEventListener('click', () => { pinned = null; clearAll(); });
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
        .replace("__TIER_COLORS__",  tier_colors_json)
        .replace("__CHAIN_COLORS__", chain_colors_json)
        .replace("__FOCUS_NODE__",   json.dumps(search))
    )
    st.components.v1.html(html, height=800, scrolling=False)

# ── Chain 2D (one chain at a time, flat tier map) ─────────────────────────────
# Reads the original chain JSONs (not the merged graph) because only they keep
# the curated tier ORDER. One selectbox → one chain → companies by tier.
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
        st.caption("Columns = tiers in flow order. Hover = direct neighbors · "
                   "CLICK = full ripple (▼ downstream amber / ▲ upstream blue) · "
                   "solid = has deal data · dashed = structure only · green dot = earnings data.")

    # Flatten the chain file into the shape the SVG template expects.
    _c2d_tiers, _c2d_edges = [], []
    _c2d_pos = {}  # company -> (tierIdx, playerIdx) of FIRST occurrence (edge targets resolve here)
    for _ti, _t in enumerate(_c2d_chain["flow"]):
        _ps = []
        for _pi, _p in enumerate(_t["players"]):
            _ps.append({"c": _p["company"], "p": _p.get("product", ""), "qd": len(_p.get("quarterly_data", []))})
            _c2d_pos.setdefault(_p["company"], (_ti, _pi))
        _c2d_tiers.append({"tier": _t["tier"], "players": _ps})
    # Edge targets that live in ANOTHER chain (e.g. Bloom→Oracle from power_cooling)
    # become ghost pills in an extra "external" column instead of being dropped.
    _c2d_ext = {}  # company -> playerIdx in the external pseudo-tier
    _c2d_pending = []
    for _ti, _t in enumerate(_c2d_chain["flow"]):
        for _pi, _p in enumerate(_t["players"]):
            for _e in _p.get("connects_to", []):
                _tgt_co = _e.get("company")
                if _tgt_co == _p["company"]:
                    continue
                _tgt = _c2d_pos.get(_tgt_co)
                if _tgt is None:
                    if _tgt_co not in _c2d_ext:
                        _c2d_ext[_tgt_co] = len(_c2d_ext)
                    _tgt = ("EXT", _c2d_ext[_tgt_co])
                _c2d_pending.append((_ti, _pi, _tgt, _e))
    if _c2d_ext:
        _c2d_tiers.append({"tier": "external", "players": [
            {"c": _co, "p": "appears in another chain", "qd": 0, "ext": 1}
            for _co in sorted(_c2d_ext, key=_c2d_ext.get)
        ]})
    _ext_ti = len(_c2d_tiers) - 1
    for _ti, _pi, _tgt, _e in _c2d_pending:
        _tti, _ttj = (_ext_ti, _tgt[1]) if _tgt[0] == "EXT" else _tgt
        _c2d_edges.append({
            "si": _ti, "sj": _pi, "ti": _tti, "tj": _ttj,
            "rel": _e.get("relationship", ""), "nc": len(_e.get("contracts", [])),
        })

    _c2d_html = (CHAIN2D_TEMPLATE
        .replace("__CHAIN2D_DATA__", json.dumps({"tiers": _c2d_tiers, "edges": _c2d_edges}, ensure_ascii=False))
        .replace("__TIER_COLORS__",  tier_colors_json)
    )
    _c2d_maxn = max((len(_t["players"]) for _t in _c2d_tiers), default=1)
    st.components.v1.html(_c2d_html, height=min(900, 80 + _c2d_maxn * 34), scrolling=True)
    st.caption(f"{sum(len(_t['players']) for _t in _c2d_tiers)} companies · {len(_c2d_edges)} edges in this chain")

# ── Company Screener (data-driven from company_metrics.json) ──────────────────
# Curated metrics layer — independent of the graph, maintained alongside each
# transcript enrichment (one row of headline numbers per company).
if os.path.exists("company_metrics.json"):
    with open("company_metrics.json", encoding="utf-8") as _f:
        _metrics = json.load(_f)
    _metrics.pop("_schema", None)

    # Map each metrics company to its tiers/chains from the graph for filtering.
    _node_lookup = {n["id"]: n for n in graph["nodes"]}
    _all_tiers  = sorted({t for n in graph["nodes"] for t in n["tiers"]})
    _all_chains = sorted({c for n in graph["nodes"] for c in n["chains"]})

    with _tab_screener:
        st.markdown("### 🔎 Company Screener")
        st.caption(
            "Headline metrics per company, curated from the same earnings calls that feed the graph. "
            "No share prices — operational signals only. Filter by tier or chain; click a column header to sort."
        )
        _fc1, _fc2 = st.columns(2)
        with _fc1:
            _f_tier = st.selectbox("Tier", ["All"] + _all_tiers, key="scr_tier")
        with _fc2:
            _f_chain = st.selectbox("Chain", ["All"] + [c.replace("_", " ") for c in _all_chains], key="scr_chain")

        _rows = []
        for _co, _m in _metrics.items():
            _n = _node_lookup.get(_co)
            if _f_tier != "All" and (not _n or _f_tier not in _n["tiers"]):
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
