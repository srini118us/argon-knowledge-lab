"""Phase 6 tests: the frozen test set, its validation, necessity, baseline, and freeze.
Offline, no API calls.

Run:  python -m pytest experiments/finance-reconciliation/tests/test_testset.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pytest  # noqa: E402

from agent import baseline  # noqa: E402
from grade import scorer  # noqa: E402
from sim import reconcile  # noqa: E402
from spec import freeze, testset, validate_testset  # noqa: E402


def test_testset_is_separate_from_dev():
    sigs = {testset.case_signature(c) for c in testset.TEST_CASES}
    assert not (sigs & testset.DEV_SIGNATURE)
    assert len(testset.TEST_CASES) == 10


def test_every_class_represented_with_variation():
    classes = [c["incident"] for c in testset.TEST_CASES]
    for cls in ("incident1_skipped_cdc", "incident2_duplicate_replay", "incident3_currency_basis",
                "incident4_lossy_join", "incident5_compound"):
        assert classes.count(cls) >= 2   # at least two varied instances per class


@pytest.mark.parametrize("case", testset.TEST_CASES, ids=[c["id"] for c in testset.TEST_CASES])
def test_case_financials_and_keys(case):
    r = validate_testset.validate_case(case)
    assert r["problems"] == [], f"{case['id']}: {r['problems']}"


@pytest.mark.parametrize("case", testset.TEST_CASES, ids=[c["id"] for c in testset.TEST_CASES])
def test_case_requires_multistep(case):
    r = validate_testset.validate_case(case)
    # a totals-only shortcut must score far below a real investigation
    assert r["multistep_required"] is True
    assert r["naive_totals_only_score"] < r["full_battery_score"] - 20


@pytest.mark.parametrize("case", testset.TEST_CASES, ids=[c["id"] for c in testset.TEST_CASES])
def test_case_remediation_reconciles(case):
    r = validate_testset.validate_case(case)
    assert r["remediation_reconciles"] is True


def test_compound_cases_have_two_defects():
    for case in testset.TEST_CASES:
        if case["incident"] == "incident5_compound":
            con, truth = testset.build_case(case)
            assert "missing" in truth["affected_keys"] and "duplicated" in truth["affected_keys"]
            s = reconcile.summary(con)
            assert s["missing_at_mart"] > 0 and s["duplicated_at_mart"] > 0


def test_benign_distractor_present_for_skipped_cdc():
    # the skipped-cdc injector adds a post-watermark lag row that must NOT be a defect
    for case in testset.TEST_CASES:
        if case["incident"] == "incident1_skipped_cdc":
            con, truth = testset.build_case(case)
            base = case["params"]["base"]
            wm = con.execute("SELECT snapshot_watermark_ts FROM recon_cutoff").fetchone()[0]
            lag = con.execute("SELECT cpudt FROM s4_acdoca WHERE belnr=?", [str(base + 800)]).fetchone()
            assert lag is not None and lag[0] > wm   # genuinely pending, not counted


def test_baseline_on_testset_is_reported_honestly():
    # we assert the baseline runs and is scored; we do NOT assert it must fail or pass a
    # particular way — its score is a finding, reported as-is (DESIGN.md 7.2)
    total = 0.0
    for case in testset.TEST_CASES:
        con, truth = testset.build_case(case)
        key = validate_testset._key_from_truth(case, truth)
        res = baseline.run_baseline(con)
        g = scorer.grade(con, key, res["verdict"], log=res["tools"].log, tool_stats=res["tools"].stats())
        total += g["score"]
        assert "score" in g
    mean = total / len(testset.TEST_CASES)
    assert 0 <= mean <= 100   # whatever it is, it is reported; here it is 100 (a ceiling finding)


def test_freeze_is_reproducible():
    a = freeze.build_frozen()
    b = freeze.build_frozen()
    assert a == b   # deterministic


def test_frozen_file_matches_current():
    ok, diffs = freeze.verify_frozen()
    assert ok, f"frozen benchmark is stale: {diffs}"


def test_frozen_has_hashes_and_ground_truth():
    import json
    frozen = json.loads((HERE.parent / "spec" / "frozen_testset.json").read_text())
    assert "benchmark_sha256" in frozen
    assert len(frozen["file_hashes"]) >= 8
    assert len(frozen["ground_truth"]) == 10
    assert frozen["scoring_rules"]["dimensions"]["root_cause"] == 30
