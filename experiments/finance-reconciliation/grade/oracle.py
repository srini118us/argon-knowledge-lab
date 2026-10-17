"""Oracle verdict + evidence builder for grader testing (grade/ only).

Produces a correct verdict and a tool-call log that carries the required evidence
signatures, so the grader can be verified to award full marks to a perfect investigation.
The oracle is NOT an agent; it reads the key. It exists only to test the grader.
"""
from __future__ import annotations

from sim import reconcile
from tools.tools import Tools

CLASS_LAYER = {
    "missing_cdc_delta": "L1",
    "duplicate_replay": "L4",
    "currency_basis": "L2",
    "lossy_join": "L4",
    "compound": "L4",
}
SAFE_PICK = {
    "missing_cdc_delta": ["reextract_batch"],
    "duplicate_replay": ["dedupe_target"],
    "currency_basis": ["fix_transform"],
    "lossy_join": ["refresh_customer_snapshot"],
    "compound": ["backfill_missing", "dedupe_target"],
}


def oracle_log(con, key: dict) -> Tools:
    """Run the evidence-producing queries an ideal agent would run, returning the Tools
    object whose .log carries real, resolvable calls."""
    T = Tools(con)
    cls = key["incident_class"]
    # anti-join for missing: a single tier can't see two layers, so the oracle reads each
    # layer and the grader detects the anti-join pattern via a LEFT JOIN ... IS NULL within
    # a tier, or via NOT IN against a listed set. Here: mart-tier self anti-join pattern.
    T.run_sql("mart", "SELECT belnr FROM dbx_ar_mart WHERE belnr NOT IN "
                      "(SELECT belnr FROM dbx_ar_mart WHERE amount_usd IS NULL)")  # NOT IN pattern
    # duplicate check (mart)
    T.run_sql("mart", "SELECT belnr, count(*) FROM dbx_ar_mart GROUP BY belnr HAVING count(*) > 1")
    # cdc layer read (for cdc_vs_source signature)
    T.run_sql("cdc", "SELECT belnr FROM cdc_acdoca")
    T.run_sql("source", "SELECT belnr FROM s4_acdoca WHERE racct='0001400000'")
    # share and mart reads (for share_vs_mart signature)
    T.run_sql("share", "SELECT belnr FROM share_ar_items")
    T.run_sql("mart", "SELECT belnr, amount_usd FROM dbx_ar_mart")
    # amount comparison: read source ksl and mart amount_usd (compared across the two reads)
    T.run_sql("source", "SELECT belnr, ksl FROM s4_acdoca WHERE waers <> 'USD'")
    if cls == "currency_basis":
        T.inspect_transformation_logic("dsp_ar_items")
    return T


def oracle_verdict(con, key: dict, *, correct_keys=True) -> dict:
    cls = key["incident_class"]
    if cls == "compound":
        root_causes = [
            {"incident_class": "compound", "layer": "L4", "description": "missing set at mart"},
            {"incident_class": "compound", "layer": "L4", "description": "duplicated set at mart"},
        ]
    else:
        root_causes = [{"incident_class": cls, "layer": CLASS_LAYER[cls], "description": "d"}]
    from .key import all_affected_keys
    keys = sorted(all_affected_keys(key)) if correct_keys else ["0/0/0/0/0/0"]
    return {
        "root_causes": root_causes,
        "affected_business_keys": keys,
        "evidence": [{"tool": "run_sql", "summary": "anti-join", "ref": "call #1"},
                     {"tool": "run_sql", "summary": "dup check", "ref": "call #2"}],
        "proposed_remediations": [{"action_type": a} for a in SAFE_PICK[cls]],
        "verification": {"discrepancy_after": 0.0, "invariants_ok": True},
    }
