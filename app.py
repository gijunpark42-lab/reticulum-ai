import streamlit as st
import json
import os
from collections import defaultdict

st.set_page_config(page_title="AI Supply Chain", layout="wide", page_icon="🧬")

# ── Load merged graph ─────────────────────────────────────────────────────────
if not os.path.exists("graph/merged_graph.json"):
    st.error("merged_graph.json not found. Run graph_build.py first.")
    st.stop()

with open("graph/merged_graph.json", encoding="utf-8") as f:
    graph = json.load(f)

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

# ── Compute degree (total edge count per node) across full graph ──────────────
# Degree = number of edges touching a node (in + out).
# Used for node size: more connections → bigger sphere.
degree = defaultdict(int)
for edge in graph["edges"]:
    degree[edge["source"]] += 1
    degree[edge["target"]] += 1

# ── Build full node + link lists ──────────────────────────────────────────────
all_nodes_js = []
for node in graph["nodes"]:
    primary_tier = node["tiers"][0] if node["tiers"] else "unknown"
    deg = degree[node["id"]]
    val = max(4, int(deg ** 1.5))  # non-linear scaling — hubs grow much bigger
    all_nodes_js.append({
        "id":             node["id"],
        "tier":           primary_tier,
        "tiers":          node["tiers"],
        "chains":         node["chains"],
        "products":       node["products"],
        "quarterly_data": node["quarterly_data"],
        "color":          TIER_COLORS.get(primary_tier, "#94a3b8"),
        "val":            val,
        "ticker":         node.get("ticker"),
        "exchange":       node.get("exchange"),
        "country":        node.get("country"),
        "status":         node.get("status", "public"),
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

# ── Search box (uses filtered node list) ─────────────────────────────────────
with st.sidebar:
    filtered_names = sorted(n["id"] for n in visible_nodes)
    search = st.selectbox("Search company", [""] + filtered_names)
    st.caption(f"{len(visible_nodes)} companies · {len(visible_links)} edges")
    st.caption("Click node → details. Drag to rotate. Scroll to zoom.")

# ── Serialize for injection into HTML ────────────────────────────────────────
graph_data_json   = json.dumps({"nodes": visible_nodes, "links": visible_links})
tier_colors_json  = json.dumps(TIER_COLORS)
chain_colors_json = json.dumps(CHAIN_COLORS)
focus_node_json   = json.dumps(search)

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
    top: 12px; right: 12px;
    width: 310px; max-height: 770px;
    overflow-y: auto;
    background: rgba(13,17,23,0.96);
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 14px;
    color: #e6edf3;
    font-size: 12px;
    z-index: 999;
    line-height: 1.5;
    scrollbar-width: thin;
  }
  .ph  { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
  .pt  { font-size:15px; font-weight:700; }
  .xb  { background:none; border:none; color:#8b949e; cursor:pointer; font-size:18px; }
  .badge  { display:inline-block; padding:2px 7px; border-radius:10px; font-size:10px; font-weight:700; color:#0d1117; margin:2px; }
  .cbadge { display:inline-block; padding:1px 6px; border-radius:6px; font-size:10px; background:#161b22; color:#8b949e; margin:2px; border-left:2px solid; }
  .sec { color:#8b949e; font-size:9px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin:10px 0 5px; padding-top:8px; border-top:1px solid #21262d; }
  .card { background:#161b22; border-radius:6px; padding:6px 8px; margin:4px 0; }
  .sig-hidden { display:none; }
  .morebtn { background:#161b22; border:1px solid #30363d; color:#58a6ff; cursor:pointer;
             font-size:11px; border-radius:6px; padding:4px 8px; margin:4px 0; width:100%; }
  .qtr { color:#58a6ff; font-size:9px; margin-bottom:2px; }
  .fig { color:#3fb950; font-weight:600; margin-top:2px; font-size:11px; }
  .rel { color:#8b949e; font-size:10px; display:block; margin-top:2px; }
  .ctract { background:#0d1117; border-radius:4px; padding:4px 7px; margin:3px 0; border-left:2px solid #21262d; font-size:11px; }
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
  b += '</div>';

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

  // Signals: newest-first, render the first 8, hide the rest behind a "show more"
  // toggle. All signals stay in the data — this only controls display order/volume
  // (hub nodes like NVIDIA carry 60+ signals and are unreadable otherwise).
  const sigs = (node.quarterly_data || []).slice().sort((a, b2) => sigDate(b2.quarter) - sigDate(a.quarter));
  if (sigs.length) {
    b += '<div class="sec">Signals</div><div id="sigwrap">';
    sigs.forEach((q, i) =>
      b += `<div class="card${i >= 8 ? ' sig-hidden' : ''}"><div class="qtr">${q.quarter}</div>${q.signal}<div class="fig">${q.figure}</div></div>`
    );
    if (sigs.length > 8)
      b += `<button class="morebtn" onclick="this.parentNode.querySelectorAll('.sig-hidden').forEach(e=>e.classList.remove('sig-hidden'));this.remove();">Show ${sigs.length - 8} more</button>`;
    b += '</div>';
  }

  if (outLinks.length) {
    b += '<div class="sec">Supplies &#8594;</div>';
    outLinks.forEach(e => {
      const tgt = e.target.id || e.target;
      b += `<div class="card"><b>${tgt}</b><span class="rel">${e.relationship}</span>`;
      (e.contracts || []).forEach(c => {
        const extras = [c.units, c.value].filter(v => v && v !== 'no specific figure').join(' \xB7 ');
        b += `<div class="ctract">${c.signal}${extras ? `<span class="cv">  ${extras}</span>` : ''}</div>`;
      });
      b += '</div>';
    });
  }

  document.getElementById('ptitle').textContent = node.id;
  document.getElementById('pbody').innerHTML = b;
  document.getElementById('panel').style.display = 'block';
}

const Graph = ForceGraph3D()(document.getElementById('graph'))
  .backgroundColor('#0d1117')
  .graphData(GDATA)
  .nodeLabel('id')
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

if (FOCUS) {
  setTimeout(() => {
    const node = GDATA.nodes.find(n => n.id === FOCUS);
    if (node) {
      Graph.cameraPosition({ x: (node.x||0) + 80, y: (node.y||0), z: (node.z||0) + 80 }, node, 1500);
      setTimeout(() => showPanel(node), 1600);
    }
  }, 3500);
}
</script>
</body>
</html>"""

html = (HTML_TEMPLATE
    .replace("__GRAPH_DATA__",   graph_data_json)
    .replace("__TIER_COLORS__",  tier_colors_json)
    .replace("__CHAIN_COLORS__", chain_colors_json)
    .replace("__FOCUS_NODE__",   focus_node_json)
)

st.components.v1.html(html, height=800, scrolling=False)

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
    st.markdown("---")
    st.markdown("### 📈 Technology & Product Timelines")
    st.caption(
        "Forward market-size, adoption and launch views — when each technology ramps, how big it "
        "gets, and which models adopt it. Separate layer from the supply graph above."
    )
    # group timelines by `category` → one tab per category; topics become sub-sections.
    # (Data stays modular — one JSON per topic. A new topic auto-joins its category tab.)
    _CAT_ORDER = ["optical", "memory", "compute", "manufacturing", "infrastructure", "products"]
    _CAT_LABEL = {"optical": "Optical", "memory": "Memory", "compute": "Compute",
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
