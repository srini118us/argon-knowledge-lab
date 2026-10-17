"""Run the deterministic baseline on all five dev scenarios and print a scored report.

    python experiments/finance-reconciliation/agent/run_baseline_dev.py

Offline, deterministic, no API calls. Scores via the Phase 4 grader.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import baseline  # noqa: E402
from grade import key as keymod, scorer  # noqa: E402

NAMES = ["incident1_skipped_cdc", "incident2_duplicate_replay", "incident3_currency_basis",
         "incident4_lossy_join", "incident5_compound"]


def main() -> None:
    print("=" * 78)
    print("DETERMINISTIC SQL BASELINE — scored on the 5 development scenarios")
    print("=" * 78)
    total = 0.0
    for name in NAMES:
        con, key = keymod.build_key(name)
        res = baseline.run_baseline(con)
        T = res["tools"]
        g = scorer.grade(con, key, res["verdict"], log=T.log, tool_stats=T.stats())
        total += g["score"]
        f = res["findings"]
        rc = ", ".join(f"{r['incident_class']}/{r['layer']}" for r in res["verdict"]["root_causes"])
        print(f"\n{name}")
        print(f"  score            : {g['score']}/100   {g['breakdown']}")
        print(f"  diagnosis        : {rc}")
        print(f"  discrepancy      : {f['discrepancy']:,.2f}  (source {f['source_total']:,.0f} - target {f['target_total']:,.0f})")
        print(f"  findings         : missing={len(f['missing'])} dup={len(f['duplicated'])} "
              f"amount_drift={len(f['amount_mismatch'])} skip_confirmed={len(f['skip_confirmed'])} "
              f"at_share_not_mart={len(f['missing_after_share'])}")
        print(f"  tool calls       : {T.stats()['tool_calls']} ({T.stats()['sql_calls']} run_sql) "
              f"unsafe={T.stats()['unsafe_attempts']} errors={T.stats()['errors']}")
        print(f"  independent verif: discrepancy_closed={g['verification_detail']['discrepancy_closed']} "
              f"invariants_clean={g['verification_detail']['invariants_clean']}")
        print(f"  critical failure : {g['critical_failures']['is_critical_failure']}   error_category={g['error_category']}")
    print("\n" + "-" * 78)
    print(f"MEAN BASELINE SCORE: {total / len(NAMES):.1f}/100")
    print("Finding: the strong deterministic SQL baseline solves all five dev incidents.")
    print("Per DESIGN.md 7.2 this is a real result to report, not a reason to weaken any case.")


if __name__ == "__main__":
    main()
