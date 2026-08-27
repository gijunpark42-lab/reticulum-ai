# baselines.py -- the cheap lower bound: keyword matching, no model at all.
#
# WHY THIS EXISTS. "The LLM gets F1 0.8" means nothing on its own. The number that
# matters is how much better it is than the obvious thing you would try first. If a
# twelve-line regex matches the agent, the agent is not earning its cost.
#
# SCOPE. This arm only attempts capacity_status -- the one field with a human label.
# Every other field is "not_stated". That is honest rather than crippled: writing
# keyword rules for "guidance_direction" would be inventing a second unlabelled
# baseline nobody asked for.
#
# NOTE ON GROUNDING RATE. This arm quotes by EXTRACTING the matched sentence, so its
# grounding rate is 100% by construction and carries no information. The eval report
# says so rather than putting a misleading 100% next to the model arms.

import re
import time

from agent.corpus import Document
from agent.schema import ExtractionResult, SignalCard
from agent.verify import verify_card

# Phrases a company uses when it says its own capacity is gone. Ordered roughly by
# how unambiguous they are; the first match wins and supplies the quote.
SOLD_OUT_PATTERNS = [
    r"sold[\s-]?out",
    r"fully\s+(?:booked|allocated|committed|subscribed|contracted|reserved)",
    r"capacity\s+is\s+(?:full|gone|sold)",
    r"oversubscribed",
    r"demand\s+(?:significantly\s+)?exceed(?:s|ing)\s+(?:our\s+|available\s+)?supply",
    r"demand\s+(?:outstrips?|outstripping|outpac(?:es|ing))\s+(?:our\s+)?supply",
    r"supply\s+(?:cannot|can't|is\s+unable\s+to)\s+(?:keep\s+up|meet)",
]

# Weaker wording -- constrained, but the company did not say it is out of capacity.
TIGHT_PATTERNS = [
    r"supply\s+(?:remains\s+|is\s+|stays\s+)?(?:very\s+)?tight",
    r"capacity\s+constrain(?:ed|t)",
    r"lead\s+times?\s+(?:are\s+)?(?:increasing|extending|stretching|lengthening)",
    r"tight\s+supply",
    r"allocation",
]

_SOLD_OUT = re.compile("|".join(SOLD_OUT_PATTERNS), re.IGNORECASE)
_TIGHT = re.compile("|".join(TIGHT_PATTERNS), re.IGNORECASE)


def _sentences(text: str):
    """Rough sentence split. Good enough to hand back a readable quote."""
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        for sentence in re.split(r"(?<=[.!?;])\s+", block):
            sentence = sentence.strip()
            if sentence:
                yield sentence


def _first_match(text: str, pattern: re.Pattern):
    """Return the first sentence matching `pattern`, or None."""
    for sentence in _sentences(text):
        if pattern.search(sentence):
            # Keep quotes short enough to read in a report.
            return sentence[:300]
    return None


def run_regex(document: Document, label: str, model: str = "regex",
              effort: str = "", prompt_version: str = "keywords_v1") -> ExtractionResult:
    """ARM 'regex': keyword lower bound. No API call, no cost."""
    text = document.read()
    started = time.time()

    sold_out_quote = _first_match(text, _SOLD_OUT)
    tight_quote = None if sold_out_quote else _first_match(text, _TIGHT)

    if sold_out_quote:
        value, quote = "sold_out", sold_out_quote
    elif tight_quote:
        value, quote = "tight", tight_quote
    else:
        value, quote = "not_stated", ""

    card = SignalCard(
        company=document.company_token,
        capacity_status=value, capacity_status_quote=quote,
        demand_direction="not_stated", demand_direction_quote="",
        pricing_power="not_stated", pricing_power_quote="",
        guidance_direction="not_stated", guidance_direction_quote="",
        constraint_owner="not_stated", constraint_owner_quote="",
        confidence=1.0 if value != "not_stated" else 0.0,
    )

    result = ExtractionResult(doc_path=document.path, source_label=label,
                              arm="regex", model="regex", prompt_version=prompt_version,
                              effort="")
    checks, total, verified = verify_card(card, text)
    result.card = card
    result.quote_checks = checks
    result.quotes_total = total
    result.quotes_verified = verified
    result.latency_s = round(time.time() - started, 3)
    return result
