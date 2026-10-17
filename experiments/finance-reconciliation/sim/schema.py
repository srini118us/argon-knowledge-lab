"""DuckDB schema for the finance reconciliation simulator (Experiment 3, Phase 2).

Offline and deterministic. No network, no SAP/BDC/Databricks connection, no real data.

Layers (see DESIGN.md section 2.3):
  L0 source     s4_acdoca            physical table, system of record (authoritative)
  L1 cdc        cdc_acdoca           physical captured rows   + cdc_control watermark
  L2 datasphere dsp_ar_items         VIEW over cdc_acdoca (business mapping, currency)
  L3 share      share_ar_items       VIEW over dsp_ar_items (logical share, no copy)
  L4 mart       dbx_ar_mart          physical table built by the consumer load
  M  metadata   pipeline_runs, pipeline_config, recon_cutoff, s4_tcurr, s4_customer

Three clocks (DESIGN.md 3.1.1):
  cpudt           on s4_acdoca          source commit/change time
  cdc_capture_ts  on cdc_acdoca         when CDC read the change
  mart_ingest_ts  on dbx_ar_mart        when the consumer load wrote the row

The L2 and L3 objects are VIEWS, not tables: they recompute on read, which is why a
transformation defect (incident 3) lives in a view definition and is not a copied row.
"""
from __future__ import annotations

# Composite business key, used everywhere downstream and in the answer key.
BUSINESS_KEY = ("rclnt", "rbukrs", "gjahr", "belnr", "docln", "rldnr")
BK_SQL = ", ".join(BUSINESS_KEY)

# Physical source table: the SAP universal journal line items (ACDOCA-inspired).
DDL_S4_ACDOCA = """
CREATE TABLE s4_acdoca (
    rclnt       VARCHAR,          -- client
    rbukrs      VARCHAR,          -- company code
    gjahr       SMALLINT,         -- fiscal year
    belnr       VARCHAR,          -- accounting document number
    docln       VARCHAR,          -- line item
    rldnr       VARCHAR,          -- ledger (0L leading)
    racct       VARCHAR,          -- GL account (AR reconciliation account)
    kunnr       VARCHAR,          -- customer
    budat       DATE,             -- posting date
    bldat       DATE,             -- document date
    blart       VARCHAR,          -- document type: DR invoice, DZ payment, DG credit memo, AB reversal
    waers       VARCHAR,          -- document currency
    hwaer       VARCHAR,          -- local currency
    kwaer       VARCHAR,          -- group currency
    wsl         DECIMAL(23,2),    -- amount in document currency, signed
    hsl         DECIMAL(23,2),    -- amount in local currency, signed
    ksl         DECIMAL(23,2),    -- amount in group currency, signed  (the reconciled amount)
    xreversing  BOOLEAN,
    xreversed   BOOLEAN,
    augdt       DATE,             -- clearing date (null if open)
    augbl       VARCHAR,          -- clearing document (null if open)
    cpudt       TIMESTAMP         -- SOURCE commit/change timestamp (clock 1)
);
"""

# Exchange rates (for incident 3: a wrong rate type/date gives a wrong USD amount).
DDL_S4_TCURR = """
CREATE TABLE s4_tcurr (
    from_waers  VARCHAR,
    to_waers    VARCHAR,
    rate_type   VARCHAR,          -- e.g. 'M' daily/spot, 'AVG' average
    rate_date   DATE,
    rate        DECIMAL(18,6)
);
"""

# Customer master snapshot held by the consumer (for incident 4: inner-join loss).
DDL_S4_CUSTOMER = """
CREATE TABLE s4_customer (
    kunnr   VARCHAR,
    name    VARCHAR
);
"""

# L1: captured CDC rows. Each carries the cpudt it saw and its own capture time (clock 2).
DDL_CDC_ACDOCA = """
CREATE TABLE cdc_acdoca (
    rclnt VARCHAR, rbukrs VARCHAR, gjahr SMALLINT, belnr VARCHAR, docln VARCHAR, rldnr VARCHAR,
    racct VARCHAR, kunnr VARCHAR, budat DATE, blart VARCHAR,
    waers VARCHAR, wsl DECIMAL(23,2), ksl DECIMAL(23,2),
    cpudt TIMESTAMP,          -- the source change time this capture row reflects
    cdc_capture_ts TIMESTAMP  -- CDC capture time (clock 2)
);
"""

# L1 control: the watermark the extract claims to have processed up to.
DDL_CDC_CONTROL = """
CREATE TABLE cdc_control (
    pipeline_id          VARCHAR,
    high_water_mark_ts   TIMESTAMP,   -- highest cpudt the extract claims to have processed
    last_run_ts          TIMESTAMP
);
"""

# L4: the consumer's materialized mart. mart_ingest_ts is clock 3.
DDL_DBX_AR_MART = """
CREATE TABLE dbx_ar_mart (
    rclnt VARCHAR, rbukrs VARCHAR, gjahr SMALLINT, belnr VARCHAR, docln VARCHAR, rldnr VARCHAR,
    racct VARCHAR, kunnr VARCHAR, budat DATE, blart VARCHAR,
    waers VARCHAR, amount_usd DECIMAL(23,2),   -- the mart's AR amount (should equal source ksl)
    cpudt TIMESTAMP,
    mart_ingest_ts TIMESTAMP   -- downstream ingestion time (clock 3)
);
"""

# M: pipeline configuration (filters, watermark copy, idempotency flag, join type).
DDL_PIPELINE_CONFIG = """
CREATE TABLE pipeline_config (
    pipeline_id   VARCHAR,
    stage         VARCHAR,
    idempotent    BOOLEAN,
    merge_key     VARCHAR,
    join_type     VARCHAR,
    note          VARCHAR
);
"""

# M: pipeline run history. Every row is SUCCESS by design (green monitoring).
DDL_PIPELINE_RUNS = """
CREATE TABLE pipeline_runs (
    run_id     VARCHAR,
    pipeline_id VARCHAR,
    stage      VARCHAR,
    status     VARCHAR,       -- always 'SUCCESS' in these incidents
    started_ts TIMESTAMP,
    ended_ts   TIMESTAMP,
    rows_in    BIGINT,
    rows_out   BIGINT
);
"""

# M: the agreed reconciliation scope and snapshot (one row). The honest comparison definition.
DDL_RECON_CUTOFF = """
CREATE TABLE recon_cutoff (
    rclnt                VARCHAR,
    rbukrs               VARCHAR,
    rldnr                VARCHAR,
    racct                VARCHAR,
    gjahr                SMALLINT,
    budat_from           DATE,
    budat_to             DATE,
    snapshot_watermark_ts TIMESTAMP,   -- source-side snapshot boundary (on cpudt)
    ingestion_cutoff_ts  TIMESTAMP,    -- target-side snapshot boundary (on mart_ingest_ts)
    currency             VARCHAR,      -- 'USD' (group ksl)
    measure              VARCHAR       -- 'period_movement'
);
"""

PHYSICAL_TABLES_DDL = [
    DDL_S4_ACDOCA, DDL_S4_TCURR, DDL_S4_CUSTOMER,
    DDL_CDC_ACDOCA, DDL_CDC_CONTROL, DDL_DBX_AR_MART,
    DDL_PIPELINE_CONFIG, DDL_PIPELINE_RUNS, DDL_RECON_CUTOFF,
]

# L2 Datasphere view: business mapping from captured rows to the AR data product.
# The CLEAN definition carries the group-currency ksl straight through (correct basis).
# Incident 3 swaps this definition for one that re-translates wsl with the wrong rate.
DSP_AR_ITEMS_CLEAN = f"""
CREATE OR REPLACE VIEW dsp_ar_items AS
SELECT {BK_SQL}, racct, kunnr, budat, blart, waers,
       ksl AS amount_usd,           -- clean: carry group currency through (correct basis)
       cpudt, cdc_capture_ts
FROM cdc_acdoca;
"""

# Incident 3 variant: wrong currency basis. Re-translate document currency with the AVG
# rate instead of carrying ksl. USD rows are unaffected; foreign-currency rows drift.
DSP_AR_ITEMS_WRONG_FX = f"""
CREATE OR REPLACE VIEW dsp_ar_items AS
SELECT c.{(', c.').join(BUSINESS_KEY)}, c.racct, c.kunnr, c.budat, c.blart, c.waers,
       CASE WHEN c.waers = 'USD' THEN c.ksl
            ELSE round(c.wsl * COALESCE(r.rate, 1.0), 2)
       END AS amount_usd,
       c.cpudt, c.cdc_capture_ts
FROM cdc_acdoca c
LEFT JOIN s4_tcurr r
  ON r.from_waers = c.waers AND r.to_waers = 'USD' AND r.rate_type = 'AVG';
"""

# L3 share view: a logical share over the provider's data product. No row duplication.
SHARE_AR_ITEMS = f"""
CREATE OR REPLACE VIEW share_ar_items AS
SELECT {BK_SQL}, racct, kunnr, budat, blart, waers, amount_usd, cpudt, cdc_capture_ts
FROM dsp_ar_items;
"""


def create_all(con) -> None:
    """Create every physical table and the L2/L3 views (clean definitions)."""
    for ddl in PHYSICAL_TABLES_DDL:
        con.execute(ddl)
    con.execute(DSP_AR_ITEMS_CLEAN)
    con.execute(SHARE_AR_ITEMS)
