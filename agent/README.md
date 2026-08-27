# Transcript Signal Agent

A tool-using LLM agent that reads an earnings-call document and emits a **structured,
quote-grounded signal card**, plus an evaluation harness that scores it against
labels a human produced independently.

Read-only with respect to the rest of the repo: it reads `transcripts/`,
`quant/*.csv` and `graph/merged_graph.json`, and writes only under `agent/out/`.

---

## Why the evaluation is real

The project owner had already hand-classified every US-listed earnings call in the
graph for one binary signal — "did this company say its own capacity is full?" —
recording an evidence quote and a written ruling per company
(`quant/signal_full_capacity.csv`, 17 positives out of 71 calls).

That is a gold set that predates the agent, so it cannot have been fitted to it.
`agent/eval/gold.py` joins it to the source documents through the project's canonical
source-label format; **70 of 71 calls resolve to a full transcript** (Corning Q1 FY2026
has no transcript in the corpus).

The agent's `capacity_status == "sold_out"` is defined to mean exactly what the
owner's `flag = 1` meant, so the two are directly comparable.

---

## Results (70 gold calls, 17 positive)

| arm | model | P | R | F1 | F1 95% CI | kappa | grounding | $/doc | p50 latency |
|---|---|---|---|---|---|---|---|---|---|
| agent | claude-opus-5 | 0.667 | **0.824** | **0.737** | [0.55, 0.88] | 0.640 | **100%** | $0.128 | 22.1 s |
| single call | claude-opus-5 | 0.667 | 0.706 | 0.686 | [0.48, 0.84] | 0.581 | **100%** | $0.098 | 9.8 s |
| regex | — | 0.667 | 0.706 | 0.686 | [0.48, 0.84] | 0.581 | n/a | $0.000 | 0.0 s |

Reproduce with `python -X utf8 -m agent.eval.evaluate` (scores cached runs; no API calls).

### What the numbers say

**A twelve-line regex is a strong baseline, and one LLM call does not beat it.**
`single_call` and `regex` land on identical precision, recall and F1. They are not
making the same mistakes — only 4 of ~11 errors overlap — but neither is better.
Reporting this rather than burying it is the point: an LLM that ties a keyword rule
has not earned its cost on this task.

**The tool loop is where the lift is.** Searching the document and self-checking
quotes moves recall 0.706 → 0.824 at unchanged precision. The confidence intervals
overlap heavily at N=70, so this is a lead, not a proven gap.

**No hallucinated quotes.** Across 70 documents, every required quote from both model
arms was found verbatim in the source (`grounding = 100%`, repair rate 0%). The
verifier is not decorative — it catches invented and stitched-together quotes in unit
tests, and the model's own `verify_quote` tool is available to it mid-run.

**The residual errors are mostly label boundary, not model error.** Two of the
agent's three false negatives are calls the owner approved by stretching the
definition ("approved (terse wording)", "approved (input-driven)"). Of the 17
positives, 11 are ruled `clear` and 6 are case-by-case stretches.

**The gold set has a coverage ceiling.** The owner labelled from chain
`quarterly_data` — an already-summarised layer — while the agent reads the raw
transcript. Checking the agent's 7 false positives against the graph text: **none of
their quotes appear there at all**, and for 3 of 7 no sold-out-style wording exists in
the graph for that company, so the human never had a candidate to rule on. Raw F1
therefore understates the agent. (Tested and rejected: widening the positive class to
`sold_out OR tight` to match a looser reading of the owner's intent makes things much
worse — F1 0.508, kappa 0.238.)

---

## The four arms

The arms exist to separate two things that are easy to confound — how much text the
model sees, and whether it gets to act:

| arm | what it reads | agency |
|---|---|---|
| `regex` | whole document | none (keyword rules) |
| `single_call` | whole document | none |
| `retrieval_single` | BM25-selected passages | none |
| `agent` | passages it chooses | searches, verifies its own quotes |

`single_call → retrieval_single` isolates the cost of retrieval.
`retrieval_single → agent` isolates what agency adds on top. Without the middle arm
those two effects are inseparable.

### Retrieval has a measurable ceiling

`retrieval_single` can only cite what we put in front of it, so before scoring it,
measure what retrieval throws away. Ground truth is the 296 quotes the full-reading
agent produced, all of which the verifier confirmed appear verbatim in the source:

| top_k | budget | median ctx words | quote recall | capacity-field recall |
|---|---|---|---|---|
| 3 | 2600 | 2510 | 71% | 79% |
| 4 | 3200 | 3130 | 78% | 85% |
| **5** | **4000** | **3841** | **85%** | **89%** |
| 6 | 5000 | 4310 | 90% | 93% |
| 8 | 7000 | 5234 | 95% | 95% |
| 12 | — | 6321 | 99% | 98% |

The median document is 7,635 words, so the chosen setting halves the prefill for an
11-point recall loss on the scored field. That loss is a hard ceiling on the arm — no
model can cite evidence that was never shown to it. Reproduce with
`python -X utf8 -m agent.eval.retrieval_curve`.

---

## Running a local model (no API key)

`agent/local_provider.py` sends the same prompt and the same passages to an Ollama
model on this machine, and the result goes through the same verifier and the same
scorer. Hardware here: Ryzen 7 7730U, 8 cores, 15.4 GB RAM, **no discrete GPU** —
measured throughput ~30 tok/s prefill, ~3 tok/s generation. That is why only the
retrieval arm is viable locally: the full-document arm would be a 5-hour run.

### Constrained decoding guarantees the shape and destroys the content

Ollama constrains sampling to the JSON schema, so a local model returns a structurally
perfect `SignalCard`. It was also, at first, **completely empty** — all five fields
`not_stated`, confidence 0.0, on documents that plainly discuss capacity and demand.
Valid JSON, zero information, no error raised anywhere. That is the failure mode worth
knowing about: structured output fails *silently*, and nothing in a schema check
catches it.

The cause is decoding order. Constrained sampling starts emitting the answer at token
one, so the model commits to an enum before it has looked at anything. Four measured
attempts to fix it, all on the same documents:

| setup | outcome |
|---|---|
| `qwen3:8b`, plain schema, thinking off | valid JSON, **0 / 5 fields**, 39 s |
| `qwen3:8b`, plain schema, thinking **on** | valid JSON, **0 / 5 fields**, 432 s |
| `qwen3:8b`, free-text field emitted first | **3 / 5**, every quote verified, 88 s |
| `qwen3:4b`, free-text field emitted first | **runaway** — see below |

More reasoning did not help: 11× the latency for the same empty card. Somewhere to
*put* the reasoning did. So the fix is a leading free-text field (prompt version
`v1_scratch`), stripped again before validation so the scored object is unchanged.

**The same fix breaks on a smaller model, and it breaks loudly.** `qwen3:4b` treats an
open scratchpad as unbounded chain-of-thought — it narrated the passages one by one
("Passage 0: … Passage 1: …"), spent all 1,500 output tokens, and stopped
(`done_reason=length`) before emitting a single answer field, leaving JSON that never
closed. Constrained decoding cannot produce malformed JSON, but it can be *cut off*
producing it, which looks identical from the outside. `local_provider.py` now reports
`done_reason` on a parse failure so the two are distinguishable.

Capping the scratchpad (`maxLength` in the schema, which the sampler enforces) got 4b
to reach the answer fields. The answers were still not usable: it labelled ASE Group
`sold_out` and cited *"Blended factory utilization ~80%"* — a real, verbatim quote that
does not support the label. **Grounding 100%, answer wrong.** Which is the point of
keeping the two metrics apart: a verifier proves a quote exists, never that it means
what the model claimed.

Net: on this hardware a local 8B is the floor for producing anything usable, a 4B is
below it, and the useful output of the local track is this diagnosis rather than a
score. The `qwen3:8b` full-gold-set cell (~208 s/document, ~4 hours) is left in
`eval/ablate.py` for a machine with a GPU.

---

## Design

```
corpus.py    documents on disk <-> the project's canonical source labels
chunker.py   paragraph-aware chunking + BM25 ranking (written out, not imported)
retrieval.py fixed per-field queries -> the passages the retrieval arm sees
tools.py     the two tools: search_transcript, verify_quote  (thread-local state)
schema.py    SignalCard: 5 closed enums, each with a REQUIRED verbatim quote
prompts.py   versioned prompt text + the repair message
extractor.py the three model arms and the shared verify -> repair -> record driver
local_provider.py  Ollama: constrained decoding, usage and CPU timing
baselines.py the regex lower bound
verify.py    the anti-hallucination check
run_extract.py  CLI: run an arm over documents, cache every result
eval/gold.py    build the gold set from the owner's existing labels
eval/evaluate.py score every cached run; bootstrap CI, kappa, cost, latency
eval/retrieval_curve.py  what each context budget throws away
eval/ablate.py  the experiment matrix, then scoring
```

Four decisions worth naming:

1. **Quotes are required by the schema, not by the prompt.** The first version used a
   free `evidence: Dict[str, Evidence]`; an empty dict validates, so the model
   silently returned zero quotes on the very first run. Pairing every judgement with
   a required `<field>_quote` sibling means the API will not accept an uncited answer.

2. **The repair loop offers a way out.** When a quote fails verification the model is
   told which one and why, and is explicitly permitted to downgrade the field to
   `not_stated`. Without that escape hatch, demanding a valid quote pushes a model
   toward inventing one — the opposite of what is being measured.

3. **Tool state is thread-local.** Extractions run in a thread pool; a module-level
   "active document" would let one worker's tools search another worker's transcript.
   That failure is silent — it produces quotes from the wrong company — so the
   isolation is covered by a concurrency test.

4. **No repair loop on the local path.** The repair turn works by appending the failed
   card and a complaint to the conversation. The Ollama call collapses to a single
   user string, so a repair there would be silently dropped rather than read. The
   local arm reports its unrepaired card instead of pretending to have repaired it.

### Lookahead bias

The model's pretraining may include what happened after any given call. Mitigations:
the prompt forbids outside knowledge, every non-`not_stated` field must carry a quote,
and each quote is re-checked against the document by our own code. This constrains but
does not eliminate the risk, and any downstream return study must say so.

---

## Running it

```bash
python -X utf8 -m agent.eval.gold                 # build the gold set from the owner's labels
python -X utf8 -m agent.run_extract --arm regex   # free, no API and no model

# frontier
python -X utf8 -m agent.run_extract --arm agent            --model claude-opus-5
python -X utf8 -m agent.run_extract --arm single_call      --model claude-opus-5
python -X utf8 -m agent.run_extract --arm retrieval_single --model claude-opus-5

# local (needs `ollama pull qwen3:4b`; single-threaded because one request saturates the CPU)
python -X utf8 -m agent.run_extract --arm retrieval_single --model qwen3:4b        --prompt v1_scratch --effort "" --workers 1

# or drive the whole matrix, then score
python -X utf8 -m agent.eval.ablate --dry-run
python -X utf8 -m agent.eval.ablate --only local --model qwen3:4b
python -X utf8 -m agent.eval.evaluate             # scores everything cached; no API calls
python -X utf8 -m agent.eval.retrieval_curve      # the context-budget curve
```

Results are cached per `(arm, model, prompt, effort, document)`, so re-scoring is free
and adding a model only pays for the new cells. `--all-docs` runs the full 221-document
corpus instead of the labelled subset.

## Not done yet

- **Haiku 4.5 and Sonnet 5 cells** (the frontier cost/quality axis) — the API credit
  balance ran out after the Opus runs (~$16). The cells are defined in
  `eval/ablate.py` and will run on a top-up without touching anything else.
- **`retrieval_single` on Claude.** The middle arm has only been run locally so far,
  so the retrieval-vs-agency decomposition is not yet closed on the frontier side.
- **A scored local row.** The local track produced a diagnosis, not a score: `qwen3:4b`
  is below the usable floor, and the `qwen3:8b` cell costs ~208 s/document (~4 hours
  for the gold set) on this CPU. Both cells stay in `eval/ablate.py` for a machine
  with a GPU; `--only local` runs them.
- Full 221-document extraction, `quant/signal_agent.csv`, and the downstream event
  study comparing the machine signal against the human one.
