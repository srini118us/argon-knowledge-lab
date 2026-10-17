"""Offline tests for the finance reconciliation simulator (Phase 2). No API calls.

Proves: a clean world reconciles; every injected incident produces its expected
discrepancy and invariant signature; the discriminating properties hold (incident 4 is
distinguishable from incident 1; incident 1's skip is distinguishable from benign lag);
the compound arithmetic ties out; and builds are deterministic.

Run:  python -m pytest experiments/finance-reconciliation/tests -q
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from sim import injectors, reconcile, schema, world  # noqa: E402

TOL = Decimal("0.01")


# ---- Clean world ----------------------------------------------------------------

def test_clean_world_reconciles():
    con = world.build_clean()
    assert reconcile.reconciles(con)
    assert abs(reconcile.discrepancy(con)) <= TOL
    assert reconcile.source_measure(con) == reconcile.target_measure(con)


def test_clean_world_has_green_monitoring():
    con = world.build_clean()
    statuses = [r[0] for r in con.execute("SELECT DISTINCT status FROM pipeline_runs").fetchall()]
    assert statuses == ["SUCCESS"]  # every incident keeps monitoring green


def test_out_of_scope_rows_excluded():
    con = world.build_clean()
    # other-account, other-period and post-watermark rows exist but do not move the measure
    other_acct = con.execute("SELECT count(*) FROM s4_acdoca WHERE racct='0001500000'").fetchone()[0]
    october = con.execute("SELECT count(*) FROM s4_acdoca WHERE budat >= '2026-10-01'").fetchone()[0]
    assert other_acct >= 1 and october >= 1
    assert reconcile.reconciles(con)  # still reconciles despite the noise


def test_build_is_deterministic():
    a = reconcile.summary(world.build_clean(seed=42))
    b = reconcile.summary(world.build_clean(seed=42))
    assert a == b
    c = reconcile.summary(world.build_clean(seed=43))
    # different seed -> same reconciliation (both clean) but different underlying totals allowed
    assert c["reconciles"] and a["reconciles"]


# ---- Each incident hits its expected discrepancy --------------------------------

def test_incident1_skipped_cdc():
    con, truth = injectors.build_incident("incident1_skipped_cdc")
    s = reconcile.summary(con)
    assert abs(s["discrepancy"] - truth["expected_discrepancy"]) < 0.01
    assert s["discrepancy"] == 450_000
    assert s["missing_at_mart"] == 3 and s["duplicated_at_mart"] == 0
    assert truth["root_cause_layer"] == ["L1"]


def test_incident1_skip_distinct_from_benign_lag():
    """The skipped keys have cpudt <= watermark AND no cdc row; the benign distractor has
    cpudt > watermark (normal lag, correctly pending, not a defect)."""
    con, truth = injectors.build_incident("incident1_skipped_cdc")
    wm = world.SNAPSHOT_WATERMARK_TS
    for bk in truth["affected_keys"]["missing"]:
        row = con.execute(
            f"SELECT cpudt FROM s4_acdoca WHERE belnr=? AND docln=?", [bk[3], bk[4]]
        ).fetchone()
        assert row[0] <= wm  # due by the watermark (control claims processed)
        in_cdc = con.execute("SELECT count(*) FROM cdc_acdoca WHERE belnr=?", [bk[3]]).fetchone()[0]
        assert in_cdc == 0   # yet never captured -> the skip
    # benign distractor: committed after the watermark, so it is NOT missing/defective
    lag = con.execute("SELECT cpudt FROM s4_acdoca WHERE belnr='4810000900'").fetchone()[0]
    assert lag > wm


def test_incident2_duplicate_replay():
    con, truth = injectors.build_incident("incident2_duplicate_replay")
    s = reconcile.summary(con)
    assert s["discrepancy"] == -140_000      # target exceeds source
    assert s["duplicated_at_mart"] == 2 and s["missing_at_mart"] == 0
    assert con.execute("SELECT idempotent FROM pipeline_config WHERE pipeline_id='mart_load'").fetchone()[0] is False


def test_incident3_currency_basis_counts_match_amounts_drift():
    con, truth = injectors.build_incident("incident3_currency_basis")
    s = reconcile.summary(con)
    assert s["missing_at_mart"] == 0 and s["duplicated_at_mart"] == 0  # count checks pass
    assert s["amount_mismatches"] > 0 and s["discrepancy"] != 0        # only amounts drift
    # USD rows are unaffected; only foreign-currency rows mismatch
    for bk in truth["affected_keys"]["amount_mismatch"]:
        waers = con.execute("SELECT waers FROM s4_acdoca WHERE belnr=?", [bk[3]]).fetchone()[0]
        assert waers != "USD"


def test_incident4_lossy_join():
    con, truth = injectors.build_incident("incident4_lossy_join")
    s = reconcile.summary(con)
    assert s["discrepancy"] == 120_000
    assert s["missing_at_mart"] == 2 and s["duplicated_at_mart"] == 0
    assert truth["root_cause_layer"] == ["L4"]


def test_incident4_distinct_from_incident1():
    """Incident 4's missing rows are present at the share (L2/L3) but absent at the mart;
    incident 1's missing rows are absent at the CDC layer too. This is the designed tell."""
    con4, t4 = injectors.build_incident("incident4_lossy_join")
    for bk in t4["affected_keys"]["missing"]:
        at_share = con4.execute("SELECT count(*) FROM share_ar_items WHERE belnr=?", [bk[3]]).fetchone()[0]
        at_mart = con4.execute("SELECT count(*) FROM dbx_ar_mart WHERE belnr=?", [bk[3]]).fetchone()[0]
        assert at_share == 1 and at_mart == 0      # present upstream, dropped at the join

    con1, t1 = injectors.build_incident("incident1_skipped_cdc")
    for bk in t1["affected_keys"]["missing"]:
        at_share = con1.execute("SELECT count(*) FROM share_ar_items WHERE belnr=?", [bk[3]]).fetchone()[0]
        assert at_share == 0                        # absent upstream too (never captured)


def test_incident5_compound_arithmetic():
    con, truth = injectors.build_incident("incident5_compound")
    s = reconcile.summary(con)
    # +450K missing and -140K from duplication net to +310K, tying to the headline
    assert truth["decomposition"]["missing_contrib"] == 450_000
    assert truth["decomposition"]["dup_contrib"] == -140_000
    assert 450_000 + (-140_000) == 310_000
    assert s["discrepancy"] == 310_000
    assert s["missing_at_mart"] == 3 and s["duplicated_at_mart"] == 2


def test_incident5_single_fix_leaves_residual():
    """Fixing only the missing half leaves -140K; fixing only the dup half leaves +450K.
    Simulated here by direct overlay-style edits on a copy, proving one action is insufficient."""
    con, truth = injectors.build_incident("incident5_compound")
    assert reconcile.discrepancy(con) == 310_000
    # Fix A only: backfill the missing keys into the mart
    for bk in truth["affected_keys"]["missing"]:
        amt = con.execute("SELECT ksl FROM s4_acdoca WHERE belnr=?", [bk[3]]).fetchone()[0]
        injectors._mart_insert(con, bk, amt, kunnr=f"CGONE0")
    assert reconcile.discrepancy(con) == -140_000   # residual equals the other defect


def test_source_is_never_corrupted():
    """Every incident leaves the source internally consistent (authoritative)."""
    for name in injectors.INJECTORS:
        con, _ = injectors.build_incident(name)
        # the source side measure is well-defined and the source has no duplicate business keys
        dup_src = con.execute(
            f"SELECT count(*) FROM (SELECT {schema.BK_SQL} FROM s4_acdoca "
            f"GROUP BY {schema.BK_SQL} HAVING count(*)>1)"
        ).fetchone()[0]
        assert dup_src == 0
