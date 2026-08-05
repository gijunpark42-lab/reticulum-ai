// sync-data.mjs
// Copies the curated JSON + logo assets from the repo root (the Python/Streamlit
// project) into web/public so the Next.js app can serve them statically on Vercel.
// Runs automatically before `next dev` and `next build` (see package.json scripts).
//
// Why bundle some folders: the browser should fetch as few files as possible.
//   reports/*.json  -> public/data/reports.bundle.json  ({ node_name: report })
//   timelines/*.json-> public/data/timelines.bundle.json ([ {id, ...timeline} ])
//   chains/**/*.json-> public/data/chains/<stem>.json + chains/index.json (fetched on demand)
// Single files (merged_graph, company_metrics, ...) are copied as-is.

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", ".."); // repo root (earnings-ai/)
const WEB = path.resolve(__dirname, ".."); // web/
const OUT_DATA = path.join(WEB, "public", "data");
const OUT_LOGOS = path.join(WEB, "public", "logos");

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function readJson(p) {
  return JSON.parse(await fs.readFile(p, "utf-8"));
}

async function ensureDir(p) {
  await fs.mkdir(p, { recursive: true });
}

// Recursively list files under a dir (returns absolute paths).
async function walk(dir) {
  const out = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(full)));
    else out.push(full);
  }
  return out;
}

async function copyFileIfExists(src, dst) {
  if (!(await exists(src))) { console.warn(`  (skip, missing) ${path.relative(ROOT, src)}`); return false; }
  await ensureDir(path.dirname(dst));
  await fs.copyFile(src, dst);
  return true;
}

async function main() {
  await ensureDir(OUT_DATA);
  await ensureDir(OUT_LOGOS);

  // 1) Single JSON files copied verbatim.
  const singles = [
    ["graph/merged_graph.json", "merged_graph.json"],
    ["company_metrics.json", "company_metrics.json"],
    ["company_metadata.json", "company_metadata.json"],
    ["capex_backlog.json", "capex_backlog.json"],
    ["reports.json", "reports_flat.json"],
  ];
  for (const [rel, out] of singles) {
    const ok = await copyFileIfExists(path.join(ROOT, rel), path.join(OUT_DATA, out));
    if (ok) console.log(`  ✓ ${rel}`);
  }

  // 2) reports/*.json -> one bundle keyed by node_name (skip files starting with "_").
  const reportsDir = path.join(ROOT, "reports");
  const reportBundle = {};
  if (await exists(reportsDir)) {
    for (const f of await walk(reportsDir)) {
      const base = path.basename(f);
      if (!base.endsWith(".json") || base.startsWith("_")) continue;
      const rep = await readJson(f);
      const key = rep.node_name || path.basename(base, ".json");
      reportBundle[key] = rep;
    }
    await fs.writeFile(path.join(OUT_DATA, "reports.bundle.json"), JSON.stringify(reportBundle));
    console.log(`  ✓ reports.bundle.json (${Object.keys(reportBundle).length} reports)`);
  }

  // 3) timelines/*.json -> one ordered array, each tagged with its filename stem as id.
  const timelinesDir = path.join(ROOT, "timelines");
  const timelineBundle = [];
  if (await exists(timelinesDir)) {
    for (const f of await walk(timelinesDir)) {
      const base = path.basename(f);
      if (!base.endsWith(".json")) continue;
      const tl = await readJson(f);
      timelineBundle.push({ id: path.basename(base, ".json"), ...tl });
    }
    await fs.writeFile(path.join(OUT_DATA, "timelines.bundle.json"), JSON.stringify(timelineBundle));
    console.log(`  ✓ timelines.bundle.json (${timelineBundle.length} timelines)`);
  }

  // 4) chains/**/*.json -> flattened per-stem files + an index (fetched on demand by Chain 2D).
  const chainsDir = path.join(ROOT, "chains");
  const chainOut = path.join(OUT_DATA, "chains");
  const chainIndex = [];
  if (await exists(chainsDir)) {
    await ensureDir(chainOut);
    for (const f of await walk(chainsDir)) {
      const base = path.basename(f);
      if (!base.endsWith(".json")) continue;
      const stem = path.basename(base, ".json");
      const chain = await readJson(f);
      await fs.writeFile(path.join(chainOut, `${stem}.json`), JSON.stringify(chain));
      chainIndex.push({ id: stem, company: chain.company || stem, chain_focus: chain.chain_focus || "" });
    }
    chainIndex.sort((a, b) => a.id.localeCompare(b.id));
    await fs.writeFile(path.join(chainOut, "index.json"), JSON.stringify(chainIndex));
    console.log(`  ✓ chains/ (${chainIndex.length} chains)`);
  }

  // 5) quant (optional).
  await copyFileIfExists(path.join(ROOT, "quant", "results.json"), path.join(OUT_DATA, "quant", "results.json"));
  await copyFileIfExists(path.join(ROOT, "quant", "results_events.csv"), path.join(OUT_DATA, "quant", "results_events.csv"));

  // 6) logos: copy every file in static/logos (images + manifest.json) into public/logos.
  const logosDir = path.join(ROOT, "static", "logos");
  if (await exists(logosDir)) {
    let n = 0;
    for (const f of await walk(logosDir)) {
      const rel = path.relative(logosDir, f);
      await ensureDir(path.dirname(path.join(OUT_LOGOS, rel)));
      await fs.copyFile(f, path.join(OUT_LOGOS, rel));
      n++;
    }
    console.log(`  ✓ logos/ (${n} files)`);
  }

  console.log("Data sync complete.");
}

main().catch((e) => { console.error(e); process.exit(1); });
