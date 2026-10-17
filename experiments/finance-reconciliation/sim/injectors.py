"""Five incident injectors (DESIGN.md section 4). Offline, deterministic.

Each injector takes a clean world (a DuckDB connection from world.build_clean) and applies
one or two defects, returning a dict of hidden truth (incident class, root-cause layer,
affected business keys, expected discrepancy, safe remediations). That truth is what the
answer key would hold; it is returned to the builder/grader, never exposed to the agent.

Design rule: the source (s4_acdoca) is authoritative and is never corrupted. Defects live
in CDC capture (L1), the transformation view (L2), or the mart load (L4). Each injector adds
whole, clean-looking accounting rows and then breaks their propagation, so the affected keys
remain ordinary, queryable records with no defect label (DESIGN.md 6.1.1).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from . import schema, world

WM = world.SNAPSHOT_WATERMARK_TS            # source-side snapshot boundary (on cpudt)
CUT = world.INGESTION_CUTOFF_TS             # target-side snapshot boundary (on mart_ingest_ts)
MART_TS = CUT - timedelta(hours=1)          # a clean in-snapshot mart ingest time


def _insert_source(con, belnr, ksl, *, blart="DR", waers="USD", kunnr="C1500",
                   budat=date(2026, 9, 15), cpudt=None):
    """Insert one authoritative source AR line and return its business key."""
    cpudt = cpudt or datetime(2026, 9, 15, 10, 0)
    spot = world.FX_SPOT.get(waers, Decimal("1.00"))
    ksl_d = Decimal(ksl).quantize(Decimal("0.01"))
    wsl = (ksl_d / spot).quantize(Decimal("0.01")) if waers != "USD" else ksl_d
    con.execute(
        f"INSERT INTO s4_acdoca ({', '.join(_COLS)}) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [world.RCLNT, world.RBUKRS, world.GJAHR, str(belnr), "000001", world.RLDNR,
         world.RACCT, kunnr, budat, budat, blart, waers, "USD", "USD",
         wsl, ksl_d, ksl_d, False, False, None, None, cpudt],
    )
    return (world.RCLNT, world.RBUKRS, world.GJAHR, str(belnr), "000001", world.RLDNR)


_COLS = ["rclnt", "rbukrs", "gjahr", "belnr", "docln", "rldnr", "racct", "kunnr",
         "budat", "bldat", "blart", "waers", "hwaer", "kwaer", "wsl", "hsl", "ksl",
         "xreversing", "xreversed", "augdt", "augbl", "cpudt"]


def _capture(con, bk, ksl, *, waers="USD", kunnr="C1500", budat=date(2026, 9, 15),
             cpudt=None):
    """Capture a source key into cdc_acdoca (so L2/L3/share see it). Clean propagation."""
    cpudt = cpudt or datetime(2026, 9, 15, 10, 0)
    spot = world.FX_SPOT.get(waers, Decimal("1.00"))
    ksl_d = Decimal(ksl).quantize(Decimal("0.01"))
    wsl = (ksl_d / spot).quantize(Decimal("0.01")) if waers != "USD" else ksl_d
    con.execute(
        "INSERT INTO cdc_acdoca VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [*bk, world.RACCT, kunnr, budat, "DR", waers, wsl, ksl_d, cpudt,
         cpudt + timedelta(hours=2)],
    )


def _mart_insert(con, bk, amount, *, kunnr="C1500", budat=date(2026, 9, 15),
                 waers="USD", cpudt=None, ingest_ts=None):
    cpudt = cpudt or datetime(2026, 9, 15, 10, 0)
    con.execute(
        "INSERT INTO dbx_ar_mart VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [*bk, world.RACCT, kunnr, budat, "DR", waers,
         Decimal(amount).quantize(Decimal("0.01")), cpudt, ingest_ts or MART_TS],
    )


# --------------------------------------------------------------------------------
# Incident 1: skipped CDC batch (watermark above the lines, yet no capture row)
# --------------------------------------------------------------------------------
def inject_skipped_cdc(con, amount=450_000, n=3, base=4810000100) -> dict:
    per = amount // n
    skipped = []
    for i in range(n):
        bk = _insert_source(con, base + i, per,
                            cpudt=datetime(2026, 9, 20, 8, 0))  # cpudt <= watermark
        skipped.append(bk)
    # The lines are committed and due (cpudt <= watermark) but were NOT captured: no cdc row,
    # so they never reach the share or the mart. Watermark already sits at WM (>= their cpudt).
    # Benign distractor: a line with cpudt AFTER the watermark (normal lag; correctly pending).
    _insert_source(con, base + 800, 99_000, cpudt=datetime(2026, 10, 2, 12, 0))
    return {
        "incident": "missing_cdc_delta",
        "root_cause_layer": ["L1"],
        "affected_keys": {"missing": skipped},
        "expected_discrepancy": float(amount),   # source exceeds target
        "safe_remediations": ["reextract_batch"],
        "benign_distractor_note": "4810000900 is post-watermark lag, not a defect",
    }


# --------------------------------------------------------------------------------
# Incident 2: duplicate downstream replay (non-idempotent load)
# --------------------------------------------------------------------------------
def inject_duplicate_replay(con, amount=140_000, n=2, base=4820000100) -> dict:
    per = amount // n
    dups = []
    for i in range(n):
        bk = _insert_source(con, base + i, per)
        _capture(con, bk, per)                       # correctly captured and shared
        _mart_insert(con, bk, per)                   # legitimate single copy
        _mart_insert(con, bk, per)                   # the replayed duplicate (defect)
        dups.append(bk)
    con.execute("UPDATE pipeline_config SET idempotent=false, note='replay not de-duplicated' "
                "WHERE pipeline_id='mart_load'")
    con.execute("INSERT INTO pipeline_runs VALUES "
                "('r-1005','mart_load','load','SUCCESS', ?, ?, ?, ?)",
                [datetime(2026, 10, 2, 23, 0), datetime(2026, 10, 2, 23, 5), n, n])
    return {
        "incident": "duplicate_replay",
        "root_cause_layer": ["L4"],
        "affected_keys": {"duplicated": dups},
        "expected_discrepancy": float(-amount),  # target exceeds source
        "safe_remediations": ["dedupe_target", "reload_idempotent"],
    }


# --------------------------------------------------------------------------------
# Incident 3: wrong currency translation basis (counts match, amounts drift)
# --------------------------------------------------------------------------------
def inject_currency_basis(con) -> dict:
    # Swap the L2 view for the wrong-FX variant. Foreign-currency rows now re-translate
    # wsl with the AVG rate instead of carrying ksl. USD rows unaffected.
    con.execute(schema.DSP_AR_ITEMS_WRONG_FX)
    # Rebuild the mart from the (now wrong) share, idempotent, no row loss or dup.
    con.execute("DELETE FROM dbx_ar_mart")
    con.execute(
        f"""
        INSERT INTO dbx_ar_mart
        SELECT s.{(', s.').join(schema.BUSINESS_KEY)}, s.racct, s.kunnr, s.budat, s.blart,
               s.waers, s.amount_usd, s.cpudt, TIMESTAMP '{MART_TS}'
        FROM share_ar_items s JOIN s4_customer cu ON cu.kunnr = s.kunnr
        """
    )
    # Affected keys: in-scope foreign-currency rows (amount differs source vs mart).
    affected = con.execute(
        f"""
        SELECT a.{(', a.').join(schema.BUSINESS_KEY)} FROM s4_acdoca a
        JOIN dbx_ar_mart m USING ({schema.BK_SQL})
        WHERE a.racct='{world.RACCT}' AND a.waers <> 'USD'
          AND a.budat BETWEEN DATE '{world.BUDAT_FROM}' AND DATE '{world.BUDAT_TO}'
          AND a.cpudt <= TIMESTAMP '{WM}'
          AND a.ksl <> m.amount_usd
        """
    ).fetchall()
    return {
        "incident": "currency_basis",
        "root_cause_layer": ["L2"],
        "affected_keys": {"amount_mismatch": affected},
        "expected_discrepancy": None,   # computed; counts match, amounts drift
        "safe_remediations": ["fix_transform"],
    }


# --------------------------------------------------------------------------------
# Incident 4: silent loss from a downstream inner join (rows present at share, dropped at mart)
# --------------------------------------------------------------------------------
def inject_lossy_join(con, amount=120_000, n=2, base=4840000100) -> dict:
    per = amount // n
    dropped = []
    for i in range(n):
        bk = _insert_source(con, base + i, per, kunnr=f"CMISSING{base}{i}")
        _capture(con, bk, per, kunnr=f"CMISSING{base}{i}")   # present at share
        dropped.append(bk)
        # NOTE: customer CMISSINGi deliberately absent from s4_customer snapshot ->
        # the inner join in the mart load drops these rows. Mart never gets them.
    con.execute("UPDATE pipeline_config SET join_type='inner', "
                "note='inner join to stale customer snapshot' WHERE pipeline_id='mart_load'")
    return {
        "incident": "lossy_join",
        "root_cause_layer": ["L4"],
        "affected_keys": {"missing": dropped},
        "expected_discrepancy": float(amount),   # source exceeds target
        # Only remediations that actually reconcile the loss belong here. refresh_customer_snapshot
        # re-includes the dropped customers and reloads; fix_transform alone does NOT recover rows
        # the inner join dropped (verified in Phase 6), so it is not a safe remediation here.
        "safe_remediations": ["refresh_customer_snapshot"],
        "distinct_from_incident1": "present at share/L2, absent only at mart",
    }


# --------------------------------------------------------------------------------
# Incident 5: compound, two offsetting L4 defects, net +310K
# --------------------------------------------------------------------------------
def inject_compound(con, missing=450_000, dup=140_000, n_missing=3, n_dup=2,
                    base=4850000100) -> dict:
    # Defect A: positive invoices present at source+share but missing from the mart.
    a_keys = []
    for i in range(n_missing):
        bk = _insert_source(con, base + i, missing // n_missing, kunnr=f"CGONE{base}{i}")
        _capture(con, bk, missing // n_missing, kunnr=f"CGONE{base}{i}")  # at share, not at mart
        a_keys.append(bk)
    # Defect B: positive invoices duplicated in the mart.
    b_keys = []
    for i in range(n_dup):
        bk = _insert_source(con, base + 100 + i, dup // n_dup)
        _capture(con, bk, dup // n_dup)
        _mart_insert(con, bk, dup // n_dup)      # legit single copy
        _mart_insert(con, bk, dup // n_dup)      # duplicate
        b_keys.append(bk)
    con.execute("UPDATE pipeline_config SET idempotent=false WHERE pipeline_id='mart_load'")
    return {
        "incident": "compound",
        "root_cause_layer": ["L4", "L4"],
        "affected_keys": {"missing": a_keys, "duplicated": b_keys},
        "expected_discrepancy": float(missing - dup),   # +450K - 140K = +310K
        "decomposition": {"missing_contrib": float(missing), "dup_contrib": float(-dup)},
        "safe_remediations": ["backfill_missing", "dedupe_target"],
    }


INJECTORS = {
    "incident1_skipped_cdc": inject_skipped_cdc,
    "incident2_duplicate_replay": inject_duplicate_replay,
    "incident3_currency_basis": inject_currency_basis,
    "incident4_lossy_join": inject_lossy_join,
    "incident5_compound": inject_compound,
}


def build_incident(name: str, seed: int = 20260901, **inject_kwargs):
    """Build a clean world and inject the named incident. Returns (con, truth).

    inject_kwargs are passed to the injector (amount, n, base, ...), letting the test-set
    generator vary magnitudes, counts and key ranges without changing dev defaults.
    """
    con = world.build_clean(seed)
    truth = INJECTORS[name](con, **inject_kwargs)
    return con, truth
