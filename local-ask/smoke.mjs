// smoke.mjs — is the local runner alive and answering?
//
//   node smoke.mjs                      (uses local-ask/.env or the environment)
//   LOCAL_ASK_URL=https://xxx.trycloudflare.com node smoke.mjs   (through the tunnel)
//
// Calls GET /health, then POST /answer with a made-up question and two sample
// snippets, and prints what came back. Exit code 1 on any failure.

import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
try {
  process.loadEnvFile(path.join(HERE, ".env"));
} catch {
  /* fine */
}

const BASE = (process.env.LOCAL_ASK_URL || "http://127.0.0.1:8787").replace(/\/+$/, "");
const SECRET = process.env.ASK_SHARED_SECRET || "";
if (!SECRET) {
  console.error("ASK_SHARED_SECRET is not set (put it in local-ask/.env).");
  process.exit(1);
}
const headers = { "content-type": "application/json", "x-ask-secret": SECRET };

const sample = {
  question: "Who started HBM4 mass production?",
  intent: "lookup",
  snippets: [
    {
      kind: "signal",
      company: "SK Hynix",
      chain: "hbm_memory",
      label: "SK Hynix Q2 FY2026 (08-14-2026)",
      date: "2026-08-14",
      text: "HBM4 12-Hi entered mass production in the quarter; HBM sales rose 30% QoQ. Figure: HBM +30% QoQ",
      topics: ["hbm"],
    },
    {
      kind: "contract",
      company: "SK Hynix",
      target: "NVIDIA",
      chain: "nvidia_vera_rubin",
      label: "SK Hynix Q2 FY2026 (08-14-2026)",
      date: "2026-08-14",
      text: "SK Hynix → NVIDIA: HBM4 supply for Vera Rubin. Volume shipments of HBM4 for the Rubin platform began in Q2.",
      topics: ["hbm"],
    },
  ],
};

async function main() {
  console.log(`runner: ${BASE}`);
  let t0 = Date.now();
  const h = await fetch(`${BASE}/health`, { headers, signal: AbortSignal.timeout(5000) });
  console.log(`GET /health → ${h.status} ${await h.text()} (${Date.now() - t0} ms)`);
  if (h.status !== 200) throw new Error("health check failed");

  t0 = Date.now();
  const r = await fetch(`${BASE}/answer`, {
    method: "POST",
    headers,
    body: JSON.stringify(sample),
    signal: AbortSignal.timeout(120_000),
  });
  const text = await r.text();
  console.log(`POST /answer → ${r.status} (${Date.now() - t0} ms)`);
  let j;
  try {
    j = JSON.parse(text);
  } catch {
    throw new Error(`not JSON: ${text.slice(0, 300)}`);
  }
  if (r.status !== 200) throw new Error(`answer failed: ${JSON.stringify(j)}`);
  console.log(`model ${j.model} (${j.cli_model}, effort ${j.effort}) · citations [${(j.citations || []).join(", ")}] · cost $${j.cost_usd ?? "?"}`);
  console.log("--- answer ---\n" + j.answer);
  if (!j.answer || !Array.isArray(j.citations)) throw new Error("reply is missing answer/citations");
}

main().catch((e) => {
  console.error("SMOKE TEST FAILED:", e.message);
  process.exit(1);
});
