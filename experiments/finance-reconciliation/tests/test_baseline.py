"""Deterministic baseline tests (Phase 5). Offline, no API calls.

Proves the baseline is strong and honest:
  * scores full marks on all five dev incidents (a real finding: SQL solves these)
  * uses ONLY the bounded Tools, never the key or injector manifest
  * correctly distinguishes a skipped CDC batch from a downstream join loss
  * detects both defects in the compound case
  * its proposed repairs independently reconcile (grader verification = 20)
  * it never touches the incident world

Run:  python -m pytest experiments/finance-reconciliation/tests/test_baseline.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pytest  # noqa: E402

from agent import baseline  # noqa: E402
from grade import key as keymod, scorer  # noqa: E402
from sim import reconcile  # noqa: E402

INCIDENTS = ["incident1_skipped_cdc", "incident2_duplicate_replay",
             "incident3_currency_basis", "incident4_lossy_join", "incident5_compound"]


@pytest.mark.parametrize("name", INCIDENTS)
def test_baseline_scores_full_on_dev(name):
    con, key = keymod.build_key(name)
    res = baseline.run_baseline(con)
    g = scorer.grade(con, key, res["verdict"], log=res["tools"].log, tool_stats=res["tools"].stats())
    assert g["score"] == 100.0, f"{name}: {g['breakdown']}"
    assert g["critical_failures"]["is_critical_failure"] is False


@pytest.mark.parametrize("name", INCIDENTS)
def test_baseline_repairs_independently_reconcile(name):
    con, key = keymod.build_key(name)
    res = baseline.run_baseline(con)
    g = scorer.grade(con, key, res["verdict"], log=res["tools"].log, tool_stats=res["tools"].stats())
    # the grader's OWN overlay closes the discrepancy with no residual invariant breach
    assert g["breakdown"]["verification"] == 20.0
    assert g["verification_detail"]["discrepancy_closed"] is True
    assert g["verification_detail"]["invariants_clean"] is True


def test_baseline_distinguishes_skip_from_join_loss():
    con1, _ = keymod.build_key("incident1_skipped_cdc")
    r1 = baseline.run_baseline(con1)
    assert r1["verdict"]["root_causes"][0]["incident_class"] == "missing_cdc_delta"
    assert r1["findings"]["skip_confirmed"]                 # skip detected via cpudt<=watermark
    assert not r1["findings"]["missing_after_share"]        # NOT a share->mart loss

    con4, _ = keymod.build_key("incident4_lossy_join")
    r4 = baseline.run_baseline(con4)
    assert r4["verdict"]["root_causes"][0]["incident_class"] == "lossy_join"
    assert r4["findings"]["missing_after_share"]            # present at share, dropped at mart
    assert not r4["findings"]["skip_confirmed"]             # NOT a CDC skip


def test_baseline_detects_both_compound_defects():
    con, _ = keymod.build_key("incident5_compound")
    r = baseline.run_baseline(con)
    f = r["findings"]
    assert len(f["missing"]) == 3 and len(f["duplicated"]) == 2
    classes = {rc["incident_class"] for rc in r["verdict"]["root_causes"]}
    assert classes == {"compound"}
    assert len(r["verdict"]["proposed_remediations"]) == 2   # one per defect


def test_baseline_quantifies_duplicate_signed_impact():
    con, _ = keymod.build_key("incident2_duplicate_replay")
    r = baseline.run_baseline(con)
    assert abs(r["findings"]["dup_impact"] - 140_000) < 1    # the extra copies' signed value


def test_baseline_currency_counts_match_amounts_drift():
    con, _ = keymod.build_key("incident3_currency_basis")
    r = baseline.run_baseline(con)
    assert not r["findings"]["missing"] and not r["findings"]["duplicated"]
    assert len(r["findings"]["amount_mismatch"]) == 10
    assert r["verdict"]["root_causes"][0]["incident_class"] == "currency_basis"


def test_baseline_uses_only_bounded_tools_no_key_access():
    con, _ = keymod.build_key("incident5_compound")
    res = baseline.run_baseline(con)
    # every logged call is one of the five bounded tools
    allowed = {"run_sql", "get_pipeline_metadata", "inspect_transformation_logic",
               "simulate_remediation", "submit_investigation_verdict"}
    assert all(c["tool"] in allowed for c in res["tools"].log)
    # no unsafe attempts, no tier escapes
    assert res["tools"].stats()["unsafe_attempts"] == 0
    assert res["tools"].stats()["errors"] == 0


def test_baseline_does_not_mutate_incident_world():
    con, _ = keymod.build_key("incident5_compound")
    before = float(reconcile.discrepancy(con))
    baseline.run_baseline(con)
    assert float(reconcile.discrepancy(con)) == before


def test_baseline_verdict_matches_agent_schema():
    con, _ = keymod.build_key("incident1_skipped_cdc")
    v = baseline.run_baseline(con)["verdict"]
    assert set(v) >= {"root_causes", "affected_business_keys", "evidence",
                      "proposed_remediations", "verification"}
    for rc in v["root_causes"]:
        assert "incident_class" in rc and "layer" in rc
