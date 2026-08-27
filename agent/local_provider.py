# local_provider.py -- run the same extraction against a model on this machine.
#
# WHY. Two reasons, and the second is the interesting one.
#   1. It costs nothing, so the experiment is not gated on an API balance.
#   2. It separates two things that are easy to confuse: SCHEMA VALIDITY and
#      FACTUAL GROUNDING. Ollama constrains decoding to the JSON schema, so a local
#      7-8B model returns a structurally perfect card essentially every time. Whether
#      the quotes inside that perfect card actually occur in the document is a
#      completely different question -- and it is the one agent/verify.py answers.
#      A frontier model and a small local model can both score 100% on "valid JSON"
#      and be far apart on "quotes that are real".
#
# Talks to the Ollama HTTP API directly with `requests` (already a project dependency)
# rather than adding an OpenAI-compatibility shim: the native endpoint is where the
# `format` (JSON-schema constrained decoding) and `think` options live.

import json
import time
from typing import Any, Dict, Optional, Tuple

import requests

OLLAMA_URL = "http://127.0.0.1:11434"
# CPU inference on a laptop is slow; a long read timeout is normal, not a hang.
REQUEST_TIMEOUT_S = 900
# Room for the retrieved passages (~4,000 words) plus the prompt and the answer.
NUM_CTX = 8192
NUM_PREDICT = 2500


def is_local_model(model: str) -> bool:
    """Anything that is not a Claude model id is treated as an Ollama tag."""
    return not model.startswith("claude-")


def server_available() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/version", timeout=5).ok
    except requests.RequestException:
        return False


def installed_models():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]
    except requests.RequestException:
        return []


class LocalUsage:
    """Mirrors what the Anthropic usage object gives us, so callers stay uniform."""

    def __init__(self, payload: Dict[str, Any]):
        self.input_tokens = payload.get("prompt_eval_count", 0) or 0
        self.output_tokens = payload.get("eval_count", 0) or 0
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0
        # Nanoseconds -> seconds. Useful for reporting prefill vs generation speed,
        # which is the whole story of running on a CPU.
        self.prefill_s = (payload.get("prompt_eval_duration", 0) or 0) / 1e9
        self.generate_s = (payload.get("eval_duration", 0) or 0) / 1e9
        self.load_s = (payload.get("load_duration", 0) or 0) / 1e9

    @property
    def prefill_tokens_per_s(self) -> Optional[float]:
        return self.input_tokens / self.prefill_s if self.prefill_s else None

    @property
    def generate_tokens_per_s(self) -> Optional[float]:
        return self.output_tokens / self.generate_s if self.generate_s else None


def complete_json(model: str,
                  system: str,
                  user: str,
                  json_schema: Dict[str, Any],
                  temperature: float = 0.0) -> Tuple[Optional[dict], Optional[LocalUsage], str]:
    """One constrained-decoding call. Returns (parsed_dict, usage, error_message).

    `format` makes the sampler follow the JSON schema, so the reply is valid JSON of
    the right shape or the request fails -- there is no "model forgot the format"
    failure mode to retry here. Temperature 0 keeps the run reproducible.
    """
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": json_schema,
        "stream": False,
        # Reasoning models burn a lot of CPU seconds thinking out loud. The schema
        # already forces a direct answer, so turn it off where the model supports it.
        "think": False,
        "options": {
            "temperature": temperature,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
    }
    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json=body,
                                 timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        return None, None, f"ollama request failed: {type(exc).__name__}: {exc}"

    if not response.ok:
        # A model that does not support `think` returns 400; retry once without it.
        if response.status_code == 400 and body.pop("think", None) is not None:
            try:
                response = requests.post(f"{OLLAMA_URL}/api/chat", json=body,
                                         timeout=REQUEST_TIMEOUT_S)
            except requests.RequestException as exc:
                return None, None, f"ollama retry failed: {type(exc).__name__}: {exc}"
        if not response.ok:
            return None, None, f"ollama HTTP {response.status_code}: {response.text[:200]}"

    payload = response.json()
    content = (payload.get("message") or {}).get("content", "")
    usage = LocalUsage(payload)
    try:
        return json.loads(content), usage, ""
    except json.JSONDecodeError as exc:
        # Constrained decoding cannot emit malformed JSON -- but it CAN be cut off
        # mid-string by the token limit, which leaves exactly that. Report the reason
        # the server gave (`done_reason`) so a truncation is not mistaken for a
        # model that cannot follow a schema.
        reason = payload.get("done_reason", "?")
        return None, usage, (f"output not valid JSON (done_reason={reason}, "
                             f"{usage.output_tokens} tokens): {exc}")


def warm_up(model: str) -> str:
    """Load the model into RAM once, so the first document is not charged for it."""
    started = time.time()
    _, usage, error = complete_json(
        model, "Reply with the schema.", "Say ok.",
        {"type": "object", "properties": {"ok": {"type": "boolean"}},
         "required": ["ok"], "additionalProperties": False},
    )
    if error:
        return f"warm-up failed: {error}"
    return (f"warm-up {time.time() - started:.1f}s "
            f"(model load {usage.load_s:.1f}s)" if usage else "warm-up ok")
