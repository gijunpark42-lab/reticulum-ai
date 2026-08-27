# extractor.py -- the agent itself, and the no-tool baseline it is measured against.
#
# ARM "agent"       : tool loop (search_transcript + verify_quote) -> structured output.
# ARM "single_call" : whole document in one prompt, no tools -> structured output.
#
# Both end in the SAME Pydantic schema, so their outputs are directly comparable.
# Everything else about them is identical (same rules, same model, same fields);
# the only difference is whether the model can search and self-check. That isolates
# what the agent machinery actually buys.
#
# Both arms also share the REPAIR step: after the model answers, we verify its quotes
# ourselves, and if any required quote is missing or fabricated we send the specific
# complaint back once. Crucially the repair message offers "not_stated" as a way out,
# so the model is never cornered into inventing a quote to satisfy us.

import os
import time

import anthropic
from dotenv import load_dotenv

from agent.corpus import Document
from agent.local_provider import complete_json, is_local_model
from agent.pricing import cost_usd
from agent.prompts import PROMPT_VERSIONS, repair_message
from agent.retrieval import select_context
from agent.schema import (ExtractionResult, SignalCard, json_schema_with_scratchpad,
                          strip_scratchpad)
from agent.tools import AGENT_TOOLS, ActiveDocument, set_active_document
from agent.verify import verify_card

load_dotenv()

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 8000
# A hard ceiling on the tool loop. Five fields x (search + verify) is ~10 calls, so
# 16 iterations is generous; hitting it means something went wrong, not a hard document.
MAX_ITERATIONS = 16
# How many times we are willing to hand the model its own bad evidence back.
MAX_REPAIRS = 1


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set (expected in .env).")
    return anthropic.Anthropic()


class _Usage:
    """Accumulates token usage across every turn, including repairs."""

    def __init__(self):
        self.input = self.output = self.cache_read = self.cache_write = 0
        self.prefill_s = self.generate_s = 0.0

    def add(self, usage) -> None:
        if usage is None:
            return
        self.input += getattr(usage, "input_tokens", 0) or 0
        self.output += getattr(usage, "output_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0
        # Only local runs report these; they stay 0.0 for API calls.
        self.prefill_s += getattr(usage, "prefill_s", 0.0) or 0.0
        self.generate_s += getattr(usage, "generate_s", 0.0) or 0.0


# --------------------------------------------------------------------------------
# One request, per arm. Each returns (card, error) and adds its usage to `usage`.
# --------------------------------------------------------------------------------

def _call_agent_arm(client, messages, model, effort, prompts, usage):
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=MAX_TOKENS,
        max_iterations=MAX_ITERATIONS,
        system=prompts["agent_system"],
        messages=messages,
        tools=AGENT_TOOLS,
        output_format=SignalCard,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        # The system prompt + tool schemas are identical for every document, so
        # caching that prefix pays for itself across a 221-document run.
        cache_control={"type": "ephemeral"},
    )
    # Iterate rather than calling until_done(), so usage from EVERY turn of the
    # loop is counted -- not just the last message.
    last = None
    for message in runner:
        usage.add(getattr(message, "usage", None))
        last = message
    card = getattr(last, "parsed_output", None)
    return card, ("" if card is not None else "no parsed output from the tool runner")


def _call_retrieval_arm(client, messages, model, effort, prompts, usage):
    """Retrieved passages, one request. Runs on Claude OR on a local Ollama model.

    The dispatch is by model id -- anything not named claude-* goes to Ollama. Both
    paths send the SAME system prompt and the SAME passages and are validated by the
    SAME Pydantic model, so the only difference between the cells is the model itself.
    """
    if is_local_model(model):
        parsed, local_usage, error = complete_json(
            model=model,
            system=prompts["retrieval_system"],
            # Ollama takes a single user string, so the roles collapse; the content
            # is identical to what the Claude path sends.
            user=messages[-1]["content"],
            json_schema=(json_schema_with_scratchpad() if prompts.get("scratchpad")
                         else SignalCard.model_json_schema()),
        )
        usage.add(local_usage)
        if parsed is None:
            return None, error
        try:
            return SignalCard.model_validate(strip_scratchpad(parsed)), ""
        except Exception as exc:                   # noqa: BLE001
            # Constrained decoding guarantees the SHAPE, not the semantics (e.g. a
            # confidence outside 0..1). Surface it instead of dropping the document.
            return None, f"schema validation failed: {type(exc).__name__}: {exc}"

    response = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=prompts["retrieval_system"],
        messages=messages,
        output_format=SignalCard,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )
    usage.add(getattr(response, "usage", None))
    card = getattr(response, "parsed_output", None)
    return card, ("" if card is not None else "no parsed output returned")


def _call_single_arm(client, messages, model, effort, prompts, usage):
    response = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=prompts["single_system"],
        messages=messages,
        output_format=SignalCard,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )
    usage.add(getattr(response, "usage", None))
    card = getattr(response, "parsed_output", None)
    return card, ("" if card is not None else "no parsed output returned")


# --------------------------------------------------------------------------------
# The shared driver: first attempt -> verify -> optional repair -> record metrics.
# --------------------------------------------------------------------------------

def _run(arm: str, document: Document, label: str, model: str,
         effort: str, prompt_version: str) -> ExtractionResult:
    prompts = PROMPT_VERSIONS[prompt_version]
    text = document.read()
    result = ExtractionResult(doc_path=document.path, source_label=label,
                              arm=arm, model=model, prompt_version=prompt_version,
                              effort=effort)

    if arm == "agent":
        call = _call_agent_arm
        messages = [{"role": "user",
                     "content": prompts["agent_user"].format(label=label)}]
        active = ActiveDocument(text, label)
        set_active_document(active)
    elif arm == "retrieval_single":
        call = _call_retrieval_arm
        context, chunk_ids = select_context(text)
        result.context_chunks = len(chunk_ids)
        result.context_words = len(context.split())
        messages = [{"role": "user",
                     "content": prompts["retrieval_user"].format(label=label, context=context)}]
        active = None
    else:
        call = _call_single_arm
        messages = [{"role": "user",
                     "content": prompts["single_user"].format(label=label, document=text)}]
        active = None

    usage = _Usage()
    started = time.time()
    card = None
    checks, total, verified = {}, 0, 0

    try:
        client = _client()
        for attempt in range(1, MAX_REPAIRS + 2):
            result.attempts = attempt
            card, error = call(client, messages, model, effort, prompts, usage)
            result.error = error
            if card is None:
                break

            checks, total, verified = verify_card(card, text)
            bad = [f for f, kind in checks.items() if kind in ("not_found", "missing")]
            if not bad or attempt == MAX_REPAIRS + 1:
                break

            if is_local_model(model):
                # The local path collapses the conversation to one user string, so a
                # repair turn would be dropped rather than read. Better to report the
                # unrepaired card honestly than to fake a repair loop.
                break

            # Hand the model its own failures back, once.
            messages = messages + [
                {"role": "assistant", "content": card.model_dump_json()},
                {"role": "user", "content": repair_message(checks)},
            ]
    except anthropic.APIStatusError as exc:
        # Keep the server's message, not just the code. A bare "400" hid a
        # credit-balance error behind what looked like a model incompatibility.
        result.error = f"{type(exc).__name__} {exc.status_code}: {str(exc.message)[:200]}"
    except Exception as exc:                       # noqa: BLE001 - record and move on
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        if active is not None:
            result.tool_calls = active.tool_calls
            result.verify_tool_failures = active.verify_failures
            set_active_document(None)

    result.card = card
    result.quote_checks = checks
    result.quotes_total = total
    result.quotes_verified = verified
    result.input_tokens = usage.input
    result.output_tokens = usage.output
    result.cache_read_tokens = usage.cache_read
    result.cost_usd = cost_usd(model, usage.input, usage.output,
                               usage.cache_read, usage.cache_write)
    result.latency_s = round(time.time() - started, 2)
    result.prefill_s = round(usage.prefill_s, 2)
    result.generate_s = round(usage.generate_s, 2)
    return result


def run_retrieval_single(document: Document, label: str, model: str = DEFAULT_MODEL,
                         effort: str = "medium", prompt_version: str = "v1") -> ExtractionResult:
    """ARM 'retrieval_single': we retrieve the passages, the model reads only those."""
    return _run("retrieval_single", document, label, model, effort, prompt_version)


def run_agent(document: Document, label: str, model: str = DEFAULT_MODEL,
              effort: str = "medium", prompt_version: str = "v1") -> ExtractionResult:
    """ARM 'agent': the model searches the document and verifies its own quotes."""
    return _run("agent", document, label, model, effort, prompt_version)


def run_single_call(document: Document, label: str, model: str = DEFAULT_MODEL,
                    effort: str = "medium", prompt_version: str = "v1") -> ExtractionResult:
    """ARM 'single_call': no tools, whole document in the prompt, one request."""
    return _run("single_call", document, label, model, effort, prompt_version)


ARMS = {"agent": run_agent,
        "single_call": run_single_call,
        "retrieval_single": run_retrieval_single}
