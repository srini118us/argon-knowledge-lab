"""Verified Gemini API pricing (USD per 1M tokens, Standard paid tier).

Source: https://ai.google.dev/gemini-api/docs/pricing (checked 2026-10-13).
Output price includes thinking tokens. Argon supports implicit caching only.
Update this table whenever Google changes pricing; never guess.
"""
from __future__ import annotations

from datetime import date

PRICING = {
    "gemini-4-argon": [
        # (valid_until_inclusive, input, output_incl_thinking, cached_input)
        (date(2026, 11, 30), 2.00, 10.00, 0.10),
        (date(9999, 12, 31), 4.00, 20.00, 0.20),
    ],
    "gemini-3.8-flash": [
        (date(2026, 12, 31), 0.75, 3.75, 0.075),
        (date(9999, 12, 31), 1.50, 7.50, 0.15),
    ],
}


def rates(model: str, on: date | None = None) -> tuple[float, float, float]:
    on = on or date.today()
    for until, inp, out, cached in PRICING[model]:
        if on <= until:
            return inp, out, cached
    raise ValueError(f"No pricing for {model} on {on}")


def cost_usd(model: str, usage, on: date | None = None) -> float:
    """Cost from an Interactions API usage object (or dict with the same fields).

    Cached tokens are billed at the cached rate and removed from the full price
    input count. Thought tokens are billed as output. Tool use tokens are treated
    as input, which is an assumption to confirm against the billing console.
    ASSUMPTION: total_output_tokens excludes total_thought_tokens. The capability
    probe checks this by comparing total_tokens against the sum of the parts.
    """
    get = (lambda k: usage.get(k) or 0) if isinstance(usage, dict) else (lambda k: getattr(usage, k, 0) or 0)
    inp, out, cached = rates(model, on)
    in_tok = get("total_input_tokens") + get("total_tool_use_tokens")
    cached_tok = get("total_cached_tokens")
    out_tok = get("total_output_tokens") + get("total_thought_tokens")
    return ((in_tok - cached_tok) * inp + cached_tok * cached + out_tok * out) / 1_000_000


def estimate_usd(model: str, input_tokens: int, output_tokens: int, runs: int = 1) -> float:
    inp, out, _ = rates(model)
    return runs * (input_tokens * inp + output_tokens * out) / 1_000_000
