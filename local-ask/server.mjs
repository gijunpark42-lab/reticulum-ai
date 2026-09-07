// server.mjs — the LOCAL answer engine for "Ask the Graph".
//
// A tiny HTTP server that answers a question from the snippets it is given by
// running the Claude Code CLI (`claude -p`) on this PC — Opus at max effort,
// with NO tools, so it can only use the snippets. The Vercel route
// (web/src/app/api/ask/route.ts) calls it through a tunnel when this machine is
// on, and silently falls back to Gemini when it is not. See README.md.
//
// Protocol (every request must carry the header  x-ask-secret: <ASK_SHARED_SECRET>):
//   GET  /health  → 200 { ok, model, effort, active, queued, uptime_s }
//   POST /answer  { question, snippets[], intent, lang, history } → 200 { answer, citations, model, model_id, cli_model, effort, latency_ms, cost_usd }
//                 (lang = "en" | "ko" answer language; history = earlier {question, answer} turns for follow-ups;
//                  model_id = the model the CLI really used, e.g. "claude-opus-5")
//   401 bad secret · 400 bad body · 429 queue full · 504 claude took too long · 500 claude failed
//
// Run it from inside the repo (it imports the shared prompt from web/src/lib):
//   cd local-ask && node server.mjs
//
// Built-in modules only — nothing to install.

import http from "node:http";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  LOCAL_MODEL_ID,
  normalizeIntent,
  normalizeLang,
  normalizeHistory,
  buildSystemPrompt,
  buildUserMessage,
  extractCitations,
} from "../web/src/lib/askPrompt.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

// ── Configuration ──────────────────────────────────────────────────────────
// Values come from local-ask/.env (copied from .env.example) or from real
// environment variables; a real environment variable always wins.
try {
  process.loadEnvFile(path.join(HERE, ".env"));
} catch {
  /* no .env file — fine, the variables may be set in the environment */
}

const SECRET = process.env.ASK_SHARED_SECRET || "";
const MODEL = process.env.ASK_MODEL || "opus"; // alias for the latest Opus
const EFFORT = process.env.ASK_EFFORT || "max"; // low | medium | high | xhigh | max
const MAX_BUDGET_USD = process.env.ASK_MAX_BUDGET_USD || "1"; // hard cap per question
const TIMEOUT_MS = Number(process.env.ASK_TIMEOUT_MS || 90_000); // kill claude after this
const CLAUDE_BIN = process.env.ASK_CLAUDE_BIN || "claude"; // path to the CLI if not on PATH
const HOST = process.env.HOST || "127.0.0.1"; // the tunnel connects locally; never expose directly
const PORT = Number(process.env.PORT || 8787);

const MAX_ACTIVE = 2; // simultaneous claude processes
const MAX_QUEUE = 5; // requests allowed to wait; more get 429
const LOG_DIR = path.join(HERE, "logs");
const LOG_FILE = path.join(LOG_DIR, "requests.jsonl");

// Input limits — the same ceilings as the Vercel route.
const MAX_BODY_BYTES = 200_000;
const MAX_QUESTION_CHARS = 500;
const MAX_SNIPPETS = 60;
const MAX_SNIPPET_TEXT = 2_000;
const MAX_TOTAL_TEXT = 20_000;
const MAX_FIELD = 160;

if (SECRET.length < 16) {
  console.error(
    "ASK_SHARED_SECRET is missing or shorter than 16 characters. Put one in local-ask/.env, e.g.\n" +
      "  ASK_SHARED_SECRET=<paste the output of the next line>\n" +
      "  node -e \"console.log(require('crypto').randomBytes(24).toString('hex'))\"\n" +
      "and set the SAME value as ASK_SHARED_SECRET on Vercel."
  );
  process.exit(1);
}

fs.mkdirSync(LOG_DIR, { recursive: true });

// ── Logging ────────────────────────────────────────────────────────────────

/** Append one JSON line to logs/requests.jsonl (never the secret). */
function logLine(entry) {
  const line = JSON.stringify({ ts: new Date().toISOString(), ...entry });
  fs.appendFile(LOG_FILE, line + "\n", () => {});
}

// ── The queue: at most MAX_ACTIVE claude processes, MAX_QUEUE waiting ──────
// Each request must "acquire a slot" before it may start claude. If a slot is
// free it starts at once; otherwise it waits in line (FIFO); if the line is
// already MAX_QUEUE long it is refused with 429 immediately.

let active = 0;
const waiting = []; // { resolve, reject } in arrival order

function acquireSlot(res) {
  return new Promise((resolve, reject) => {
    if (active < MAX_ACTIVE) {
      active++;
      resolve();
      return;
    }
    if (waiting.length >= MAX_QUEUE) {
      reject(Object.assign(new Error(`busy: ${MAX_QUEUE} questions already waiting`), { status: 429 }));
      return;
    }
    const entry = { resolve, reject };
    waiting.push(entry);
    // The caller went away while waiting → leave the line quietly.
    res.on("close", () => {
      const i = waiting.indexOf(entry);
      if (i >= 0) {
        waiting.splice(i, 1);
        reject(Object.assign(new Error("client left the queue"), { status: 499 }));
      }
    });
  });
}

/** Hand the slot to the next waiter, or free it. */
function releaseSlot() {
  const next = waiting.shift();
  if (next) next.resolve(); // the slot passes straight on: `active` is unchanged
  else active--;
}

// ── Running claude ─────────────────────────────────────────────────────────

/** The exact command line, for the banner and the README. */
function claudeArgs(systemPrompt) {
  return [
    "-p", // print mode: answer and exit
    "--safe-mode", // ignore this PC's CLAUDE.md / hooks / MCP / plugins / skills
    "--tools", "", // NO tools — the answer must come from the snippets alone
    "--no-session-persistence", // do not write a session file for every question
    "--model", MODEL,
    "--effort", EFFORT,
    "--output-format", "json", // one JSON object on stdout
    "--max-budget-usd", MAX_BUDGET_USD,
    "--system-prompt", systemPrompt,
  ];
}

/**
 * Spawn `claude -p` with the system prompt as an argument and the user message
 * on stdin (a command line is capped at ~32k characters on Windows; the
 * snippets can be 20k on their own). Resolves with what the CLI reported —
 * it never rejects; failures come back as { ok: false, reason }.
 */
function runClaude(systemPrompt, userMessage, onSpawn) {
  return new Promise((resolve) => {
    // Without these two deletions the CLI refuses to start when this server
    // was itself launched from inside a Claude Code session.
    const env = { ...process.env };
    delete env.CLAUDECODE;
    delete env.CLAUDE_CODE_ENTRYPOINT;

    const started = Date.now();
    let child;
    try {
      child = spawn(CLAUDE_BIN, claudeArgs(systemPrompt), {
        env,
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
        // An npm shim (claude.cmd) can only be started through the shell; the
        // native claude.exe must not be.
        shell: /\.cmd$/i.test(CLAUDE_BIN),
      });
    } catch (e) {
      resolve({ ok: false, status: 500, reason: `could not start ${CLAUDE_BIN}: ${e.message}`, exit_code: null, duration_ms: 0 });
      return;
    }
    onSpawn(child);

    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let settled = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL"); // TerminateProcess on Windows
    }, TIMEOUT_MS);

    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", (e) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ok: false, status: 500, reason: `could not start ${CLAUDE_BIN}: ${e.message}`, exit_code: null, duration_ms: Date.now() - started });
    });
    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const duration_ms = Date.now() - started;
      if (timedOut) {
        resolve({ ok: false, status: 504, reason: `claude exceeded ${TIMEOUT_MS} ms and was stopped`, exit_code: code, duration_ms, stderr });
        return;
      }
      // The CLI prints ONE JSON object; be tolerant of a stray line before it.
      let result = null;
      const lines = stdout.trim().split("\n");
      for (let i = lines.length - 1; i >= 0 && result === null; i--) {
        if (!lines[i].startsWith("{")) continue;
        try {
          result = JSON.parse(lines[i]);
        } catch {
          /* not that line */
        }
      }
      if (result === null) {
        try {
          result = JSON.parse(stdout);
        } catch {
          /* no JSON at all */
        }
      }
      if (!result) {
        resolve({ ok: false, status: 500, reason: `claude exited with code ${code} and no JSON result`, exit_code: code, duration_ms, stderr });
        return;
      }
      const success = result.type === "result" && result.subtype === "success" && result.is_error === false;
      const answer = typeof result.result === "string" ? result.result.trim() : "";
      if (!success || !answer) {
        const why = result.subtype || (result.is_error ? "is_error" : "empty answer");
        resolve({ ok: false, status: 500, reason: `claude reported ${why}`, exit_code: code, duration_ms, stderr, cost_usd: result.total_cost_usd ?? null });
        return;
      }
      // Which model actually wrote the answer? The CLI's usage report lists every
      // model it touched (a small helper model may appear too); the one with the
      // most output tokens is the author. "opus" is only an alias.
      let modelId = null;
      let most = -1;
      const usage = result.modelUsage && typeof result.modelUsage === "object" ? result.modelUsage : {};
      for (const [id, u] of Object.entries(usage)) {
        const out = Number(u && u.outputTokens) || 0;
        if (out > most) {
          most = out;
          modelId = id;
        }
      }
      resolve({
        ok: true,
        answer,
        modelId,
        exit_code: code,
        duration_ms,
        cost_usd: typeof result.total_cost_usd === "number" ? result.total_cost_usd : null,
      });
    });

    child.stdin.on("error", () => {}); // the child may exit before reading everything
    child.stdin.end(userMessage);
  });
}

// ── HTTP plumbing ──────────────────────────────────────────────────────────

function send(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "content-length": Buffer.byteLength(body) });
  res.end(body);
}

/** Constant-time comparison so the secret cannot be guessed letter by letter. */
function secretOk(req) {
  const given = req.headers["x-ask-secret"];
  if (typeof given !== "string" || given.length !== SECRET.length) return false;
  return crypto.timingSafeEqual(Buffer.from(given), Buffer.from(SECRET));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        reject(Object.assign(new Error("Request too large."), { status: 413 }));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

const str = (v, max) => (typeof v === "string" && v.length <= max ? v : null);

/** Returns { question, snippets, intent } or a string saying what is wrong. */
function parseAnswerBody(raw) {
  let b;
  try {
    b = JSON.parse(raw);
  } catch {
    return "Body is not valid JSON.";
  }
  if (!b || typeof b !== "object") return "Body must be a JSON object.";
  const question = typeof b.question === "string" ? b.question.trim() : "";
  if (!question) return "Missing 'question'.";
  if (question.length > MAX_QUESTION_CHARS) return `Question is too long (max ${MAX_QUESTION_CHARS} characters).`;
  if (!Array.isArray(b.snippets)) return "Missing 'snippets' array.";
  if (b.snippets.length > MAX_SNIPPETS) return `Too many snippets (max ${MAX_SNIPPETS}).`;
  const snippets = [];
  let total = 0;
  for (const s of b.snippets) {
    if (!s || typeof s !== "object") return "Each snippet must be an object.";
    const kind = s.kind === "signal" || s.kind === "contract" ? s.kind : null;
    const company = str(s.company, MAX_FIELD);
    const chain = str(s.chain, MAX_FIELD);
    const label = str(s.label, MAX_FIELD);
    const date = str(s.date, 20);
    const text = str(s.text, MAX_SNIPPET_TEXT);
    if (!kind || company === null || chain === null || label === null || date === null || text === null)
      return "A snippet has a missing or oversized field.";
    const target = s.target === undefined ? undefined : str(s.target, MAX_FIELD);
    if (target === null) return "A snippet has an invalid 'target'.";
    const topics = Array.isArray(s.topics) ? s.topics.filter((t) => typeof t === "string").slice(0, 10) : undefined;
    total += text.length;
    if (total > MAX_TOTAL_TEXT) return `Snippet text exceeds ${MAX_TOTAL_TEXT} characters in total.`;
    snippets.push({ kind, company, target, chain, label, date, text, topics });
  }
  return {
    question,
    snippets,
    intent: normalizeIntent(b.intent),
    lang: normalizeLang(b.lang),
    history: normalizeHistory(b.history),
  };
}

// ── Handlers ───────────────────────────────────────────────────────────────

const startedAt = Date.now();

function handleHealth(res) {
  send(res, 200, {
    ok: true,
    model: MODEL,
    effort: EFFORT,
    active,
    queued: waiting.length,
    uptime_s: Math.round((Date.now() - startedAt) / 1000),
  });
}

async function handleAnswer(req, res) {
  const t0 = Date.now();
  let raw;
  try {
    raw = await readBody(req);
  } catch (e) {
    send(res, e.status || 400, { error: e.message });
    return;
  }
  const parsed = parseAnswerBody(raw);
  if (typeof parsed === "string") {
    send(res, 400, { error: parsed });
    return;
  }
  const { question, snippets, intent, lang, history } = parsed;
  const short = question.length > 80 ? question.slice(0, 77) + "…" : question;

  // Wait for a slot (or be refused).
  try {
    await acquireSlot(res);
  } catch (e) {
    if (e.status === 429) {
      send(res, 429, { error: e.message });
      logLine({ question, intent, snippets: snippets.length, queued_ms: Date.now() - t0, latency_ms: Date.now() - t0, exit_code: null, ok: false, error: "queue full" });
    }
    return; // 499: the client is gone, nothing to send
  }
  const queued_ms = Date.now() - t0;
  console.log(`→ "${short}" (${snippets.length} snippets, intent ${intent}, lang ${lang}, ${history.length} earlier turns, waited ${queued_ms} ms)`);

  let child = null;
  let finished = false;
  // The Vercel route gives up after ~60 s; when it hangs up, stop paying for the answer.
  res.on("close", () => {
    if (!finished && child) child.kill("SIGKILL");
  });

  const system = buildSystemPrompt(intent, lang);
  const user = buildUserMessage(question, snippets, intent, history);
  let r;
  try {
    r = await runClaude(system, user, (c) => (child = c));
  } finally {
    finished = true;
    releaseSlot();
  }

  const latency_ms = Date.now() - t0;
  if (!r.ok) {
    console.log(`✗ "${short}" → ${r.status} ${r.reason} (${latency_ms} ms)`);
    logLine({ question, intent, lang, snippets: snippets.length, queued_ms, latency_ms, exit_code: r.exit_code, ok: false, error: r.reason, stderr: (r.stderr || "").slice(0, 500), cost_usd: r.cost_usd ?? null });
    if (!res.writableEnded) send(res, r.status, { error: r.reason });
    return;
  }
  const citations = extractCitations(r.answer, snippets.length);
  console.log(`✓ "${short}" → ${r.answer.length} chars, cites [${citations.join(", ")}], ${r.modelId || MODEL} · effort ${EFFORT}, ${latency_ms} ms, $${r.cost_usd ?? "?"}`);
  logLine({ question, intent, lang, snippets: snippets.length, queued_ms, latency_ms, exit_code: r.exit_code, ok: true, model_id: r.modelId, cost_usd: r.cost_usd });
  if (!res.writableEnded)
    send(res, 200, {
      answer: r.answer,
      citations,
      model: LOCAL_MODEL_ID,
      model_id: r.modelId, // e.g. "claude-opus-5" — what the badge shows
      cli_model: MODEL, // the alias given to the CLI ("opus")
      effort: EFFORT,
      latency_ms,
      cost_usd: r.cost_usd,
    });
}

// ── The server ─────────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  if (!secretOk(req)) {
    send(res, 401, { error: "unauthorized" });
    return;
  }
  try {
    if (req.method === "GET" && url.pathname === "/health") handleHealth(res);
    else if (req.method === "POST" && url.pathname === "/answer") await handleAnswer(req, res);
    else send(res, 404, { error: "not found" });
  } catch (e) {
    console.error("unexpected error:", e);
    if (!res.writableEnded) send(res, 500, { error: "internal error" });
  }
});

server.listen(PORT, HOST, () => {
  console.log(
    `local-ask listening on http://${HOST}:${PORT}  model=${MODEL} effort=${EFFORT} timeout=${TIMEOUT_MS}ms ` +
      `max_active=${MAX_ACTIVE} max_queue=${MAX_QUEUE} log=${LOG_FILE}`
  );
  console.log(`command: ${CLAUDE_BIN} ${claudeArgs("<system prompt>").join(" ")}   (user message on stdin)`);
  logLine({ event: "start", host: HOST, port: PORT, model: MODEL, effort: EFFORT, timeout_ms: TIMEOUT_MS });
});
