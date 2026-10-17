"""Validate the frozen test set and prove each case needs genuine multistep investigation.

Checks (all offline, no key leakage to any agent):
  1. Financial math: each case's source-minus-target discrepancy equals the expected net.
  2. Affected keys: the injected keys actually exhibit their defect (missing/dup/amount) at the
     right layer, computed from the world, not asserted.
  3. Remediation outcome: applying the case's safe remediations on an overlay closes the
     discrepancy with no residual invariant breach (same engine the grader uses).
  4. Multistep necessity: a naive "totals-only" strategy (compare the two totals, read off the
     sign) CANNOT produce the correct structural diagnosis; the full battery can. This proves
     the case is not solvable by a single total comparison.
  5. No dev reuse: no test case shares a dev (incident, seed, base) signature.

Nothing here is tuned against a model. The necessity test is symmetric: it measures a property
of the case (does a shortcut suffice?), not of any model.
"""
from __future__ import annotations

from decimal import Decimal

from agent import baseline
from grade import scorer
from sim import reconcile
from tools.tools import Tools

from . import testset


def naive_totals_only_verdict(con) -> dict:
    """The weakest plausible strategy: compute the two totals, read off the sign, and guess a
    single class from the sign alone. It does NOT localise the layer, find keys, or detect the
    second defect in a compound case. Used to prove a total comparison is insufficient."""
    T = Tools(con)
    disc = reconcile.discrepancy(con)
    # sign heuristic only: positive -> "something missing", negative -> "something duplicated"
    if disc > 0:
        rc = [{"incident_class": "missing_cdc_delta", "layer": "L1", "description": "totals: source high"}]
    elif disc < 0:
        rc = [{"incident_class": "duplicate_replay", "layer": "L4", "description": "totals: target high"}]
    else:
        rc = [{"incident_class": "currency_basis", "layer": "L2", "description": "totals match"}]
    return {
        "root_causes": rc,
        "affected_business_keys": [],          # a totals comparison names no keys
        "evidence": [],
        "proposed_remediations": [],           # and proposes no concrete fix
        "verification": {"discrepancy_after": float(disc), "invariants_ok": False},
    }, T


def validate_case(case: dict) -> dict:
    con, truth = testset.build_case(case)
    s = reconcile.summary(con)
    result = {"id": case["id"], "incident": case["incident"], "problems": []}

    # 1. financial math
    exp = testset.expected_net(case)
    if exp is not None and abs(s["discrepancy"] - exp) > 0.01:
        result["problems"].append(f"discrepancy {s['discrepancy']} != expected {exp}")
    result["discrepancy"] = s["discrepancy"]

    # 2. affected keys exhibit their defect
    ak = truth["affected_keys"]
    if "missing" in ak:
        missing_now = {"/".join(map(str, k)) for k in reconcile.missing_at_mart(con)}
        for bk in ak["missing"]:
            if "/".join(map(str, bk)) not in missing_now:
                result["problems"].append(f"declared-missing key not actually missing: {bk}")
    if "duplicated" in ak:
        dup_now = {"/".join(map(str, k)) for k in reconcile.duplicated_at_mart(con)}
        for bk in ak["duplicated"]:
            if "/".join(map(str, bk)) not in dup_now:
                result["problems"].append(f"declared-duplicate key not actually duplicated: {bk}")
    if "amount_mismatch" in ak:
        mm_now = {"/".join(map(str, k[:6])) for k in reconcile.amount_mismatches(con)}
        for bk in ak["amount_mismatch"]:
            if "/".join(map(str, bk)) not in mm_now:
                result["problems"].append(f"declared-mismatch key not actually mismatched: {bk}")

    # 3. remediation outcome (reuse the grader's independent overlay via a correct verdict)
    correct = _correct_verdict(truth)
    verdict_state = scorer._apply_proposed_to_overlay(con, correct)
    closed = abs(Decimal(str(verdict_state["discrepancy"]))) <= Decimal("0.01")
    clean = (verdict_state["missing_at_mart"] == 0 and verdict_state["duplicated_at_mart"] == 0
             and verdict_state["amount_mismatches"] == 0)
    if not (closed and clean):
        result["problems"].append(f"safe remediation does not reconcile: {verdict_state}")
    result["remediation_reconciles"] = bool(closed and clean)

    # 4. multistep necessity: naive totals-only must NOT score full marks.
    # Build a key from THIS case's own truth (not the dev key).
    case_key = _key_from_truth(case, truth)
    naive_v, naive_T = naive_totals_only_verdict(con)
    naive_g = scorer.grade(con, case_key, naive_v, log=naive_T.log, tool_stats=naive_T.stats())
    result["naive_totals_only_score"] = naive_g["score"]
    # the full battery (baseline) for contrast
    res = baseline.run_baseline(con)
    full_g = scorer.grade(con, case_key, res["verdict"], log=res["tools"].log, tool_stats=res["tools"].stats())
    result["full_battery_score"] = full_g["score"]
    # necessity holds if a totals-only shortcut scores far below a real investigation
    if naive_g["score"] >= full_g["score"] - 20:
        result["problems"].append(
            f"totals-only shortcut scores {naive_g['score']} vs full {full_g['score']}: case may be too easy")
    result["multistep_required"] = naive_g["score"] < full_g["score"] - 20

    return result


def _correct_verdict(truth: dict) -> dict:
    """A correct verdict built from the case truth (used only for remediation validation)."""
    cls = truth["incident"]
    layers = truth["root_cause_layer"]
    if cls == "compound":
        rcs = [{"incident_class": "compound", "layer": "L4"},
               {"incident_class": "compound", "layer": "L4"}]
        rems = [{"action_type": "backfill_missing",
                 "parameters": {"business_keys": ["/".join(map(str, k)) for k in truth["affected_keys"]["missing"]]}},
                {"action_type": "dedupe_target"}]
    else:
        rcs = [{"incident_class": cls, "layer": layers[0]}]
        rems = [{"action_type": truth["safe_remediations"][0]}]
        if cls == "missing_cdc_delta":
            rems = [{"action_type": "reextract_batch",
                     "parameters": {"business_keys": ["/".join(map(str, k)) for k in truth["affected_keys"]["missing"]]}}]
    allk = []
    for v in truth["affected_keys"].values():
        allk += ["/".join(map(str, k)) for k in v]
    return {"root_causes": rcs, "affected_business_keys": allk,
            "evidence": [], "proposed_remediations": rems,
            "verification": {"discrepancy_after": 0.0, "invariants_ok": True}}


def _key_from_truth(case: dict, truth: dict) -> dict:
    """Build a grader key dict for a test case from its own truth (not the dev key)."""
    from grade.key import REQUIRED_EVIDENCE
    return {
        "incident_name": case["id"],
        "incident_class": truth["incident"],
        "root_cause_layers": truth["root_cause_layer"],
        "affected_keys": {k: [list(map(str, bk)) for bk in v] for k, v in truth["affected_keys"].items()},
        "safe_remediations": set(truth["safe_remediations"]),
        "required_evidence": REQUIRED_EVIDENCE.get(truth["incident"], []),
        "expected_discrepancy": truth.get("expected_discrepancy"),
    }


def validate_all() -> list[dict]:
    # no dev reuse
    sigs = {testset.case_signature(c) for c in testset.TEST_CASES}
    assert not (sigs & testset.DEV_SIGNATURE), "test set reuses a dev fixture signature"
    return [validate_case(c) for c in testset.TEST_CASES]
