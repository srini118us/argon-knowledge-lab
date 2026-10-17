"""Phase 6 report: validate the frozen test set, score the baseline, show the freeze hash.

    python experiments/finance-reconciliation/spec/run_phase6.py

Offline, deterministic, no API calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import baseline  # noqa: E402
from grade import scorer  # noqa: E402
from spec import freeze, testset, validate_testset  # noqa: E402


def main() -> None:
    print("=" * 80)
    print("PHASE 6 — unseen TEST set: validation, necessity, baseline, freeze")
    print("=" * 80)
    print(f"\n{'id':4s}{'class':22s}{'disc':>10s}{'remed':>7s}{'naive':>7s}{'full':>6s}"
          f"{'multistep':>11s}  issues")
    base_total = 0.0
    for case in testset.TEST_CASES:
        r = validate_testset.validate_case(case)
        con, truth = testset.build_case(case)
        key = validate_testset._key_from_truth(case, truth)
        res = baseline.run_baseline(con)
        g = scorer.grade(con, key, res["verdict"], log=res["tools"].log, tool_stats=res["tools"].stats())
        base_total += g["score"]
        print(f"{r['id']:4s}{r['incident']:22s}{r['discrepancy']:>10,.0f}"
              f"{str(r['remediation_reconciles']):>7s}{r['naive_totals_only_score']:>7.0f}"
              f"{r['full_battery_score']:>6.0f}{str(r['multistep_required']):>11s}  "
              f"{r['problems'] or 'none'}")
    print("-" * 80)
    print(f"Baseline mean on TEST set: {base_total / len(testset.TEST_CASES):.1f}/100  "
          f"(a ceiling finding, reported as-is per DESIGN.md 7.2)")
    ok, diffs = freeze.verify_frozen()
    import json
    fp = json.loads((Path(__file__).resolve().parent / "frozen_testset.json").read_text())
    print(f"\nFrozen benchmark: {'MATCHES current' if ok else 'STALE: ' + ', '.join(diffs)}")
    print(f"benchmark_sha256: {fp.get('benchmark_sha256')}")


if __name__ == "__main__":
    main()
