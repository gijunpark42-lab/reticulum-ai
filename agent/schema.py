# schema.py -- what the agent is allowed to output.
#
# The whole design rests on ONE idea: keep the output space SMALL and CLOSED.
# Every judgement is an enum (a fixed list of allowed strings), never free text.
# Free text cannot be scored against a human label; an enum can.
#
# `capacity_status == "sold_out"` is deliberately defined to mean exactly what the
# project owner meant by flag=1 in quant/signal_full_capacity.csv:
#   "the company itself said its capacity is full / sold out / demand exceeds its supply."
# That 1:1 correspondence is what lets us measure precision/recall without doing
# any new hand-labelling.
#
# NOTE ON SHAPE: each judgement is paired with a REQUIRED `<field>_quote` sibling
# rather than a free-form evidence dictionary. A dictionary is legal when empty, so
# the model can silently skip citing anything -- which is exactly what happened on
# the first smoke test. Making the quote a required field of the schema means the
# API itself will not accept an answer without one.

from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field

CapacityStatus = Literal["sold_out", "tight", "balanced", "underutilized", "not_stated"]
DemandDirection = Literal["accelerating", "stable", "decelerating", "not_stated"]
PricingPower = Literal["raising", "stable", "falling", "not_stated"]
GuidanceDirection = Literal["raised", "maintained", "lowered", "not_stated"]
ConstraintOwner = Literal["self", "supplier", "customer_demand", "none", "not_stated"]

# The five scored fields, in a fixed order. Everything downstream iterates this.
SIGNAL_FIELDS = (
    "capacity_status",
    "demand_direction",
    "pricing_power",
    "guidance_direction",
    "constraint_owner",
)

_QUOTE_RULE = (
    "The span from the document that supports {field}, copied VERBATIM. "
    "Use an empty string ONLY when {field} is 'not_stated'."
)


class SignalCard(BaseModel):
    """One structured signal record per source document. Pure model output."""

    company: str = Field(description="Company whose call this is, as named in the document.")

    capacity_status: CapacityStatus = Field(
        description=(
            "The company's OWN capacity, in its own words. "
            "'sold_out' = capacity is sold out / fully booked / fully allocated / "
            "demand exceeds its supply. "
            "'tight' = constrained or lead times stretching, but not sold out. "
            "'balanced' = supply and demand roughly matched. "
            "'underutilized' = excess capacity, low utilization, underloaded fabs. "
            "'not_stated' = the document does not say."
        )
    )
    capacity_status_quote: str = Field(description=_QUOTE_RULE.format(field="capacity_status"))

    demand_direction: DemandDirection = Field(
        description="Direction of demand for the company's own products this quarter."
    )
    demand_direction_quote: str = Field(description=_QUOTE_RULE.format(field="demand_direction"))

    pricing_power: PricingPower = Field(
        description="Whether the company says it is raising, holding, or cutting prices/ASPs."
    )
    pricing_power_quote: str = Field(description=_QUOTE_RULE.format(field="pricing_power"))

    guidance_direction: GuidanceDirection = Field(
        description="What the company did to its forward guidance versus the previous quarter."
    )
    guidance_direction_quote: str = Field(description=_QUOTE_RULE.format(field="guidance_direction"))

    constraint_owner: ConstraintOwner = Field(
        description=(
            "If growth is limited, WHO is the binding constraint. "
            "'self' = the company's own capacity. "
            "'supplier' = an input it cannot get (wafers, memory, substrates, testers). "
            "'customer_demand' = demand is the limit, not supply. "
            "'none' = nothing is binding. "
            "'not_stated' = the document does not say."
        )
    )
    constraint_owner_quote: str = Field(description=_QUOTE_RULE.format(field="constraint_owner"))

    confidence: float = Field(
        ge=0.0, le=1.0,
        description="0..1 -- how confident you are in this card overall."
    )

    # --- convenience accessors (not part of the model's job) ---------------------
    def value_of(self, field: str) -> str:
        return getattr(self, field)

    def quote_of(self, field: str) -> str:
        return getattr(self, f"{field}_quote") or ""

    def asserted_fields(self):
        """Fields where the model committed to a value, so a quote is required."""
        return [f for f in SIGNAL_FIELDS if self.value_of(f) != "not_stated"]


class ExtractionResult(BaseModel):
    """A SignalCard plus everything needed to score the RUN itself.

    Kept separate from SignalCard on purpose: the card is what the MODEL produced,
    this wrapper is what WE measured about it.
    """

    card: Optional[SignalCard] = None
    doc_path: str = ""
    source_label: str = ""      # canonical label, e.g. "Rambus Q2 FY2026 (07-27-2026)"
    arm: str = ""               # "agent" | "single_call" | "regex"
    model: str = ""
    prompt_version: str = ""
    effort: str = ""

    # Engineering metrics.
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    tool_calls: int = 0
    # retrieval_single only: how much context we chose to show the model.
    context_chunks: int = 0
    context_words: int = 0
    # local (Ollama) runs only: where the wall-clock actually went.
    prefill_s: float = 0.0
    generate_s: float = 0.0
    verify_tool_failures: int = 0   # quotes the model itself caught as NOT FOUND
    attempts: int = 1               # 1 = accepted on the first try, 2 = needed a repair
    error: str = ""

    # Filled by agent/verify.py: field -> "exact" | "normalized" | "not_found" | "missing"
    quote_checks: Dict[str, str] = Field(default_factory=dict)
    quotes_total: int = 0           # asserted fields that needed a quote
    quotes_verified: int = 0        # of those, how many really occur in the document

    @property
    def grounding_rate(self) -> Optional[float]:
        """Share of required quotes that really occur in the document."""
        if self.quotes_total == 0:
            return None
        return self.quotes_verified / self.quotes_total

    def missing_or_bad_fields(self):
        """Asserted fields whose quote is absent or not in the document."""
        return [f for f, kind in self.quote_checks.items()
                if kind in ("not_found", "missing")]


# --------------------------------------------------------------------------------
# Constrained-decoding accommodation.
#
# When a sampler is constrained to a JSON schema it starts emitting the answer at the
# very first token: there is no room to look at the passages before committing. Large
# models absorb that; a local 8B does not. Measured on one document with qwen3:8b:
#
#   plain schema, thinking off   ->  0 of 5 fields asserted   (39 s)
#   plain schema, thinking ON    ->  0 of 5 fields asserted  (432 s)
#   ONE free-text field first    ->  3 of 5 fields asserted   (88 s)
#
# So the fix is not more reasoning, it is somewhere to put it. This adds a single
# leading string field; it is stripped again before validating into SignalCard, so
# the scored object is identical either way.
# --------------------------------------------------------------------------------

SCRATCHPAD_KEY = "evidence_notes"

# The scratchpad must be BOUNDED. Left open, a small model treats it as free
# chain-of-thought: qwen3:4b spent its entire 1500-token budget narrating
# ("Passage 0: ... Passage 1: ...") and hit the length limit before emitting a single
# answer field, so the JSON never closed. It had found the right evidence on the way
# -- it just never arrived. A maxLength in the schema is a hard stop the sampler
# itself enforces, and the wording below asks for quotes rather than reasoning.
SCRATCHPAD_MAX_CHARS = 1200


def json_schema_with_scratchpad(max_chars: int = SCRATCHPAD_MAX_CHARS) -> dict:
    """SignalCard's schema with a leading, length-capped field to collect quotes in."""
    schema = SignalCard.model_json_schema()
    schema["properties"] = {
        SCRATCHPAD_KEY: {
            "type": "string",
            "maxLength": max_chars,
            "description": (
                "Scratch space, filled in FIRST. For each of the five topics "
                "(capacity, demand, pricing, guidance, constraints) copy AT MOST ONE "
                "short sentence from the passages, exactly as written, or the single "
                "word 'absent'. Do NOT explain your reasoning, do not number the "
                "passages, do not write commentary -- quotes only. Keep the whole "
                f"field under {max_chars} characters, then answer the fields below."
            ),
        },
        **schema["properties"],
    }
    schema["required"] = [SCRATCHPAD_KEY] + list(schema["required"])
    return schema


def strip_scratchpad(payload: dict) -> dict:
    """Drop the scratchpad so what gets validated is exactly a SignalCard."""
    return {k: v for k, v in payload.items() if k != SCRATCHPAD_KEY}
