# Phase 2: offline simulator and schema

Deterministic, offline DuckDB simulation of the SAP S/4HANA to Databricks reconciliation
path. No network, no SAP/BDC/Databricks connection, no real data, no Gemini calls. Implements
the schema, clean world, five incident injectors and reconciliation invariants from `DESIGN.md`.

## What is here

| File | Role |
|---|---|
| `schema.py` | DuckDB DDL for every layer; L2 (`dsp_ar_items`) and L3 (`share_ar_items`) are VIEWS, not tables; the clean and wrong-FX view definitions |
| `world.py` | `build_clean(seed)` seeds an authoritative ACDOCA ledger and runs a faithful CDC -> Datasphere -> share -> mart pipeline that reconciles exactly |
| `injectors.py` | Five incident injectors; each returns hidden truth (class, layer, affected keys, expected discrepancy) that the answer key would hold, never exposed to an agent |
| `reconcile.py` | Period-movement measure and invariant checks (missing, duplicated, amount mismatch), computed from first principles |
| `demo.py` | Prints the reproduction table below |

Three clocks (per `DESIGN.md` 3.1.1): `cpudt` (source commit), `cdc_capture_ts` (CDC capture),
`mart_ingest_ts` (downstream ingestion). The snapshot has a source-side boundary on `cpudt`
(`snapshot_watermark_ts`) and a target-side boundary on `mart_ingest_ts` (`ingestion_cutoff_ts`).

The reconciled measure is **period AR movement**: signed sum of group-currency `ksl` over the
in-scope, due-by-watermark lines. The source is authoritative and is never corrupted; defects
live only in CDC capture (L1), the transformation view (L2), or the mart load (L4).

## Reproduce (offline, free)

```bash
pip install --break-system-packages duckdb pytest          # dependencies
python experiments/finance-reconciliation/sim/demo.py       # the table below
python -m pytest experiments/finance-reconciliation/tests -q # 13 tests
```

## Result

```
CLEAN WORLD
  source=  4,442,000.00  target=  4,442,000.00  discrepancy=0.00  reconciles=True

INCIDENT                          discrepancy     expected  missing  dup  amt   result
incident1_skipped_cdc              450,000.00      450,000        3    0    0     PASS
incident2_duplicate_replay        -140,000.00     -140,000        0    2    0     PASS
incident3_currency_basis             9,881.11     computed        0    0   10     n/a
incident4_lossy_join               120,000.00      120,000        2    0    0     PASS
incident5_compound                 310,000.00      310,000        3    2    0     PASS

Compound: +450,000 (missing) + (-140,000) (duplicated) = +310,000  -> True
```

The tests additionally prove the discriminating properties: incident 4's missing rows are
present at the share but absent at the mart (incident 1's are absent at CDC too); incident 1's
skip (watermark above the line, no capture row) is distinct from benign post-watermark lag;
incident 3 passes count checks but drifts only on foreign-currency amounts; and fixing one half
of the compound case leaves a residual equal to the other half.

## Not in Phase 2

No Gemini agent, no tools layer, no grader, no answer-key file, no API calls. Those are Phases
3 to 8 in `DESIGN.md`, gated on approval.
