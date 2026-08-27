# prompts.py -- prompt text, kept separate so the ablation can swap versions.
#
# Prompt version is an EXPERIMENTAL AXIS, not a detail: agent/eval/ablate.py reports
# a score per (model, arm, prompt_version) cell. Keeping the text here means a
# prompt change is a visible, reviewable diff rather than an untracked edit.

from agent.schema import SIGNAL_FIELDS

_FIELD_LIST = "\n".join(f"  - {name}" for name in SIGNAL_FIELDS)

# --- v1: the working prompt ------------------------------------------------------
# Three jobs it has to do:
#   1. Close the output space (the schema does most of this).
#   2. Forbid outside knowledge. The model was trained on the internet and may
#      "know" what happened after the call. That is lookahead bias and it would
#      silently contaminate the downstream event study.
#   3. Force quoting, and make the quote a verbatim copy rather than a paraphrase.
SYSTEM_V1 = f"""You extract structured signals from a single earnings-call document.

You will be given ONE document. Everything you output must come from that document
and nothing else.

HARD RULES
1. Use ONLY the text of this document. Do not use anything you know about this
   company, its stock, or what happened after this call. If the document does not
   say something, the answer is "not_stated" -- that is a correct answer, not a
   failure.
2. Every field you set to a value other than "not_stated" must have an evidence
   quote copied VERBATIM from the document. Copy characters exactly; do not fix
   grammar, do not shorten with "...", and never join text from two different
   places into one quote.
3. Call verify_quote on every quote before you finish. If it returns NOT FOUND,
   search again and copy the real wording. Never submit a quote that failed.
4. Judge only what the COMPANY SAYS ABOUT ITSELF. A supplier's or customer's
   situation described in passing is not this company's signal.

HOW TO WORK
Search before you answer. Run one focused search_transcript per field rather than a
single broad one -- companies use specific words, so search for those words:
{_FIELD_LIST}

For example, for capacity_status search wording like
"sold out fully booked allocated capacity constrained demand exceeds supply",
and for guidance_direction search "guidance raising outlook full year raised lowered".

When you have the evidence, produce the structured result.
"""

USER_TEMPLATE = """Document label: {label}

Extract the signal card for the company whose earnings call this is.
Begin by searching the document."""

# The single-call baseline gets no tools, so it is handed the whole document and
# told the same rules. Keeping the rules identical is what makes the comparison fair:
# the only thing that differs between arms is the RETRIEVAL AND VERIFICATION MACHINERY.
SYSTEM_SINGLE_CALL_V1 = f"""You extract structured signals from a single earnings-call document.

The full document is given to you below. Everything you output must come from it
and nothing else.

HARD RULES
1. Use ONLY the text of this document. Do not use anything you know about this
   company, its stock, or what happened after this call. If the document does not
   say something, the answer is "not_stated".
2. Every field you set to a value other than "not_stated" must have an evidence
   quote copied VERBATIM from the document. Copy characters exactly; do not fix
   grammar, do not shorten with "...", and never join text from two different
   places into one quote.
3. Judge only what the COMPANY SAYS ABOUT ITSELF.

Fields to fill:
{_FIELD_LIST}
"""

USER_SINGLE_CALL_TEMPLATE = """Document label: {label}

<document>
{document}
</document>

Extract the signal card for the company whose earnings call this is."""

# The retrieval arm sees selected passages instead of the whole call. The RULES are
# word-for-word the single-call rules -- only the material changes -- because the
# experiment is about how much context the model gets, not how it was instructed.
# The same text is sent to Claude and to the local model for the same reason.
SYSTEM_RETRIEVAL_V1 = SYSTEM_SINGLE_CALL_V1.replace(
    "The full document is given to you below.",
    "Passages selected from the document are given to you below.",
).replace(
    "3. Judge only what the COMPANY SAYS ABOUT ITSELF.",
    "3. Judge only what the COMPANY SAYS ABOUT ITSELF.\n"
    "4. You are seeing extracts, not the whole call. If the passages do not settle a\n"
    "   field, answer \"not_stated\" rather than guessing from the rest.",
)

USER_RETRIEVAL_TEMPLATE = """Document label: {label}

<passages>
{context}
</passages>

Extract the signal card for the company whose earnings call this is."""

PROMPT_VERSIONS = {
    "v1": {
        "agent_system": SYSTEM_V1,
        "agent_user": USER_TEMPLATE,
        "single_system": SYSTEM_SINGLE_CALL_V1,
        "single_user": USER_SINGLE_CALL_TEMPLATE,
        "retrieval_system": SYSTEM_RETRIEVAL_V1,
        "retrieval_user": USER_RETRIEVAL_TEMPLATE,
        "scratchpad": False,
    },
    # Same instructions and same passages -- the ONLY difference is that the model is
    # given one leading free-text field to work in before it commits to the enums.
    # Local models need this to produce anything at all; see agent/schema.py.
    "v1_scratch": {
        "agent_system": SYSTEM_V1,
        "agent_user": USER_TEMPLATE,
        "single_system": SYSTEM_SINGLE_CALL_V1,
        "single_user": USER_SINGLE_CALL_TEMPLATE,
        "retrieval_system": SYSTEM_RETRIEVAL_V1,
        "retrieval_user": USER_RETRIEVAL_TEMPLATE,
        "scratchpad": True,
    },
}


def repair_message(quote_checks) -> str:
    """Tell the model exactly which of its quotes failed our check, and how to fix it.

    The escape hatch matters: we explicitly allow the model to downgrade a field to
    "not_stated". Without it, a model that cannot find supporting text is pushed
    toward inventing some -- the opposite of what we are trying to measure.
    """
    reasons = {
        "not_found": "the quote you gave does not appear anywhere in the document",
        "missing": "you asserted a value but gave no quote",
    }
    lines = [f"  - {field}: {reasons[kind]}"
             for field, kind in quote_checks.items() if kind in reasons]
    return (
        "Your evidence did not pass verification:\n"
        + "\n".join(lines)
        + "\n\nProduce the card again. For each field listed above, EITHER find the real "
          "supporting text and copy it exactly, OR set that field to 'not_stated' with "
          "an empty quote. Setting it to 'not_stated' is the correct answer when the "
          "document genuinely does not say -- do not invent a quote to fill the gap. "
          "Leave every other field as it was."
    )
