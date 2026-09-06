"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import type { VizNode, VizLink } from "@/lib/types";
import {
  retrieveWithMeta,
  suggestQuestions,
  type Snippet,
  type RetrievalResult,
} from "@/lib/retrieval";
import "./AskGraph.css";

// AskGraph — the "Ask" tab. Type a question → lib/retrieval.ts picks the best
// stored signals / contracts in the browser → /api/ask streams Claude's answer,
// which may only use those snippets and must cite them as [n]. Each [n] renders
// as a chip that reveals the underlying snippet (company clickable → NodePanel),
// and "Context used" lists everything that was sent. The last 5 Q&As stay in
// component state only — nothing is persisted, nothing is sent except the
// question and the snippets.

type Status = "loading" | "streaming" | "done" | "error";

interface Turn {
  id: number;
  question: string;
  meta: RetrievalResult; // snippets + what the question parser recognised
  answer: string;
  status: Status;
  error?: string;
  model?: string;
  usage?: { input_tokens: number; output_tokens: number };
  stopReason?: string | null;
}

const MAX_TURNS = 5;

export default function AskGraph({
  nodes,
  links,
  onOpen,
}: {
  nodes: VizNode[];
  links: VizLink[];
  onOpen: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [setupNeeded, setSetupNeeded] = useState(false);
  const ctrlRef = useRef<AbortController | null>(null);
  const nextId = useRef(1);

  const suggestions = useMemo(() => suggestQuestions(nodes), [nodes]);

  // Leaving the tab mid-answer: cancel the request instead of leaking it.
  useEffect(() => () => ctrlRef.current?.abort(), []);

  const patch = (id: number, fn: (t: Turn) => Turn) =>
    setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));

  async function ask(raw: string) {
    const question = raw.trim();
    if (!question || busy) return;

    // 1) Retrieval happens here, in the browser, against the graph we already have.
    const meta = retrieveWithMeta(question, nodes, links);
    const id = nextId.current++;
    const turn: Turn = { id, question, meta, answer: "", status: "loading" };
    setTurns((ts) => [turn, ...ts].slice(0, MAX_TURNS));
    setQ("");

    // Nothing matched → say so locally; no point paying for a model call.
    if (meta.snippets.length === 0) {
      patch(id, (t) => ({ ...t, status: "done", answer: noMatchMessage(meta) }));
      return;
    }

    // 2) Ask the server route, which holds the API key, and stream the answer.
    setBusy(true);
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question, snippets: meta.snippets }),
        signal: ctrl.signal,
      });
      if (!res.ok) {
        const j: any = await res.json().catch(() => ({}));
        if (res.status === 503 && j?.code === "no_api_key") setSetupNeeded(true);
        throw new Error(j?.error || `Request failed (${res.status})`);
      }
      if (!res.body) throw new Error("The server sent an empty response.");

      // The route answers with one JSON object per line (NDJSON).
      const handleLine = (line: string) => {
        let ev: any;
        try {
          ev = JSON.parse(line);
        } catch {
          return;
        }
        if (ev.type === "text") {
          patch(id, (t) => ({ ...t, status: "streaming", answer: t.answer + ev.text }));
        } else if (ev.type === "done") {
          patch(id, (t) => ({
            ...t,
            status: "done",
            model: ev.model,
            usage: ev.usage,
            stopReason: ev.stop_reason ?? null,
          }));
        } else if (ev.type === "error") {
          // Keep whatever text already arrived; only flag a hard error if there is none.
          patch(id, (t) => ({ ...t, status: t.answer ? "done" : "error", error: ev.error }));
        }
      };

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl: number;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (line) handleLine(line);
        }
      }
      if (buf.trim()) handleLine(buf.trim());
      // A stream that ended without a "done" line still counts as finished.
      patch(id, (t) => (t.status === "done" || t.status === "error" ? t : { ...t, status: "done" }));
    } catch (e: any) {
      if (e?.name === "AbortError") return;
      patch(id, (t) => ({ ...t, status: "error", error: e?.message || String(e) }));
    } finally {
      if (ctrlRef.current === ctrl) ctrlRef.current = null;
      setBusy(false);
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    ask(q);
  };

  return (
    <div className="ask">
      <h3>💬 Ask the Graph</h3>
      <p className="caption ask-intro">
        Ask in plain English. The answer is written only from the signals and contracts stored
        in this graph (transcript-grounded data) — every claim is cited to its source label, and
        when the graph does not contain the answer it says so. No outside knowledge is used.
      </p>

      {setupNeeded && <SetupNotice />}

      <form className="ask-form" onSubmit={onSubmit}>
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. Who supplies HBM4 for NVIDIA Vera Rubin?"
          maxLength={500}
          disabled={busy}
          aria-label="Your question"
          autoComplete="off"
        />
        <button type="submit" className="btn ask-send" disabled={busy || !q.trim()}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </form>

      {suggestions.length > 0 && (
        <div className="ask-chips" aria-label="Suggested questions">
          {suggestions.map((s) => (
            <button key={s} type="button" className="ask-chip" disabled={busy} onClick={() => ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      {turns.length > 0 && (
        <div className="ask-thread" aria-live="polite">
          <div className="ask-thread-head">
            <span className="caption">
              Last {turns.length} of up to {MAX_TURNS} questions — kept only while this tab is open.
            </span>
            <button
              type="button"
              className="copy-btn ask-clear"
              onClick={() => {
                ctrlRef.current?.abort();
                setTurns([]);
              }}
            >
              Clear
            </button>
          </div>
          {turns.map((t) => (
            <TurnView key={t.id} turn={t} onOpen={onOpen} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── One question + its answer ──────────────────────────────────────────────

function TurnView({ turn, onOpen }: { turn: Turn; onOpen: (id: string) => void }) {
  const [active, setActive] = useState<number | null>(null); // which [n] chip is open
  const { snippets, companies, chains, topics } = turn.meta;
  const activeSnippet = active !== null ? snippets[active - 1] : undefined;

  const matched: ReactNode[] = [];
  if (companies.length) matched.push(<span key="c"><b>{companies.join(", ")}</b></span>);
  if (chains.length) matched.push(<span key="ch">chains: {chains.join(", ")}</span>);
  if (topics.length) matched.push(<span key="t">topics: {topics.join(", ")}</span>);

  return (
    <article className="ask-turn">
      <p className="ask-q">{turn.question}</p>
      <div className="ask-match">
        {snippets.length} snippet{snippets.length === 1 ? "" : "s"} matched
        {matched.length > 0 && <> · </>}
        {matched.map((m, i) => (
          <span key={i}>
            {i > 0 && " · "}
            {m}
          </span>
        ))}
      </div>

      {turn.status === "loading" && <div className="ask-thinking">Reading the graph…</div>}

      {turn.answer && (
        <div className="ask-a">
          <AnswerBody
            text={turn.answer}
            count={snippets.length}
            active={active}
            onCite={(n) => setActive(active === n ? null : n)}
            streaming={turn.status === "streaming"}
          />
        </div>
      )}

      {turn.error && <div className="ask-err">⚠ {turn.error}</div>}

      {activeSnippet && (
        <SnippetView s={activeSnippet} n={active as number} onOpen={onOpen} highlight />
      )}

      {(turn.status === "done" || turn.status === "error") && (
        <div className="ask-foot">
          {turn.usage && (
            <span>
              {turn.model || "model"} · {turn.usage.input_tokens.toLocaleString()} in /{" "}
              {turn.usage.output_tokens.toLocaleString()} out tokens
            </span>
          )}
          {turn.stopReason === "max_tokens" && <span>· answer cut at the token limit</span>}
          {turn.stopReason === "refusal" && <span>· the model declined to answer this</span>}
        </div>
      )}

      {snippets.length > 0 && (
        <details className="ask-context">
          <summary>Context used — {snippets.length} snippets sent to the model</summary>
          <ol>
            {snippets.map((s, i) => (
              <li key={i}>
                <SnippetView s={s} n={i + 1} onOpen={onOpen} />
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}

// ── One snippet (used for the open citation and the context list) ──────────

function SnippetView({
  s,
  n,
  onOpen,
  highlight,
}: {
  s: Snippet;
  n: number;
  onOpen: (id: string) => void;
  highlight?: boolean;
}) {
  return (
    <div className={"ask-snip" + (highlight ? " on" : "")}>
      <div className="ask-snip-head">
        <span className="ask-n">[{n}]</span>
        <span className={"ask-kind " + s.kind}>{s.kind}</span>
        <button type="button" className="ask-co" onClick={() => onOpen(s.company)} title={`Open ${s.company}`}>
          {s.company}
        </button>
        {s.target && (
          <>
            <span>→</span>
            <button type="button" className="ask-co" onClick={() => onOpen(s.target!)} title={`Open ${s.target}`}>
              {s.target}
            </button>
          </>
        )}
        {s.chain && <span className="ask-chain">· {s.chain.replace(/_/g, " ")}</span>}
        <span className="ask-label">· {s.label}</span>
      </div>
      <div className="ask-snip-text">{s.text}</div>
    </div>
  );
}

// ── Answer rendering: paragraphs, "- " bullets, **bold**, [n] citation chips ──

// [3]  [2, 5]  [2-4]  — one or more snippet numbers inside square brackets.
const INLINE_RE = /(\*\*[^*]+\*\*|\[\d{1,2}(?:\s*[,\-–]\s*\d{1,2})*\])/g;

/** "2, 4-6" → [2, 4, 5, 6], keeping only numbers that exist in the context list. */
function citeNumbers(inner: string, count: number): number[] {
  const out: number[] = [];
  for (const part of inner.split(",")) {
    const range = /^\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\s*$/.exec(part);
    if (range) {
      const a = +range[1];
      const b = +range[2];
      if (b >= a && b - a < 10) for (let x = a; x <= b; x++) out.push(x);
    } else {
      const x = parseInt(part, 10);
      if (!isNaN(x)) out.push(x);
    }
  }
  return out.filter((x) => x >= 1 && x <= count);
}

function AnswerBody({
  text,
  count,
  active,
  onCite,
  streaming,
}: {
  text: string;
  count: number;
  active: number | null;
  onCite: (n: number) => void;
  streaming: boolean;
}) {
  // Inline pass: bold and citations. `key` seeds keep React keys unique per block.
  const inline = (s: string, key: string): ReactNode[] =>
    s.split(INLINE_RE).map((part, i) => {
      if (!part) return null;
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={key + i}>{inline(part.slice(2, -2), key + i + "b")}</strong>;
      if (part.startsWith("[")) {
        const nums = citeNumbers(part.slice(1, -1), count);
        if (!nums.length) return <span key={key + i}>{part}</span>; // not a valid citation
        return (
          <span key={key + i} className="ask-cites">
            {nums.map((n) => (
              <button
                key={n}
                type="button"
                className={"ask-cite" + (active === n ? " on" : "")}
                onClick={() => onCite(n)}
                title={`Show snippet ${n}`}
              >
                {n}
              </button>
            ))}
          </span>
        );
      }
      return <span key={key + i}>{part}</span>;
    });

  // Block pass: blank line = paragraph break, "- " lines = one bullet list.
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (!list.length) return;
    const k = "ul" + blocks.length;
    blocks.push(
      <ul key={k}>
        {list.map((li, i) => (
          <li key={i}>{inline(li, k + i)}</li>
        ))}
      </ul>
    );
    list = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    const bullet = /^[-•*]\s+(.*)$/.exec(line);
    if (bullet) {
      list.push(bullet[1]);
      continue;
    }
    flush();
    const k = "p" + blocks.length;
    blocks.push(<p key={k}>{inline(line.replace(/^#+\s*/, ""), k)}</p>);
  }
  flush();

  return (
    <>
      {blocks}
      {streaming && <span className="ask-cursor" aria-hidden="true" />}
    </>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function noMatchMessage(meta: RetrievalResult): string {
  if (meta.companies.length)
    return (
      `The graph has a node for ${meta.companies.join(", ")} but no stored signals or contracts ` +
      `matched this question, so there is nothing to answer from yet. Enrich its latest earnings call ` +
      `or filing to fill this in.`
    );
  return (
    "No stored signal or contract matched this question, so there is nothing to answer from. " +
    "Try naming a company (SK Hynix, TSMC, Vertiv…) or a product generation " +
    "(Vera Rubin, B200, MI450 Helios, TPU v8, Trainium3), or a topic like HBM, CoWoS, CPO or transformers."
  );
}

function SetupNotice() {
  return (
    <div className="ask-setup" role="status">
      <b>Ask the Graph needs a server-side model API key — none is configured yet.</b>
      <ol>
        <li>
          <b>Free option (recommended):</b> create a Gemini API key at <code>aistudio.google.com</code>{" "}
          (free tier, no card) and set <code>GEMINI_API_KEY</code>. Also free: Groq at{" "}
          <code>console.groq.com</code> → <code>GROQ_API_KEY</code>. Paid: Anthropic at{" "}
          <code>console.anthropic.com</code> → <code>ANTHROPIC_API_KEY</code>. Any other
          OpenAI-compatible service: <code>ASK_BASE_URL</code> + <code>ASK_API_KEY</code>{" "}
          (+ optional <code>ASK_MODEL</code>).
        </li>
        <li>
          On Vercel: open the project → <b>Settings → Environment Variables</b> → add the variable
          for Production and Preview → <b>Deployments → Redeploy</b>.
        </li>
        <li>
          Locally: put the same line (e.g. <code>GEMINI_API_KEY=…</code>) in <code>web/.env</code>{" "}
          (already git-ignored) and restart <code>npm run dev</code>.
        </li>
      </ol>
      The key never leaves the server — the browser only sends the question and the snippets.
      Every other tab works without it.
    </div>
  );
}
