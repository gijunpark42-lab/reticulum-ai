// down.mjs — "ask 종료": stop the runner and the tunnel that up.mjs started.
// Nothing on Vercel is touched: with the tunnel gone, /health fails in ≤3 s and
// the site falls back to Gemini by itself.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STATE_FILE = path.join(HERE, "logs", "state.json");
const PORT = Number(process.env.PORT || 8787);

function readState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return {};
  }
}

/** Kill a process (and, on Windows, its children). */
function stop(label, pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0); // throws when it is not running
  } catch {
    console.log(`${label}: not running (pid ${pid})`);
    return false;
  }
  if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { windowsHide: true });
  else process.kill(pid);
  console.log(`${label}: stopped (pid ${pid})`);
  return true;
}

/** Pids listening on the runner port (Windows netstat), for a runner started by hand. */
function listeningPids(port) {
  if (process.platform !== "win32") return [];
  const out = spawnSync("netstat", ["-ano"], { encoding: "utf8", windowsHide: true }).stdout || "";
  const pids = new Set();
  for (const line of out.split("\n")) {
    if (line.includes(`:${port} `) && line.includes("LISTENING")) {
      const pid = Number(line.trim().split(/\s+/).pop());
      if (pid) pids.add(pid);
    }
  }
  return [...pids];
}

const state = readState();
stop("tunnel", state.tunnelPid);
stop("runner", state.runnerPid);
for (const pid of listeningPids(PORT)) stop(`runner on port ${PORT}`, pid);
// A tunnel started by hand (start-tunnel.cmd) has no pid on file: stop every cloudflared.
if (process.platform === "win32") {
  const r = spawnSync("taskkill", ["/IM", "cloudflared.exe", "/F"], { encoding: "utf8", windowsHide: true });
  if (r.status === 0) console.log("tunnel: stopped remaining cloudflared processes");
}
delete state.runnerPid;
delete state.tunnelPid;
fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
console.log("done — the site now answers with Gemini until the next `node local-ask/up.mjs`.");
