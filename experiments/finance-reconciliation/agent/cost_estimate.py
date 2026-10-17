"""Conservative cost estimate for the Phase 8 pilot and full benchmark (Phase 7).

Uses the repo's VERIFIED pricing (src/argon_lab/pricing.py, checked 2026-10-13 and reconfirmed
against public pricing in Phase 7). Token-per-turn figures are PLACEHOLDERS until a real pilot
measures them; they are flagged as such. The estimate is deliberately conservative (worst-case
turns and a generous token budget), and the real runner's per-call reservation + hard cap bound
actual spend regardless (DESIGN.md 9.3: no control is a hard billing guarantee; the cap is the
primary client-side control plus a provider-side alert budget).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from argon_lab.pricing import rates  # noqa: E402

# PLACEHOLDER token profile per CASE (not per turn), from the Phase 7 mock loop shape and the
# Experiment 2 pilot ranges. A real pilot replaces these. Conservative = generous.
# Agentic loop re-sends the growing transcript each turn, so input tokens dominate.
PLACEHOLDER = {
    "medium": {"input": 14_000, "output": 1_200, "thinking": 3_000},   # ~7 turns, growing context
    "high":   {"input": 20_000, "output": 2_000, "thinking": 14_000},  # not in the initial benchmark
}
# A conservative multiplier applied to the placeholder to avoid under-estimating.
SAFETY_MARGIN = 1.5


def case_cost(model: str, level: str, profile=None, margin: float = SAFETY_MARGIN) -> float:
    p = (profile or PLACEHOLDER)[level]
    inp, out, _ = rates(model)
    toks_in = p["input"] * margin
    toks_out = (p["output"] + p["thinking"]) * margin   # thinking billed as output
    return (toks_in * inp + toks_out * out) / 1_000_000


def estimate(n_cases: int, arms, level: str = "medium") -> dict:
    per = {f"{m}": round(case_cost(m, level), 4) for m in arms}
    total = sum(per[m] * n_cases for m in arms)
    return {"n_cases": n_cases, "arms": arms, "level": level,
            "per_case_usd": per, "total_usd": round(total, 2)}


def main() -> None:
    arms = ["gemini-3.8-flash", "gemini-4-argon"]
    print("CONSERVATIVE COST ESTIMATE (medium thinking, verified promo pricing, 1.5x margin)")
    print("  rates $/1M:", {m: rates(m)[:2] for m in arms})
    print()
    # smallest fair pilot: all 5 DEV incident classes, both arms, 1 trial
    pilot = estimate(5, arms, "medium")
    print(f"PILOT (5 dev cases x 2 arms x 1 trial):")
    print(f"  per case: {pilot['per_case_usd']}")
    print(f"  TOTAL estimate: ${pilot['total_usd']}")
    print()
    # full frozen benchmark: 10 test cases, both arms, 1 trial
    full = estimate(10, arms, "medium")
    print(f"FULL BENCHMARK (10 frozen test cases x 2 arms x 1 trial):")
    print(f"  TOTAL estimate: ${full['total_usd']}")
    print()
    # a small variance probe (3 trials on 1 case x 2 arms)
    var = estimate(1, arms, "medium")
    print(f"VARIANCE PROBE (1 case x 2 arms x 3 trials): ${round(var['total_usd'] * 3, 2)}")
    print()
    print("NOTE: token-per-case figures are PLACEHOLDERS until a real pilot measures them.")
    print("The runner's per-call worst-case reservation + hard --cap bound actual spend; a")
    print("provider-side Cloud Billing alert budget is early warning, NOT a hard stop.")


if __name__ == "__main__":
    main()
