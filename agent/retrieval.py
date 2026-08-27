# retrieval.py -- pick the passages worth reading, without asking the model to search.
#
# WHY A THIRD ARM. The tool-loop arm needs the model to decide what to search for and
# to call verify_quote on itself. Small local models are unreliable at both. But the
# expensive part of "read the whole call" is not the reasoning -- it is pushing 10,000
# tokens of transcript through prefill. So this arm keeps the retrieval and drops the
# agency: WE run one fixed BM25 query per field, dedupe the hits, and hand the model a
# single short prompt.
#
# That makes it the honest middle term of the ablation:
#
#   single_call       full document, no retrieval, no tools
#   retrieval_single  retrieved passages, no tools      <- this file
#   agent             retrieved passages, model-driven search + self-verification
#
# The gap single_call -> retrieval_single measures what RETRIEVAL is worth.
# The gap retrieval_single -> agent measures what AGENCY is worth on top of it.
# Without this arm those two effects are confounded.
#
# It is also the only arm that fits on a CPU: ~3x less prefill than the full document.

from typing import List, Tuple

from agent.chunker import build_index

# One query per scored field. These are keyword queries, not questions -- BM25 ranks
# by term overlap, so the words a company would actually SAY are what belong here.
FIELD_QUERIES = {
    "capacity_status": (
        "capacity sold out fully booked allocated committed subscribed constrained "
        "utilization demand exceeds outstrips supply tight"
    ),
    "demand_direction": (
        "demand orders bookings backlog growth strong accelerating slowing softening "
        "book-to-bill momentum"
    ),
    "pricing_power": (
        "price pricing increase raise ASP cost pass through discount margin "
        "price increases"
    ),
    "guidance_direction": (
        "guidance outlook forecast full year raised raising lowered cutting guide "
        "next quarter expect revenue"
    ),
    "constraint_owner": (
        "constraint shortage bottleneck limited by lead times wafer substrate memory "
        "supplier allocation cannot get"
    ),
}

# Chosen from the recall/budget curve below, measured against the 296 verbatim quotes
# the full-reading Opus agent produced (all of them verified against the source):
#
#   top_k  budget  median ctx words   quote recall   capacity-field recall
#       3    2600              2510            71%                    79%
#       4    3200              3130            78%                    85%
#       5    4000              3841            85%                    89%   <- knee
#       6    5000              4310            90%                    93%
#       8    7000              5234            95%                    95%
#      12       -              6321            99%                    98%
#
# The median document is 7,635 words, so top_k=5 is a ~2x prefill saving for a
# ~11-point recall loss on the scored field. That loss is a CEILING on this arm:
# evidence outside the retrieved passages cannot be found however good the model is.
# Reproduce the curve with agent/eval/retrieval_curve.py.
TOP_K_PER_FIELD = 5
# Cap so one long document cannot blow past a small local context window.
MAX_CONTEXT_WORDS = 4000


def select_context(document_text: str,
                   top_k: int = TOP_K_PER_FIELD,
                   max_words: int = MAX_CONTEXT_WORDS) -> Tuple[str, List[int]]:
    """Return (context_text, chunk_ids) -- the passages to show the model.

    Chunks are deduplicated (one query's hit is often another's) and then emitted in
    DOCUMENT ORDER, not relevance order. Ordering by relevance would scramble the
    call's narrative and makes quotes harder to attribute.
    """
    index = build_index(document_text)

    chosen = {}
    for query in FIELD_QUERIES.values():
        for chunk in index.search(query, top_k=top_k):
            chosen.setdefault(chunk.id, chunk)

    ordered = [chosen[cid] for cid in sorted(chosen)]

    # Trim from the end if we are over budget, so early context survives.
    kept, words = [], 0
    for chunk in ordered:
        n = len(chunk.text.split())
        if words + n > max_words and kept:
            break
        kept.append(chunk)
        words += n

    context = "\n\n".join(f"--- passage {c.id} ---\n{c.text}" for c in kept)
    return context, [c.id for c in kept]
