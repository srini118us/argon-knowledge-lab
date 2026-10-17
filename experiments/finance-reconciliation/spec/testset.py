"""Frozen, unseen TEST set for Experiment 3 (Phase 6).

Distinct from the five development fixtures: different base ledgers (seeds), different defect
magnitudes and counts, different key ranges, extra currency mixes, and compound variants that
pair different parameters than the dev compound. Benign distractors (post-watermark lag, late
arrivals) are carried by the injectors themselves.

Nothing here is tuned to make Flash fail or Argon win. Cases vary the surface (data, keys,
amounts) while holding the task class constant, as DESIGN.md 7.1 requires. The set is built
only from the existing Phase 2 injectors via build_incident(**kwargs); no new defect logic.

The TEST cases never reuse a dev (seed, base, amounts) triple. build_case() returns (con, truth)
exactly like build_incident, so the grader and baseline consume them identically.
"""
from __future__ import annotations

from sim import injectors

# Each entry: id, incident class, seed (new base ledger), and injector params.
# Dev fixtures use seed 20260901 with the default bases/amounts; TEST uses seed 20270101+
# and shifted bases/amounts, so no case is a dev duplicate.
TEST_CASES = [
    # --- missing CDC delta: different magnitude, count, key range, ledger ---
    {"id": "T01", "incident": "incident1_skipped_cdc", "seed": 20270101,
     "params": {"amount": 270_000, "n": 3, "base": 4910000100}},
    {"id": "T02", "incident": "incident1_skipped_cdc", "seed": 20270102,
     "params": {"amount": 88_000, "n": 2, "base": 4910001100}},

    # --- duplicate replay: more duplicates, different magnitude ---
    {"id": "T03", "incident": "incident2_duplicate_replay", "seed": 20270103,
     "params": {"amount": 210_000, "n": 3, "base": 4920000100}},
    {"id": "T04", "incident": "incident2_duplicate_replay", "seed": 20270104,
     "params": {"amount": 60_000, "n": 2, "base": 4920001100}},

    # --- currency basis: different ledger (different fx mix via seed) ---
    {"id": "T05", "incident": "incident3_currency_basis", "seed": 20270105, "params": {}},
    {"id": "T06", "incident": "incident3_currency_basis", "seed": 20270106, "params": {}},

    # --- lossy join: different magnitude, count, ledger ---
    {"id": "T07", "incident": "incident4_lossy_join", "seed": 20270107,
     "params": {"amount": 174_000, "n": 3, "base": 4940000100}},   # divisible by n to avoid penny drift
    {"id": "T08", "incident": "incident4_lossy_join", "seed": 20270108,
     "params": {"amount": 52_000, "n": 2, "base": 4940001100}},

    # --- compound: different splits than the dev +450/-140; still net = missing - dup ---
    {"id": "T09", "incident": "incident5_compound", "seed": 20270109,
     "params": {"missing": 600_000, "dup": 220_000, "n_missing": 3, "n_dup": 2, "base": 4950000100}},
    {"id": "T10", "incident": "incident5_compound", "seed": 20270110,
     "params": {"missing": 360_000, "dup": 90_000, "n_missing": 4, "n_dup": 3, "base": 4950001100}},
]

# Dev triples, to assert the test set shares none of them.
DEV_SIGNATURE = {("incident1_skipped_cdc", 20260901, 4810000100),
                 ("incident2_duplicate_replay", 20260901, 4820000100),
                 ("incident3_currency_basis", 20260901, None),
                 ("incident4_lossy_join", 20260901, 4840000100),
                 ("incident5_compound", 20260901, 4850000100)}


def case_signature(case: dict) -> tuple:
    return (case["incident"], case["seed"], case["params"].get("base"))


def build_case(case: dict):
    """Build one test case world + truth. Same return shape as build_incident."""
    return injectors.build_incident(case["incident"], seed=case["seed"], **case["params"])


def expected_net(case: dict) -> float | None:
    """The expected source-minus-target discrepancy for a case, computed from its params
    (None for currency, which is counts-match/amount-drift)."""
    p = case["params"]
    inc = case["incident"]
    if inc == "incident1_skipped_cdc" or inc == "incident4_lossy_join":
        return float(p.get("amount", 0))
    if inc == "incident2_duplicate_replay":
        return float(-p.get("amount", 0))
    if inc == "incident5_compound":
        return float(p.get("missing", 0) - p.get("dup", 0))
    return None   # currency_basis
