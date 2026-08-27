# verify.py -- the anti-hallucination check.
#
# The agent is asked to quote the document verbatim. We do NOT take its word for it.
# After the model returns, this module re-checks every quote against the real file.
#
# Why this matters more than it looks: "grounding rate" (share of quotes that really
# occur in the source) is a hard, model-independent number. A model that invents a
# convincing-sounding quote is caught here even when its label happens to be right.

import unicodedata
import re

# Characters that transcripts pick up from web pages / PDFs and that a model
# routinely "cleans up" when quoting. Normalising both sides removes false misses.
_TRANSLATIONS = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
    "\u2026": "...", "\u00a0": " ", "\u200b": "",
}


def normalize(text: str) -> str:
    """Fold away formatting differences that do not change the words.

    NFKC first (so e.g. full-width characters collapse), then punctuation
    substitutions, then lowercase, then squash every run of whitespace to one space.
    """
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _TRANSLATIONS.items():
        text = text.replace(src, dst)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def check_quote(quote: str, document: str, normalized_document: str = None) -> str:
    """Return the match kind for one quote: 'exact' | 'normalized' | 'not_found'.

    'exact'      -- the quote appears byte-for-byte in the document.
    'normalized' -- it appears after whitespace/punctuation normalisation.
                    We still count this as verified: the WORDS are really there.
    'not_found'  -- the model made it up, or stitched together distant sentences.
    """
    if not quote or not quote.strip():
        return "not_found"
    if quote in document:
        return "exact"
    if normalized_document is None:
        normalized_document = normalize(document)
    if normalize(quote) in normalized_document:
        return "normalized"
    return "not_found"

def verify_card(card, document: str):
    """Check every REQUIRED quote on a SignalCard against the real document.

    A quote is required for each field the model did NOT answer "not_stated".
    Returns (quote_checks, quotes_total, quotes_verified) where quote_checks maps
    field name -> "exact" | "normalized" | "not_found" | "missing".

    Nothing is mutated on the card: the card stays a pure record of what the model
    said, and our measurements live on the ExtractionResult.
    """
    from agent.schema import SIGNAL_FIELDS   # imported here to avoid a circular import

    if card is None:
        return {}, 0, 0

    normalized_document = normalize(document)
    checks = {}
    total = verified = 0
    for field in SIGNAL_FIELDS:
        if card.value_of(field) == "not_stated":
            continue          # no claim made, so no evidence owed
        quote = card.quote_of(field).strip()
        if not quote:
            checks[field] = "missing"
            total += 1
            continue
        kind = check_quote(quote, document, normalized_document)
        checks[field] = kind
        total += 1
        if kind in ("exact", "normalized"):
            verified += 1
    return checks, total, verified
