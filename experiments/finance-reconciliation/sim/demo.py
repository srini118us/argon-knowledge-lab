"""Print a reproduction table: clean world reconciles, each incident hits its discrepancy.

    python experiments/finance-reconciliation/sim/demo.py

Offline, deterministic, no API calls. This is the Phase 2 demonstration.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim import injectors, reconcile, world  # noqa: E402


def main() -> None:
    print("CLEAN WORLD")
    con = world.build_clean()
    s = reconcile.summary(con)
    print(f"  source={s['source']:>14,.2f}  target={s['target']:>14,.2f}  "
          f"discrepancy={s['discrepancy']:>12,.2f}  reconciles={s['reconciles']}")
    print()
    print(f"{'INCIDENT':30s} {'discrepancy':>14s} {'expected':>12s} {'missing':>8s} "
          f"{'dup':>5s} {'amt':>5s}  {'result':>8s}")
    for name in injectors.INJECTORS:
        con, truth = injectors.build_incident(name)
        s = reconcile.summary(con)
        exp = truth["expected_discrepancy"]
        ok = "n/a" if exp is None else ("PASS" if abs(exp - s["discrepancy"]) < 0.01 else "FAIL")
        exp_s = "computed" if exp is None else f"{exp:,.0f}"
        print(f"{name:30s} {s['discrepancy']:>14,.2f} {exp_s:>12s} "
              f"{s['missing_at_mart']:>8d} {s['duplicated_at_mart']:>5d} "
              f"{s['amount_mismatches']:>5d}  {ok:>8s}")
    print()
    print("Compound check: +450,000 (missing) + (-140,000) (duplicated) = +310,000  ->",
          450_000 + (-140_000) == 310_000)


if __name__ == "__main__":
    main()
