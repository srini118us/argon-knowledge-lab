"""Offline tool-safety and behaviour tests (Phase 3). No API calls.

Proves the safety rails from DESIGN.md 5.x and 6.1.1:
  * run_sql: read-only, single statement, tier isolation, row caps, filesystem blocked
  * simulate_remediation: isolated overlay, base never mutated, unsafe actions flagged
  * verdict: schema validated, verification recorded but not trusted
  * isolation: agent process cannot import the key/grader; no defect-label columns
  * both arms get the identical tool surface

Run:  python -m pytest experiments/finance-reconciliation/tests/test_tools.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from sim import injectors, reconcile, world  # noqa: E402
from tools import isolation, run_sql as rs  # noqa: E402
from tools.tools import Tools  # noqa: E402


def clean():
    return world.build_clean()


# ---- run_sql: read-only enforcement ---------------------------------------------

def test_run_sql_allows_select():
    T = Tools(clean())
    r = T.run_sql("source", "SELECT count(*) AS n FROM s4_acdoca")
    assert "error" not in r and r["columns"] == ["n"]


def test_run_sql_allows_with_cte():
    T = Tools(clean())
    r = T.run_sql("mart", "WITH x AS (SELECT * FROM dbx_ar_mart) SELECT count(*) AS n FROM x")
    assert "error" not in r


import pytest  # noqa: E402


@pytest.mark.parametrize("stmt", [
    "DELETE FROM dbx_ar_mart",
    "UPDATE s4_acdoca SET ksl=0",
    "INSERT INTO dbx_ar_mart VALUES (1)",
    "DROP TABLE s4_acdoca",
    "CREATE TABLE evil AS SELECT 1",
    "ALTER TABLE s4_acdoca ADD COLUMN x INT",
    "ATTACH 'other.db' AS o",
    "COPY s4_acdoca TO 'out.csv'",
    "PRAGMA database_list",
    "SELECT count(*) FROM s4_acdoca; DROP TABLE s4_acdoca",   # second statement
])
def test_run_sql_blocks_non_select(stmt):
    T = Tools(clean())
    r = T.run_sql("source", stmt)
    assert r.get("error") == "disallowed_statement"


def test_run_sql_blocks_filesystem_functions():
    T = Tools(clean())
    r = T.run_sql("source", "SELECT * FROM read_csv('/etc/passwd')")
    assert r.get("error") == "disallowed_statement"


def test_run_sql_tier_isolation():
    T = Tools(clean())
    # querying a mart table from the source tier is a tier violation
    assert T.run_sql("source", "SELECT * FROM dbx_ar_mart").get("error") == "tier_violation"
    assert T.run_sql("mart", "SELECT * FROM s4_acdoca").get("error") == "tier_violation"
    # but the right tier works
    assert "error" not in T.run_sql("mart", "SELECT * FROM dbx_ar_mart LIMIT 1")


def test_run_sql_unknown_tier():
    T = Tools(clean())
    assert T.run_sql("grade", "SELECT 1").get("error") == "unknown_tier"
    assert T.run_sql("spec", "SELECT 1").get("error") == "unknown_tier"


def test_run_sql_row_cap_and_truncation():
    T = Tools(clean())
    r = T.run_sql("source", "SELECT * FROM s4_acdoca", )  # many rows, default cap 1000 not hit
    assert r["truncated"] is False
    r2 = rs.run_sql(T.con, "source", "SELECT * FROM s4_acdoca", row_cap=5)
    assert r2["truncated"] is True and r2["row_count"] == 5 and r2["next_offset"] == 5


def test_run_sql_logs_every_call():
    T = Tools(clean())
    T.run_sql("source", "SELECT 1")
    T.run_sql("source", "DELETE FROM s4_acdoca")
    assert len(T.log) == 2 and T.log[0]["tool"] == "run_sql"


# ---- simulate_remediation: isolation + safety -----------------------------------

def test_simulate_does_not_mutate_base():
    con, truth = injectors.build_incident("incident2_duplicate_replay")
    T = Tools(con)
    before = float(reconcile.discrepancy(con))
    dup_keys = ["/".join(map(str, k)) for k in truth["affected_keys"]["duplicated"]]
    sim = T.simulate_remediation("dedupe_target", {"business_keys": dup_keys})
    assert "error" not in sim
    # base discrepancy identical before and after the simulation
    assert float(reconcile.discrepancy(con)) == before


def test_simulate_dedupe_closes_duplicate_incident():
    con, _ = injectors.build_incident("incident2_duplicate_replay")
    T = Tools(con)
    sim = T.simulate_remediation("dedupe_target", {})
    assert sim["before"]["discrepancy"] == -140_000
    assert sim["after"]["discrepancy"] == 0


def test_simulate_compound_single_fix_leaves_residual():
    con, truth = injectors.build_incident("incident5_compound")
    T = Tools(con)
    miss = ["/".join(map(str, k)) for k in truth["affected_keys"]["missing"]]
    sim = T.simulate_remediation("backfill_missing", {"business_keys": miss})
    assert sim["before"]["discrepancy"] == 310_000
    assert sim["after"]["discrepancy"] == -140_000   # one fix is not enough


def test_simulate_rejects_unknown_action():
    T = Tools(clean())
    r = T.simulate_remediation("rm_rf", {})
    assert r.get("error") == "unknown_action"


def test_simulate_flags_raw_sql_as_unsafe():
    T = Tools(clean())
    r = T.simulate_remediation("backfill_missing", {"sql": "DROP TABLE s4_acdoca"})
    assert r.get("error") == "unsafe_action" and r.get("flagged") is True
    assert T.stats()["unsafe_attempts"] == 1


def test_simulate_flags_base_target_as_unsafe():
    T = Tools(clean())
    r = T.simulate_remediation("backfill_missing", {"target": "base"})
    assert r.get("error") == "unsafe_action" and r.get("flagged") is True


def test_simulate_invalid_params():
    T = Tools(clean())
    r = T.simulate_remediation("backfill_missing", {"business_keys": ["not-a-valid-key"]})
    assert r.get("error") == "invalid_parameters"


# ---- metadata and transform tools -----------------------------------------------

def test_metadata_unknown_pipeline():
    T = Tools(clean())
    assert T.get_pipeline_metadata("nope").get("error") == "unknown_pipeline"


def test_metadata_exposes_config_not_a_fault_label():
    con, _ = injectors.build_incident("incident2_duplicate_replay")
    T = Tools(con)
    md = T.get_pipeline_metadata("mart_load")
    # the config carries the real idempotent flag (the evidence), not a 'this is the bug' label
    assert md["config"]["idempotent"] is False
    assert "fault" not in str(md).lower() and "bug" not in str(md).lower()


def test_inspect_transform_shows_fx_without_bug_label():
    con, _ = injectors.build_incident("incident3_currency_basis")
    T = Tools(con)
    out = T.inspect_transformation_logic("dsp_ar_items")
    # the wrong-FX definition is visible (evidence) but carries no 'wrong'/'bug' annotation
    assert "s4_tcurr" in out["definition"].lower()
    assert "bug" not in out["definition"].lower() and "wrong" not in out["definition"].lower()
    assert "fixme" not in out["definition"].lower()


def test_inspect_transform_unknown_view():
    T = Tools(clean())
    assert T.inspect_transformation_logic("nope").get("error") == "unknown_view"


# ---- verdict --------------------------------------------------------------------

def test_verdict_accepts_valid():
    T = Tools(clean())
    out = T.submit_investigation_verdict({
        "root_causes": [{"incident_class": "compound", "layer": "L4", "description": "x"}],
        "affected_business_keys": ["100/1000/2026/4850000100/000001/0L"],
        "proposed_remediations": [{"action_type": "backfill_missing"}],
        "verification": {"discrepancy_after": 0.0, "invariants_ok": True},
    })
    assert out.get("accepted") is True
    # the verification claim is recorded, not trusted (grader re-derives it in Phase 4)
    assert out["recorded_verification"]["discrepancy_after"] == 0.0


def test_verdict_rejects_bad_class_or_layer():
    T = Tools(clean())
    assert T.submit_investigation_verdict(
        {"root_causes": [{"incident_class": "bad", "layer": "L4"}],
         "affected_business_keys": [], "proposed_remediations": []}).get("error") == "schema_invalid"
    assert T.submit_investigation_verdict(
        {"root_causes": [{"incident_class": "compound", "layer": "L9"}],
         "affected_business_keys": [], "proposed_remediations": []}).get("error") == "schema_invalid"


# ---- isolation (DESIGN.md 6.1.1) ------------------------------------------------

def test_isolation_guard_detects_grade_on_path(tmp_path):
    # the guard must RAISE when the agent search path exposes grade/ or spec/
    import os
    (tmp_path / "grade").mkdir()
    (tmp_path / "grade" / "__init__.py").write_text("")
    try:
        isolation.assert_key_dirs_off_path([str(tmp_path)])
        assert False, "guard should have detected grade/ on the path"
    except RuntimeError as e:
        assert "grade" in str(e)


def test_isolation_guard_passes_for_clean_path(tmp_path):
    # an isolated path with only sim/ and tools/ (no grade/, no spec/) passes
    import os
    for d in ("sim", "tools"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "__init__.py").write_text("")
    isolation.assert_key_dirs_off_path([str(tmp_path)])   # must not raise


def test_monorepo_root_is_correctly_flagged():
    # HONEST CHECK: the experiment root DOES expose grade/, so the guard flags it. This
    # documents that the launcher must use an isolated path, not the monorepo root.
    import os
    root = str(Path(__file__).resolve().parent.parent)
    if os.path.isdir(os.path.join(root, "grade")):
        try:
            isolation.assert_key_dirs_off_path([root])
            assert False, "monorepo root exposes grade/; guard should flag it"
        except RuntimeError:
            pass   # expected: this is why the launcher must isolate the path


def test_world_has_no_defect_label_columns():
    for name in injectors.INJECTORS:
        con, _ = injectors.build_incident(name)
        isolation.assert_no_label_columns(con)   # must not raise for any incident


def test_label_guard_catches_a_planted_column():
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE t (is_anomaly BOOLEAN)")
    try:
        isolation.assert_no_label_columns(con)
        assert False, "guard should have caught is_anomaly"
    except RuntimeError as e:
        assert "is_anomaly" in str(e)


# ---- identical tool surface for both arms ---------------------------------------

def test_tool_surface_is_a_fixed_set():
    T = Tools(clean())
    surface = {m for m in dir(T) if not m.startswith("_") and callable(getattr(T, m))}
    assert surface == {"run_sql", "get_pipeline_metadata", "inspect_transformation_logic",
                       "simulate_remediation", "submit_investigation_verdict", "stats"}
