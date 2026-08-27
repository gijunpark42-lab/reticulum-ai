# pricing.py -- turn token usage into dollars, so cost is a first-class metric.
#
# Cost per correct label is an engineering result, not an afterthought: a cheap model
# that matches an expensive one is the finding. Rates are USD per 1,000,000 tokens.

PRICES = {
    # model id            input   output
    "claude-opus-5":     (5.00,  25.00),
    "claude-sonnet-5":   (3.00,  15.00),   # 2.00/10.00 promotional rate ran to 2026-08-31
    "claude-haiku-4-5":  (1.00,   5.00),
}

# A cache READ costs about a tenth of a fresh input token; a cache WRITE about 1.25x.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


def cost_usd(model: str,
             input_tokens: int,
             output_tokens: int,
             cache_read_tokens: int = 0,
             cache_write_tokens: int = 0) -> float:
    """Dollar cost of one request (or of a whole agent loop, if you sum the usage)."""
    if model not in PRICES:
        return 0.0
    input_rate, output_rate = PRICES[model]
    million = 1_000_000
    return (
        input_tokens / million * input_rate
        + output_tokens / million * output_rate
        + cache_read_tokens / million * input_rate * CACHE_READ_MULTIPLIER
        + cache_write_tokens / million * input_rate * CACHE_WRITE_MULTIPLIER
    )
