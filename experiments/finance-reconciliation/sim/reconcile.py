"""Reconciliation measure and invariant checks (offline, deterministic).

This is the honest comparison definition from DESIGN.md 3.2-3.3, computed from first
principles. The grader (Phase 4) and the deterministic baseline will reuse this logic;
it never reads the answer key.
"""
from __future__ import annotations

from decimal import Decimal

from . import schema


def _scope(con) -> dict:
    row = con.execute("SELECT * FROM recon_cutoff").fetchone()
    cols = [d[0] for d in con.description]
    return dict(zip(cols, row))


def source_measure(con) -> Decimal:
    """Period AR movement on the source side: signed sum of ksl over the in-scope,
    due-by-watermark rows of s4_acdoca."""
    s = _scope(con)
    v = con.execute(
        f"""
        SELECT COALESCE(SUM(ksl), 0) FROM s4_acdoca
        WHERE rclnt=? AND rbukrs=? AND rldnr=? AND racct=? AND gjahr=?
          AND budat BETWEEN ? AND ?
          AND cpudt <= ?
        """,
        [s["rclnt"], s["rbukrs"], s["rldnr"], s["racct"], s["gjahr"],
         s["budat_from"], s["budat_to"], s["snapshot_watermark_ts"]],
    ).fetchone()[0]
    return Decimal(str(v))


def target_measure(con) -> Decimal:
    """Period AR movement on the target side: signed sum of amount_usd over the in-scope
    rows of dbx_ar_mart ingested by the cutoff."""
    s = _scope(con)
    v = con.execute(
        f"""
        SELECT COALESCE(SUM(amount_usd), 0) FROM dbx_ar_mart
        WHERE rclnt=? AND rbukrs=? AND rldnr=? AND racct=? AND gjahr=?
          AND budat BETWEEN ? AND ?
          AND mart_ingest_ts <= ?
        """,
        [s["rclnt"], s["rbukrs"], s["rldnr"], s["racct"], s["gjahr"],
         s["budat_from"], s["budat_to"], s["ingestion_cutoff_ts"]],
    ).fetchone()[0]
    return Decimal(str(v))


def discrepancy(con) -> Decimal:
    """source - target (the reported variance)."""
    return source_measure(con) - target_measure(con)


# ---- Invariant checks (return the offending keys, so they double as evidence) --------

def _in_scope_source_keys(con):
    s = _scope(con)
    return f"""
        SELECT {schema.BK_SQL} FROM s4_acdoca
        WHERE rclnt='{s["rclnt"]}' AND rbukrs='{s["rbukrs"]}' AND rldnr='{s["rldnr"]}'
          AND racct='{s["racct"]}' AND gjahr={s["gjahr"]}
          AND budat BETWEEN DATE '{s["budat_from"]}' AND DATE '{s["budat_to"]}'
          AND cpudt <= TIMESTAMP '{s["snapshot_watermark_ts"]}'
    """


def _in_scope_mart_keys(con):
    s = _scope(con)
    return f"""
        SELECT {schema.BK_SQL} FROM dbx_ar_mart
        WHERE rclnt='{s["rclnt"]}' AND rbukrs='{s["rbukrs"]}' AND rldnr='{s["rldnr"]}'
          AND racct='{s["racct"]}' AND gjahr={s["gjahr"]}
          AND budat BETWEEN DATE '{s["budat_from"]}' AND DATE '{s["budat_to"]}'
          AND mart_ingest_ts <= TIMESTAMP '{s["ingestion_cutoff_ts"]}'
    """


def missing_at_mart(con) -> list[tuple]:
    """INV-1: in-scope source keys with no in-scope mart row."""
    return con.execute(
        f"SELECT {schema.BK_SQL} FROM ({_in_scope_source_keys(con)}) "
        f"EXCEPT SELECT {schema.BK_SQL} FROM ({_in_scope_mart_keys(con)})"
    ).fetchall()


def duplicated_at_mart(con) -> list[tuple]:
    """INV-2: business keys appearing more than once in the in-scope mart."""
    return con.execute(
        f"SELECT {schema.BK_SQL} FROM ({_in_scope_mart_keys(con)}) "
        f"GROUP BY {schema.BK_SQL} HAVING count(*) > 1"
    ).fetchall()


def amount_mismatches(con) -> list[tuple]:
    """INV-3: in-scope keys present on both sides whose amounts differ (currency drift).
    Returns (business key..., source_ksl, target_amount)."""
    s = _scope(con)
    return con.execute(
        f"""
        WITH src AS ({_in_scope_source_keys(con)}),
             m AS (
               SELECT {schema.BK_SQL}, amount_usd FROM dbx_ar_mart
               WHERE racct='{s["racct"]}' AND mart_ingest_ts <= TIMESTAMP '{s["ingestion_cutoff_ts"]}'
             )
        SELECT a.{(', a.').join(schema.BUSINESS_KEY)}, a.ksl, m.amount_usd
        FROM s4_acdoca a
        JOIN src USING ({schema.BK_SQL})
        JOIN m    USING ({schema.BK_SQL})
        WHERE a.ksl <> m.amount_usd
        """
    ).fetchall()


def reconciles(con, tol: Decimal = Decimal("0.01")) -> bool:
    """A world reconciles when the signed measures agree and no structural invariant is broken."""
    return (
        abs(discrepancy(con)) <= tol
        and not missing_at_mart(con)
        and not duplicated_at_mart(con)
        and not amount_mismatches(con)
    )


def summary(con) -> dict:
    return {
        "source": float(source_measure(con)),
        "target": float(target_measure(con)),
        "discrepancy": float(discrepancy(con)),
        "missing_at_mart": len(missing_at_mart(con)),
        "duplicated_at_mart": len(duplicated_at_mart(con)),
        "amount_mismatches": len(amount_mismatches(con)),
        "reconciles": reconciles(con),
    }
