"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { VizNode, VizLink } from "@/lib/types";
import { BADGE_EMOJI } from "@/lib/signals";

// react-force-graph-3d is ESM + touches window/three at import time, so we load
// it client-side into state. This (unlike next/dynamic) forwards `ref` correctly,
// which we need for camera / force config / screen projection.

interface Props {
  nodes: VizNode[]; // ALL nodes (stable) — filtering is show/hide, not add/remove
  links: VizLink[]; // ALL links (stable)
  visibleIds: Set<string>;
  visibleChains: Set<string>;
  dimStale: boolean;
  glass: boolean;
  focusId: string | null;
  onNodeClick: (n: VizNode) => void;
  onBackgroundClick: () => void;
}

interface LogoObj {
  n: any;
  chip: HTMLDivElement;
  img: HTMLImageElement;
  rWorld: number;
  dead?: boolean;
}

const MIN_R = 9;
const STALE_COLOR = "#3a3f46";

// A link endpoint is a raw id string before the force sim runs, and the node
// object afterwards. Module scope so the memoised accessors below can use it.
const linkId = (e: any) => (typeof e === "object" ? e.id : e);

export default function Graph3D({
  nodes,
  links,
  visibleIds,
  visibleChains,
  dimStale,
  glass,
  focusId,
  onNodeClick,
  onBackgroundClick,
}: Props) {
  const fgRef = useRef<any>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const hoverIdRef = useRef<string | null>(null);
  const focusRef = useRef<string | null>(null);
  const rafRef = useRef<number | null>(null);
  const [size, setSize] = useState({ w: 800, h: 800 });
  const [FG, setFG] = useState<any>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  // Hover also lives in state (not just the ref) so the particle / arrow accessors
  // below can re-evaluate. Node hover fires on enter+leave only, so this re-renders
  // a couple of times per interaction, not per frame.
  const [hoverNodeId, setHoverNodeId] = useState<string | null>(null);

  // Keep the latest visibility in a ref so the logo RAF loop reads fresh values
  // without rebuilding the overlay DOM on every filter toggle.
  const visRef = useRef(visibleIds);
  visRef.current = visibleIds;

  // Graph data is built ONCE from the full node/link set → stable identity →
  // the force simulation runs once and never reheats when filters change.
  const graphData = useMemo(
    () => ({ nodes: nodes as any, links: links as any }),
    [nodes, links]
  );

  useEffect(() => {
    let alive = true;
    import("react-force-graph-3d")
      .then((m) => alive && setFG(() => m.default))
      .catch((e) => alive && setLoadErr(e?.message || String(e)));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const configuredRef = useRef(false);
  const configure = () => {
    const fg = fgRef.current;
    if (!fg || configuredRef.current) return;
    configuredRef.current = true;
    try {
      fg.d3Force("charge").strength(-400);
      fg.d3Force("link").distance(150);
    } catch {}
    // On a retina/4K display devicePixelRatio is 2-3, so the GPU renders 4-9x the
    // pixels of the canvas. Clamping to 1.5 is a huge fill-rate win and is visually
    // indistinguishable for spheres and lines.
    try {
      fg.renderer().setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    } catch {}
    if ("ontouchstart" in window || navigator.maxTouchPoints > 0) {
      const c = fg.controls();
      c.rotateSpeed = 0.35;
      c.zoomSpeed = 0.5;
      c.panSpeed = 0.25;
    }
  };

  // Build the logo overlay once per node set (not per filter change).
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    overlay.innerHTML = "";
    const logoNodes: LogoObj[] = [];
    for (const n of nodes as any[]) {
      if (!n.logo) continue;
      const chip = document.createElement("div");
      chip.className = "nlogo" + (n.logoBg === "dark" ? " dk" : "");
      const img = document.createElement("img");
      img.src = n.logo;
      img.alt = "";
      chip.appendChild(img);
      overlay.appendChild(chip);
      const o: LogoObj = { n, chip, img, rWorld: 4 * Math.cbrt(n.val) };
      img.onerror = () => {
        chip.remove();
        o.dead = true;
      };
      logoNodes.push(o);
    }

    const tick = () => {
      const fg = fgRef.current;
      const wrap = wrapRef.current;
      if (fg && wrap) {
        const cam = fg.camera();
        const halfH = wrap.clientHeight / 2;
        const perPx = halfH / Math.tan(((cam.fov / 2) * Math.PI) / 180);
        const W = wrap.clientWidth;
        const H = wrap.clientHeight;
        const vis = visRef.current;
        for (const o of logoNodes) {
          if (o.dead) continue;
          const n = o.n;
          if (n.x === undefined || !vis.has(n.id)) {
            o.chip.style.display = "none";
            continue;
          }
          const p = fg.graph2ScreenCoords(n.x, n.y, n.z);
          if (p.x < -80 || p.y < -80 || p.x > W + 80 || p.y > H + 80) {
            o.chip.style.display = "none";
            continue;
          }
          const c = cam.position;
          const d = Math.hypot(c.x - n.x, c.y - n.y, c.z - n.z);
          const rPx = (o.rWorld * perPx) / d;
          const forced = n.id === hoverIdRef.current || n.id === focusRef.current;
          if (rPx < MIN_R && !forced) {
            o.chip.style.display = "none";
            continue;
          }
          let w = Math.min(rPx * 1.8, 240);
          if (forced) w = Math.max(w, 40);
          o.img.style.width = w + "px";
          o.chip.style.padding = w * 0.07 + "px " + w * 0.11 + "px";
          o.chip.style.left = p.x + "px";
          o.chip.style.top = p.y + "px";
          o.chip.style.zIndex = forced ? "6" : "5";
          o.chip.style.display = "block";
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [nodes]);

  // Fly the camera to a searched node (only if it is currently visible).
  useEffect(() => {
    focusRef.current = focusId;
    if (!focusId) return;
    const t = setTimeout(() => {
      const fg = fgRef.current;
      if (!fg) return;
      const node = (nodes as any[]).find((n) => n.id === focusId);
      if (node && node.x !== undefined) {
        fg.cameraPosition(
          { x: (node.x || 0) + 80, y: node.y || 0, z: (node.z || 0) + 80 },
          node,
          1500
        );
      }
    }, 400);
    return () => clearTimeout(t);
  }, [focusId, nodes]);

  // Particles and arrows are per-link THREE meshes: at 253 contract links (x2
  // particles) plus 1,104 arrows that was ~1,600 objects animating every frame,
  // whether or not anything was visible. Now only the links touching the hovered
  // or searched node get them — typically a handful.
  const emphasisId = hoverNodeId ?? focusId;
  const touchesEmphasis = useCallback(
    (l: any) =>
      emphasisId != null &&
      (linkId(l.source) === emphasisId || linkId(l.target) === emphasisId),
    [emphasisId]
  );
  const linkParticles = useCallback(
    (l: any) => (touchesEmphasis(l) && l.contracts && l.contracts.length ? 2 : 0),
    [touchesEmphasis]
  );
  const linkArrowLength = useCallback(
    (l: any) => (touchesEmphasis(l) ? 4 : 0),
    [touchesEmphasis]
  );

  return (
    <div ref={wrapRef} className="graph-wrap">
      <div ref={overlayRef} className="nodelogos" />
      {loadErr && <div className="graph-msg">Failed to load 3D graph library: {loadErr}</div>}
      {!FG && !loadErr && <div className="graph-msg">Initializing 3D engine…</div>}
      {FG && (
        <FG
          ref={fgRef}
          width={size.w}
          height={size.h}
          graphData={graphData}
          backgroundColor={glass ? "#262b35" : "#0d1117"}
          nodeLabel={(n: any) => {
            const em = (n.badges || []).map((b: string) => BADGE_EMOJI[b] || "").join("");
            return em ? `${n.id} ${em}` : n.id;
          }}
          nodeColor={(n: any) => (dimStale && n.stale ? STALE_COLOR : n.color)}
          nodeVal={(n: any) => n.val}
          nodeOpacity={0.9}
          nodeVisibility={(n: any) => visibleIds.has(n.id)}
          linkVisibility={(l: any) =>
            visibleChains.has(l.chain) &&
            visibleIds.has(linkId(l.source)) &&
            visibleIds.has(linkId(l.target))
          }
          onNodeClick={(n: any) => {
            focusRef.current = n.id;
            onNodeClick(n as VizNode);
          }}
          onNodeHover={(n: any) => {
            hoverIdRef.current = n ? n.id : null;
            setHoverNodeId(n ? n.id : null);
          }}
          onBackgroundClick={() => {
            focusRef.current = null;
            onBackgroundClick();
          }}
          linkColor={(l: any) => l.color}
          linkOpacity={0.2}
          linkWidth={(l: any) => (l.contracts && l.contracts.length ? 1.5 : 0.5)}
          linkDirectionalArrowLength={linkArrowLength}
          linkDirectionalArrowRelPos={1}
          linkDirectionalArrowColor={(l: any) => l.color}
          linkDirectionalParticles={linkParticles}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleColor={(l: any) => l.color}
          onEngineTick={configure}
        />
      )}
    </div>
  );
}
