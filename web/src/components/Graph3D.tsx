"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { VizNode, VizLink } from "@/lib/types";
import { BADGE_EMOJI } from "@/lib/signals";

// react-force-graph-3d touches window/three at import time → client-only.
const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

interface Props {
  nodes: VizNode[];
  links: VizLink[];
  glass: boolean;
  focusId: string | null;
  onNodeClick: (n: VizNode) => void;
  onBackgroundClick: () => void;
}

// Logo overlay bookkeeping (one chip DOM node per logo'd graph node).
interface LogoObj {
  n: any;
  chip: HTMLDivElement;
  img: HTMLImageElement;
  rWorld: number;
  dead?: boolean;
}

const MIN_R = 9; // sphere on-screen radius (px) below which logos hide

export default function Graph3D({
  nodes,
  links,
  glass,
  focusId,
  onNodeClick,
  onBackgroundClick,
}: Props) {
  const fgRef = useRef<any>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const hoverIdRef = useRef<string | null>(null);
  const focusRef = useRef<string | null>(null); // clicked/panel-open node
  const rafRef = useRef<number | null>(null);
  const [size, setSize] = useState({ w: 800, h: 800 });

  // Size the canvas to its container.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // Configure forces once the graph instance exists.
  const onEngineRef = useRef(false);
  const configure = () => {
    const fg = fgRef.current;
    if (!fg || onEngineRef.current) return;
    onEngineRef.current = true;
    try {
      fg.d3Force("charge").strength(-400);
      fg.d3Force("link").distance(150);
    } catch {}
    if ("ontouchstart" in window || navigator.maxTouchPoints > 0) {
      const c = fg.controls();
      c.rotateSpeed = 0.35;
      c.zoomSpeed = 0.5;
      c.panSpeed = 0.25;
    }
  };

  // Build the logo overlay whenever the node set changes.
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
        for (const o of logoNodes) {
          if (o.dead) continue;
          const n = o.n;
          if (n.x === undefined) {
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

  // Fly the camera to a searched node.
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

  return (
    <div ref={wrapRef} className="graph-wrap">
      <div ref={overlayRef} className="nodelogos" />
      <ForceGraph3D
        ref={fgRef}
        width={size.w}
        height={size.h}
        graphData={{ nodes: nodes as any, links: links as any }}
        backgroundColor={glass ? "#262b35" : "#0d1117"}
        nodeLabel={(n: any) => {
          const em = (n.badges || []).map((b: string) => BADGE_EMOJI[b] || "").join("");
          return em ? `${n.id} ${em}` : n.id;
        }}
        nodeColor={(n: any) => n.color}
        nodeVal={(n: any) => n.val}
        nodeOpacity={0.9}
        onNodeClick={(n: any) => {
          focusRef.current = n.id;
          onNodeClick(n as VizNode);
        }}
        onNodeHover={(n: any) => {
          hoverIdRef.current = n ? n.id : null;
        }}
        onBackgroundClick={() => {
          focusRef.current = null;
          onBackgroundClick();
        }}
        linkColor={(l: any) => l.color}
        linkOpacity={0.2}
        linkWidth={(l: any) => (l.contracts && l.contracts.length ? 1.5 : 0.5)}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={(l: any) => l.color}
        linkDirectionalParticles={(l: any) => (l.contracts && l.contracts.length ? 2 : 0)}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleColor={(l: any) => l.color}
        onEngineTick={configure}
      />
    </div>
  );
}
