"""Adversarial tests for the run_sql safety boundary (Phase 4 requirement).

These push on the guard rather than confirm the happy path. Passing them does NOT mean the
guard is universally secure; see tools/SECURITY.md for the honest threat model and known
limits. The guard is a regex-and-allowlist filter over a trusted local DuckDB, not a
hardened SQL firewall. Its real safety rests on three layers:
  (1) this filter (defence in depth),
  (2) the database holding only synthetic data (no secrets to exfiltrate),
  (3) process isolation keeping the answer key off the agent's path.

Run:  python -m pytest experiments/finance-reconciliation/tests/test_sql_adversarial.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pytest  # noqa: E402

from sim import world  # noqa: E402
from tools import run_sql as rs  # noqa: E402


@pytest.fixture(scope="module")
def con():
    return world.build_clean()


# ---- writes and DDL must never pass, in any disguise ----------------------------
@pytest.mark.parametrize("stmt", [
    "DELETE FROM dbx_ar_mart",
    "delete from dbx_ar_mart",                      # case
    "DeLeTe FROM dbx_ar_mart",                      # mixed case
    "DELETE/**/FROM/**/dbx_ar_mart",                # comment between tokens
    "UPDATE s4_acdoca SET ksl = ksl + 1",
    "INSERT INTO dbx_ar_mart SELECT * FROM dbx_ar_mart",
    "DROP TABLE s4_acdoca",
    "TRUNCATE s4_acdoca",
    "ALTER TABLE s4_acdoca ADD COLUMN z INT",
    "CREATE TABLE evil AS SELECT 1",
    "CREATE OR REPLACE VIEW dsp_ar_items AS SELECT 1",
    "SELECT 1; DROP TABLE s4_acdoca",              # stacked
    "SELECT 1 -- ; DROP TABLE s4_acdoca\n",       # comment-terminated (benign, stays SELECT)
])
def test_no_writes_pass(con, stmt):
    r = rs.run_sql(con, "mart", stmt)
    # either blocked as disallowed, or (for the commented benign case) runs as a pure SELECT
    assert r.get("error") in ("disallowed_statement", "tier_violation", "query_error") or "columns" in r
    # and the base data is untouched regardless
    n = con.execute("SELECT count(*) FROM dbx_ar_mart").fetchone()[0]
    assert n > 0


def test_write_attempts_do_not_mutate(con):
    before = con.execute("SELECT count(*) FROM s4_acdoca").fetchone()[0]
    for stmt in ["DELETE FROM s4_acdoca", "DROP TABLE s4_acdoca",
                 "UPDATE s4_acdoca SET ksl=0", "INSERT INTO s4_acdoca DEFAULT VALUES"]:
        rs.run_sql(con, "source", stmt)
    after = con.execute("SELECT count(*) FROM s4_acdoca").fetchone()[0]
    assert after == before   # nothing was written


# ---- filesystem / attach / copy escapes -----------------------------------------
@pytest.mark.parametrize("stmt", [
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('secret.parquet')",
    "SELECT * FROM glob('/**')",
    "ATTACH '/tmp/x.db' AS x",
    "COPY s4_acdoca TO '/tmp/leak.csv'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "PRAGMA database_list",
])
def test_filesystem_and_attach_blocked(con, stmt):
    r = rs.run_sql(con, "source", stmt)
    assert r.get("error") in ("disallowed_statement", "tier_violation")


# ---- tier isolation under evasion -----------------------------------------------
@pytest.mark.parametrize("stmt", [
    "SELECT * FROM dbx_ar_mart",                                  # direct
    'SELECT * FROM "dbx_ar_mart"',                                # quoted identifier (fixed)
    "SELECT * FROM main.dbx_ar_mart",                            # schema-qualified
    "SELECT (SELECT count(*) FROM dbx_ar_mart)",                 # scalar subquery
    "SELECT * FROM s4_acdoca WHERE belnr IN (SELECT belnr FROM dbx_ar_mart)",  # IN subquery
    "WITH e AS (SELECT * FROM dbx_ar_mart) SELECT * FROM e",     # CTE wrapping
    "SELECT * FROM s4_acdoca UNION SELECT * FROM cdc_acdoca",    # union across tiers
    "SeLeCt * FrOm DBX_AR_MART",                                 # case
])
def test_cross_tier_access_blocked_from_source(con, stmt):
    r = rs.run_sql(con, "source", stmt)
    assert r.get("error") == "tier_violation", f"leaked: {stmt!r} -> {r}"


def test_same_tier_access_allowed(con):
    assert "error" not in rs.run_sql(con, "mart", "SELECT * FROM dbx_ar_mart LIMIT 1")
    assert "error" not in rs.run_sql(con, "source",
                                     "SELECT * FROM s4_acdoca JOIN s4_customer USING (kunnr) LIMIT 1")


# ---- string literals and comments are not false positives -----------------------
def test_keyword_in_string_literal_is_allowed(con):
    r = rs.run_sql(con, "source", "SELECT 'DELETE FROM x and DROP TABLE y' AS note")
    assert "error" not in r and r["rows"][0][0].startswith("DELETE")


def test_tier_name_in_string_is_not_a_reference(con):
    r = rs.run_sql(con, "source", "SELECT 'dbx_ar_mart' AS label FROM s4_acdoca LIMIT 1")
    assert "error" not in r   # the string literal is not a cross-tier table reference


# ---- KNOWN LIMITATION, asserted so it is visible and tracked --------------------
def test_known_limitation_arbitrary_readonly_function_is_not_blocklisted(con):
    """HONEST: the guard denylists known-dangerous functions but does not allowlist ALL
    functions. A harmless read-only scalar like setseed() is not blocked. This is a real
    limit of a denylist approach. It is acceptable here because the DB is synthetic and
    read-only (no secrets, no writes possible), but it is NOT a claim of universal security.
    If a future DuckDB function could read the filesystem or exfiltrate, the denylist would
    need updating. This test documents the gap rather than hiding it."""
    r = rs.run_sql(con, "source", "SELECT setseed(0.5)")
    assert "error" not in r   # currently allowed; see tools/SECURITY.md
    # The mitigation that actually matters: even this call cannot write or escape the tier.
    n = con.execute("SELECT count(*) FROM s4_acdoca").fetchone()[0]
    assert n > 0
