# tools.py -- the two tools the agent can call.
#
# Both tools operate on ONE document at a time. Rather than rebuilding the tool
# objects for every document (the @beta_tool decorator wraps a plain function, so
# the schema is generated once from the signature), the extractor sets an
# "active document" before each run and the tools read it back.
#
# That active document is THREAD-LOCAL, because extractions run in parallel --
# see the comment on _STATE below. It also gives the tool-call counters one
# obvious home, per run.

import threading

from anthropic import beta_tool

from agent.chunker import build_index
from agent.verify import check_quote


class ActiveDocument:
    """The document the agent is currently reading, plus its search index."""

    def __init__(self, text: str, label: str):
        self.text = text
        self.label = label
        self.index = build_index(text)
        self.tool_calls = 0          # how many times the model used a tool
        self.search_calls = 0
        self.verify_calls = 0
        self.verify_failures = 0     # quotes the model tried that were NOT in the doc


# Set by agent/extractor.py before each run.
#
# THREAD-LOCAL ON PURPOSE. run_extract.py extracts many documents in parallel with a
# thread pool, and a plain module global would be shared by every worker: thread A
# would set the active document, thread B would overwrite it, and A's tools would
# then search B's transcript. The bug would not crash -- it would quietly produce
# quotes from the wrong company, which our own verifier would then reject as
# hallucinations. threading.local() gives each worker its own slot.
_STATE = threading.local()


def set_active_document(document: "ActiveDocument | None") -> None:
    _STATE.active = document


def get_active_document() -> "ActiveDocument | None":
    return getattr(_STATE, "active", None)


@beta_tool
def search_transcript(query: str) -> str:
    """Search the earnings-call document for passages relevant to a query.

    Use several targeted searches rather than one broad one. Good queries name the
    concept AND the words a company would actually use, for example
    "capacity sold out fully booked allocated" or "raising prices ASP increase".

    Args:
        query: Keywords to look for. Not a question -- just the words.
    """
    active = get_active_document()
    if active is None:
        return "ERROR: no active document."
    active.tool_calls += 1
    active.search_calls += 1

    hits = active.index.search(query, top_k=4)
    if not hits:
        return f"No passage matched '{query}'. Try different words."
    parts = [f"{len(hits)} passage(s) for '{query}':"]
    for chunk in hits:
        parts.append(f"\n--- passage {chunk.id} ---\n{chunk.text}")
    return "\n".join(parts)


@beta_tool
def verify_quote(quote: str) -> str:
    """Check that a quote you intend to use really appears in the document.

    Call this for every quote before you finalise your answer. If it comes back
    NOT FOUND you must go back to search_transcript and copy the real wording --
    do not submit a quote that failed this check.

    Args:
        quote: The exact span you plan to cite, copied from a passage.
    """
    active = get_active_document()
    if active is None:
        return "ERROR: no active document."
    active.tool_calls += 1
    active.verify_calls += 1

    kind = check_quote(quote, active.text)
    if kind == "exact":
        return "FOUND (exact match). Safe to use."
    if kind == "normalized":
        return "FOUND (matches ignoring whitespace/punctuation). Safe to use."
    active.verify_failures += 1
    return (
        "NOT FOUND. This wording does not occur in the document. "
        "Do not use it. Search again and copy the text exactly as written."
    )


AGENT_TOOLS = [search_transcript, verify_quote]
