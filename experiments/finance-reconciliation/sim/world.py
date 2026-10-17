"""Deterministic clean-world builder for the finance reconciliation simulator.

Builds a seeded ACDOCA ledger plus a faithful CDC -> Datasphere -> share -> mart pipeline
that reconciles exactly (source period-movement == target period-movement). Everything is
generated from a fixed seed so a given world is byte-for-byte reproducible.

No incident is injected here. injectors.py applies defects to a clean world.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

import duckdb

from . import schema

# ---- Fixed scope (DESIGN.md 3.2) -------------------------------------------------
RCLNT, RBUKRS, RLDNR = "100", "1000", "0L"
RACCT = "0001400000"            # AR reconciliation account
GJAHR = 2026
BUDAT_FROM = date(2026, 9, 1)
BUDAT_TO = date(2026, 9, 30)
# Snapshot boundaries: the two ends of the same snapshot across the three clocks.
SNAPSHOT_WATERMARK_TS = datetime(2026, 10, 2, 0, 0, 0)   # source-side (on cpudt)
INGESTION_CUTOFF_TS = datetime(2026, 10, 3, 0, 0, 0)     # target-side (on mart_ingest_ts)
CURRENCY = "USD"
MEASURE = "period_movement"

# A different GL account, used to seed out-of-scope noise that must never affect the measure.
OTHER_ACCT = "0001500000"

FX_AVG = {"EUR": Decimal("1.08"), "GBP": Decimal("1.26")}   # average rate (used by the WRONG view)
FX_SPOT = {"EUR": Decimal("1.10"), "GBP": Decimal("1.30"), "USD": Decimal("1.00")}  # correct daily


def _bk(row: dict) -> tuple:
    return tuple(row[k] for k in schema.BUSINESS_KEY)


def _gen_lines(seed: int) -> list[dict]:
    """Generate a deterministic set of AR journal lines in the scope.

    Includes invoices (DR, positive), payments (DZ, negative), a reversal pair (DR + AB),
    foreign-currency invoices, out-of-scope rows (other account, other period, post-watermark),
    and benign CDC-lag / late-arrival distractors. All clean and self-consistent.
    """
    rnd = random.Random(seed)
    lines: list[dict] = []
    belnr_seq = 4800000000

    def add(blart, ksl, waers="USD", budat=None, cpudt=None, racct=RACCT,
            xreversing=False, xreversed_=False, augdt=None, kunnr=None):
        nonlocal belnr_seq
        belnr_seq += 1
        budat = budat or date(2026, 9, rnd.randint(1, 28))
        # clean cpudt: at or before the snapshot watermark unless caller overrides
        cpudt = cpudt or datetime(2026, 9, budat.day, rnd.randint(0, 23), rnd.randint(0, 59))
        spot = FX_SPOT.get(waers, Decimal("1.00"))
        wsl = (Decimal(ksl) / spot).quantize(Decimal("0.01")) if waers != "USD" else Decimal(ksl)
        ksl_d = Decimal(ksl).quantize(Decimal("0.01"))
        lines.append({
            "rclnt": RCLNT, "rbukrs": RBUKRS, "gjahr": GJAHR,
            "belnr": str(belnr_seq), "docln": "000001", "rldnr": RLDNR,
            "racct": racct, "kunnr": kunnr or f"C{rnd.randint(1000, 1999)}",
            "budat": budat, "bldat": budat, "blart": blart,
            "waers": waers, "hwaer": "USD", "kwaer": "USD",
            "wsl": wsl, "hsl": ksl_d, "ksl": ksl_d,
            "xreversing": xreversing, "xreversed": xreversed_,
            "augdt": augdt, "augbl": None,
            "cpudt": cpudt,
        })
        return lines[-1]

    # Core USD invoices (positive AR debits)
    for _ in range(40):
        add("DR", rnd.choice([12000, 25000, 48000, 9000, 150000, 310000]))
    # Payments (negative) and credit memos (negative)
    for _ in range(12):
        add("DZ", -rnd.choice([5000, 11000, 23000]))
    for _ in range(4):
        add("DG", -rnd.choice([4000, 7000]))
    # Foreign-currency invoices (exercised by incident 3)
    for _ in range(10):
        add("DR", rnd.choice([20000, 60000, 35000]), waers=rnd.choice(["EUR", "GBP"]))
    # A reversal pair that nets to zero
    inv = add("DR", 80000)
    add("AB", -80000, xreversing=True)
    inv["xreversed"] = True

    # ---- Out-of-scope rows that must NOT affect the measure ----
    # other account
    add("DR", 999000, racct=OTHER_ACCT)
    # other period (October)
    add("DR", 777000, budat=date(2026, 10, 5),
        cpudt=datetime(2026, 10, 5, 9, 0))
    # committed after the snapshot watermark (genuinely pending; excluded both sides)
    add("DR", 500000, budat=date(2026, 9, 29),
        cpudt=datetime(2026, 10, 2, 12, 0))  # cpudt > snapshot_watermark_ts

    return lines


def _load_source(con, lines: list[dict]) -> None:
    con.executemany(
        f"INSERT INTO s4_acdoca ({', '.join(lines[0].keys())}) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [list(l.values()) for l in lines],
    )


def _seed_reference(con) -> None:
    # Exchange rates: AVG (wrong basis for incident 3) and spot/M (correct)
    rows = []
    for waers, rate in FX_AVG.items():
        rows.append([waers, "USD", "AVG", BUDAT_FROM, float(rate)])
    for waers, rate in FX_SPOT.items():
        rows.append([waers, "USD", "M", BUDAT_FROM, float(rate)])
    con.executemany("INSERT INTO s4_tcurr VALUES (?,?,?,?,?)", rows)

    con.execute(
        """INSERT INTO recon_cutoff VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [RCLNT, RBUKRS, RLDNR, RACCT, GJAHR, BUDAT_FROM, BUDAT_TO,
         SNAPSHOT_WATERMARK_TS, INGESTION_CUTOFF_TS, CURRENCY, MEASURE],
    )


def _run_cdc_extract(con) -> None:
    """Capture every source change with cpudt <= watermark into cdc_acdoca.

    Clean behaviour: the extract captures exactly the due changes and sets the watermark
    honestly to the snapshot watermark. (Injectors perturb this.)
    """
    con.execute(
        f"""
        INSERT INTO cdc_acdoca
        SELECT {schema.BK_SQL}, racct, kunnr, budat, blart, waers, wsl, ksl,
               cpudt, cpudt + INTERVAL 2 HOUR AS cdc_capture_ts
        FROM s4_acdoca
        WHERE cpudt <= TIMESTAMP '{SNAPSHOT_WATERMARK_TS}'
        """
    )
    con.execute(
        "INSERT INTO cdc_control VALUES ('cdc_extract', ?, ?)",
        [SNAPSHOT_WATERMARK_TS, SNAPSHOT_WATERMARK_TS],
    )


def _run_mart_load(con) -> None:
    """Build dbx_ar_mart from the share with a correct, idempotent load.

    Clean behaviour: inner meaning preserved via a left-ish join to the customer snapshot
    that contains every customer (so nothing drops), one row per business key, ingested at
    a time <= ingestion cutoff. Injectors perturb join type, idempotency, and membership.
    """
    # customer snapshot contains every customer that appears (clean: no loss)
    con.execute(
        "INSERT INTO s4_customer SELECT DISTINCT kunnr, 'cust' FROM share_ar_items"
    )
    con.execute(
        f"""
        INSERT INTO dbx_ar_mart
        SELECT s.{(', s.').join(schema.BUSINESS_KEY)}, s.racct, s.kunnr, s.budat, s.blart,
               s.waers, s.amount_usd, s.cpudt,
               TIMESTAMP '{INGESTION_CUTOFF_TS}' - INTERVAL 1 HOUR AS mart_ingest_ts
        FROM share_ar_items s
        JOIN s4_customer cu ON cu.kunnr = s.kunnr
        """
    )


def _seed_green_monitoring(con) -> None:
    """Every stage SUCCESS, with plausible row counts. Green monitoring over wrong data."""
    def n(sql):
        return con.execute(sql).fetchone()[0]
    src_due = n(f"SELECT count(*) FROM s4_acdoca WHERE cpudt <= TIMESTAMP '{SNAPSHOT_WATERMARK_TS}'")
    cdc_n = n("SELECT count(*) FROM cdc_acdoca")
    mart_n = n("SELECT count(*) FROM dbx_ar_mart")
    base = datetime(2026, 10, 2, 22, 0)
    runs = [
        ("r-1001", "cdc_extract", "extract", src_due, cdc_n),
        ("r-1002", "dsp_build", "transform", cdc_n, cdc_n),
        ("r-1003", "share_publish", "publish", cdc_n, cdc_n),
        ("r-1004", "mart_load", "load", cdc_n, mart_n),
    ]
    con.executemany(
        "INSERT INTO pipeline_runs VALUES (?,?,?,'SUCCESS',?,?,?,?)",
        [[rid, pid, stg, base, base + timedelta(minutes=5), ri, ro]
         for (rid, pid, stg, ri, ro) in runs],
    )
    con.executemany(
        "INSERT INTO pipeline_config VALUES (?,?,?,?,?,?)",
        [
            ["cdc_extract", "extract", True, None, None, "watermark-driven CDC"],
            ["dsp_build", "transform", True, None, None, "group-currency passthrough"],
            ["share_publish", "publish", True, None, None, "logical share, no copy"],
            ["mart_load", "load", True, schema.BK_SQL, "inner", "idempotent merge on business key"],
        ],
    )


def build_clean(seed: int = 20260901) -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection holding a clean, reconciling world."""
    con = duckdb.connect(":memory:")
    schema.create_all(con)
    lines = _gen_lines(seed)
    _load_source(con, lines)
    _seed_reference(con)
    _run_cdc_extract(con)
    _run_mart_load(con)
    _seed_green_monitoring(con)
    return con
