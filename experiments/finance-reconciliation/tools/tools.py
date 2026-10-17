"""The remaining four agent tools (DESIGN.md 5.2-5.5), plus a Tools facade.

  get_pipeline_metadata(pipeline_id)
  inspect_transformation_logic(view_name)
  simulate_remediation(action_type, parameters)   -- isolated, reversible, never mutates base
  submit_investigation_verdict(...)

All tools are deterministic and offline. simulate_remediation operates on an isolated
overlay (a scratch copy of the mutable layers) and provably never changes the base
connection; the base is re-measured after every simulation to assert immutability.

No tool exposes the hidden answer key or the injector parameters.
"""
from __future__ import annotations

import copy
import json
import re
import uuid

import duckdb

from sim import reconcile, schema
from . import run_sql as rs

PIPELINES = {"cdc_extract", "dsp_build", "share_publish", "mart_load"}
VIEWS = {"dsp_ar_items", "share_ar_items", "dbx_ar_mart_load"}

VERDICT_CLASSES = {"missing_cdc_delta", "duplicate_replay", "currency_basis",
                   "lossy_join", "compound"}
VERDICT_LAYERS = {"L1", "L2", "L3", "L4"}

SIM_ACTIONS = {"reextract_batch", "backfill_missing", "dedupe_target",
               "reload_idempotent", "fix_transform", "refresh_customer_snapshot"}


# --------------------------------------------------------------------------------
# 5.2 get_pipeline_metadata
# --------------------------------------------------------------------------------
def get_pipeline_metadata(con, pipeline_id: str, *, log: list | None = None) -> dict:
    if pipeline_id not in PIPELINES:
        out = {"error": "unknown_pipeline", "detail": f"pipeline must be one of {sorted(PIPELINES)}"}
        _log(log, "get_pipeline_metadata", {"pipeline_id": pipeline_id}, out)
        return out
    cfg_rows = con.execute(
        "SELECT stage, idempotent, merge_key, join_type, note FROM pipeline_config WHERE pipeline_id=?",
        [pipeline_id],
    ).fetchall()
    config = {}
    for stage, idem, mk, jt, note in cfg_rows:
        config = {"stage": stage, "idempotent": idem, "merge_key": mk, "join_type": jt, "note": note}
    # CDC timestamps belong to the extract pipeline.
    if pipeline_id == "cdc_extract":
        wm = con.execute("SELECT high_water_mark_ts FROM cdc_control WHERE pipeline_id='cdc_extract'").fetchone()
        if wm:
            config["high_water_mark_ts"] = wm[0].isoformat()
    runs = con.execute(
        "SELECT run_id, stage, status, started_ts, ended_ts, rows_in, rows_out "
        "FROM pipeline_runs WHERE pipeline_id=? ORDER BY started_ts", [pipeline_id],
    ).fetchall()
    out = {
        "pipeline_id": pipeline_id,
        "config": config,
        "runs": [
            {"run_id": r[0], "stage": r[1], "status": r[2],
             "started_ts": r[3].isoformat() if r[3] else None,
             "ended_ts": r[4].isoformat() if r[4] else None,
             "rows_in": r[5], "rows_out": r[6]}
            for r in runs
        ],
    }
    _log(log, "get_pipeline_metadata", {"pipeline_id": pipeline_id}, None)
    return out


# --------------------------------------------------------------------------------
# 5.3 inspect_transformation_logic
# --------------------------------------------------------------------------------
def inspect_transformation_logic(con, view_name: str, *, log: list | None = None) -> dict:
    if view_name not in VIEWS:
        out = {"error": "unknown_view", "detail": f"view must be one of {sorted(VIEWS)}"}
        _log(log, "inspect_transformation_logic", {"view_name": view_name}, out)
        return out
    if view_name in ("dsp_ar_items", "share_ar_items"):
        definition = con.execute(
            "SELECT sql FROM duckdb_views() WHERE view_name=?", [view_name]
        ).fetchone()
        definition = definition[0] if definition else ""
        mapping = _mapping_for_view(view_name, definition)
    else:
        # dbx_ar_mart_load is not a DB view; its logic is described by pipeline_config.
        cfg = con.execute(
            "SELECT join_type, merge_key, idempotent, note FROM pipeline_config WHERE pipeline_id='mart_load'"
        ).fetchone()
        definition = (f"load dbx_ar_mart from share_ar_items; join_type={cfg[0]}; "
                      f"merge_key={cfg[1]}; idempotent={cfg[2]}")
        mapping = {"join": cfg[0], "merge_key": cfg[1], "idempotent": cfg[2]}
    out = {"view": view_name, "definition": definition, "mapping": mapping}
    _log(log, "inspect_transformation_logic", {"view_name": view_name}, None)
    return out


def _mapping_for_view(view_name: str, definition: str) -> dict:
    """A neutral structured mapping. Describes the currency basis factually, WITHOUT any
    'this is the bug' annotation (DESIGN.md 6.1.1): the evidence is present, the label is not."""
    d = definition.lower()
    if "s4_tcurr" in d or "rate" in d:
        basis = "re-translate wsl via s4_tcurr rate"     # factual, not 'wrong'
    elif "ksl" in d:
        basis = "carry ksl (group currency)"
    else:
        basis = "unknown"
    return {"amount_usd": {"basis": basis}}


# --------------------------------------------------------------------------------
# 5.4 simulate_remediation  (isolated overlay; never mutates base)
# --------------------------------------------------------------------------------
def _clone_world(con) -> duckdb.DuckDBPyConnection:
    """Build a scratch DuckDB holding copies of every physical table, plus the live view
    definitions, so a remediation can be applied and reconciled without touching base."""
    scratch = duckdb.connect(":memory:")
    schema.create_all(scratch)   # tables + clean views
    phys = ["s4_acdoca", "s4_tcurr", "s4_customer", "cdc_acdoca", "cdc_control",
            "dbx_ar_mart", "pipeline_config", "pipeline_runs", "recon_cutoff"]
    for t in phys:
        rows = con.execute(f"SELECT * FROM {t}").fetchall()
        if rows:
            ph = ",".join(["?"] * len(rows[0]))
            scratch.executemany(f"INSERT INTO {t} VALUES ({ph})", [list(r) for r in rows])
    # carry over the live dsp_ar_items definition (it may be the wrong-FX variant)
    live = con.execute("SELECT sql FROM duckdb_views() WHERE view_name='dsp_ar_items'").fetchone()
    if live and "s4_tcurr" in live[0].lower():
        scratch.execute(schema.DSP_AR_ITEMS_WRONG_FX)
    return scratch


def _recon_snapshot(con) -> dict:
    return {
        "ar_source": float(reconcile.source_measure(con)),
        "ar_target": float(reconcile.target_measure(con)),
        "discrepancy": float(reconcile.discrepancy(con)),
        "missing_at_mart": len(reconcile.missing_at_mart(con)),
        "duplicated_at_mart": len(reconcile.duplicated_at_mart(con)),
        "amount_mismatches": len(reconcile.amount_mismatches(con)),
    }


def simulate_remediation(con, action_type: str, parameters: dict | None = None,
                         *, log: list | None = None) -> dict:
    """Apply a remediation to an ISOLATED clone and return before/after. Base is untouched.

    Returns an error (flagged as unsafe) for any non-enumerated action or any attempt to
    pass raw SQL. The base connection's reconciliation is identical before and after.
    """
    parameters = parameters or {}
    base_before = _recon_snapshot(con)

    # Safety: reject raw SQL or base-state targeting as an UNSAFE action (flagged).
    if "sql" in parameters or "query" in parameters or parameters.get("target") == "base":
        out = {"error": "unsafe_action",
               "detail": "direct mutation of base state is not permitted", "flagged": True}
        _log(log, "simulate_remediation", {"action_type": action_type}, out, unsafe=True)
        _assert_base_unchanged(con, base_before)
        return out
    if action_type not in SIM_ACTIONS:
        out = {"error": "unknown_action", "detail": f"action must be one of {sorted(SIM_ACTIONS)}"}
        _log(log, "simulate_remediation", {"action_type": action_type}, out)
        _assert_base_unchanged(con, base_before)
        return out

    scratch = _clone_world(con)
    before = _recon_snapshot(scratch)
    try:
        _apply_action(scratch, action_type, parameters)
    except _BadParams as e:
        scratch.close()
        out = {"error": "invalid_parameters", "detail": str(e)}
        _log(log, "simulate_remediation", {"action_type": action_type, "parameters": parameters}, out)
        _assert_base_unchanged(con, base_before)
        return out
    after = _recon_snapshot(scratch)
    scratch.close()

    _assert_base_unchanged(con, base_before)   # the base MUST be identical
    out = {
        "simulation_id": "sim-" + uuid.uuid4().hex[:8],
        "action_type": action_type,
        "before": before, "after": after, "reversible": True,
    }
    _log(log, "simulate_remediation", {"action_type": action_type, "parameters": parameters}, None)
    return out


class _BadParams(Exception):
    pass


def _keys_from_params(parameters) -> list[list]:
    keys = parameters.get("business_keys") or parameters.get("keys")
    if not keys:
        raise _BadParams("business_keys required for this action")
    norm = []
    for k in keys:
        if isinstance(k, str):   # "100/1000/2026/4800000001/000001/0L"
            parts = k.split("/")
            if len(parts) != 6:
                raise _BadParams(f"malformed business key: {k}")
            norm.append(parts)
        elif isinstance(k, (list, tuple)) and len(k) == 6:
            norm.append(list(k))
        else:
            raise _BadParams(f"malformed business key: {k}")
    return norm


def _apply_action(scratch, action_type: str, parameters: dict) -> None:
    """Apply the remediation to the scratch overlay only."""
    if action_type in ("reextract_batch", "backfill_missing"):
        # Bring the named missing keys into the mart from the source (authoritative).
        keys = _keys_from_params(parameters)
        for k in keys:
            row = scratch.execute(
                f"SELECT ksl, kunnr, budat, waers, cpudt FROM s4_acdoca "
                f"WHERE {_key_where()}", k).fetchone()
            if row is None:
                continue
            scratch.execute(
                "INSERT INTO dbx_ar_mart VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [*k, "0001400000", row[1], row[2], "DR", row[3], row[0], row[4],
                 scratch.execute("SELECT ingestion_cutoff_ts FROM recon_cutoff").fetchone()[0]],
            )
    elif action_type in ("dedupe_target", "reload_idempotent"):
        # Keep exactly one mart row per business key.
        scratch.execute(
            f"""
            CREATE TABLE _dedup AS
            SELECT * FROM dbx_ar_mart
            QUALIFY row_number() OVER (PARTITION BY {schema.BK_SQL} ORDER BY mart_ingest_ts) = 1
            """
        )
        scratch.execute("DELETE FROM dbx_ar_mart")
        scratch.execute("INSERT INTO dbx_ar_mart SELECT * FROM _dedup")
        scratch.execute("DROP TABLE _dedup")
    elif action_type == "fix_transform":
        # Swap the L2 view back to the correct ksl-passthrough and rebuild the mart.
        scratch.execute(schema.DSP_AR_ITEMS_CLEAN)
        scratch.execute("DELETE FROM dbx_ar_mart")
        scratch.execute(
            f"""
            INSERT INTO dbx_ar_mart
            SELECT s.{(', s.').join(schema.BUSINESS_KEY)}, s.racct, s.kunnr, s.budat, s.blart,
                   s.waers, s.amount_usd, s.cpudt,
                   (SELECT ingestion_cutoff_ts FROM recon_cutoff) - INTERVAL 1 HOUR
            FROM share_ar_items s JOIN s4_customer cu ON cu.kunnr = s.kunnr
            """
        )
    elif action_type == "refresh_customer_snapshot":
        # Add any customers referenced by the share but missing from the snapshot, then reload.
        scratch.execute(
            "INSERT INTO s4_customer SELECT DISTINCT kunnr, 'cust' FROM share_ar_items "
            "WHERE kunnr NOT IN (SELECT kunnr FROM s4_customer)"
        )
        scratch.execute("DELETE FROM dbx_ar_mart")
        scratch.execute(
            f"""
            INSERT INTO dbx_ar_mart
            SELECT s.{(', s.').join(schema.BUSINESS_KEY)}, s.racct, s.kunnr, s.budat, s.blart,
                   s.waers, s.amount_usd, s.cpudt,
                   (SELECT ingestion_cutoff_ts FROM recon_cutoff) - INTERVAL 1 HOUR
            FROM share_ar_items s JOIN s4_customer cu ON cu.kunnr = s.kunnr
            """
        )


def _key_where() -> str:
    return " AND ".join(f"{c}=?" for c in schema.BUSINESS_KEY)


def _assert_base_unchanged(con, before: dict) -> None:
    after = _recon_snapshot(con)
    if after != before:   # pragma: no cover - a guard that must never fire
        raise RuntimeError("simulate_remediation mutated the base state (isolation breach)")


# --------------------------------------------------------------------------------
# 5.5 submit_investigation_verdict
# --------------------------------------------------------------------------------
def submit_investigation_verdict(verdict: dict, *, log: list | None = None) -> dict:
    """Validate the final structured diagnosis. Records (does not trust) the verification
    block. Returns {'accepted': True, ...} or a schema error WITHOUT ending the run."""
    errs = []
    rcs = verdict.get("root_causes")
    if not isinstance(rcs, list) or not rcs:
        errs.append("root_causes must be a non-empty list")
    else:
        for rc in rcs:
            if rc.get("incident_class") not in VERDICT_CLASSES:
                errs.append(f"invalid incident_class: {rc.get('incident_class')}")
            if rc.get("layer") not in VERDICT_LAYERS:
                errs.append(f"invalid layer: {rc.get('layer')}")
    if not isinstance(verdict.get("affected_business_keys"), list):
        errs.append("affected_business_keys must be a list")
    if not isinstance(verdict.get("proposed_remediations"), list):
        errs.append("proposed_remediations must be a list")
    if errs:
        out = {"error": "schema_invalid", "detail": errs}
        _log(log, "submit_investigation_verdict", {"verdict": "<invalid>"}, out)
        return out
    out = {"accepted": True, "recorded_verification": verdict.get("verification")}
    _log(log, "submit_investigation_verdict", {"root_causes": rcs}, None, terminal=True)
    return out


# --------------------------------------------------------------------------------
# logging + facade
# --------------------------------------------------------------------------------
def _log(log, tool, args, error, *, unsafe=False, terminal=False):
    if log is None:
        return
    log.append({"tool": tool, "args": _safe(args),
                "error": (error or {}).get("error"),
                "unsafe": unsafe, "terminal": terminal})


def _safe(args):
    try:
        json.dumps(args)
        return args
    except TypeError:
        return {k: str(v) for k, v in (args or {}).items()}


class Tools:
    """A per-investigation facade binding the tools to one world connection and one log.

    This is the exact surface both model arms would receive. It holds no answer key.
    """
    def __init__(self, con):
        self.con = con
        self.log: list = []

    def run_sql(self, tier, query, offset=0):
        return rs.run_sql(self.con, tier, query, offset=offset, log=self.log)

    def get_pipeline_metadata(self, pipeline_id):
        return get_pipeline_metadata(self.con, pipeline_id, log=self.log)

    def inspect_transformation_logic(self, view_name):
        return inspect_transformation_logic(self.con, view_name, log=self.log)

    def simulate_remediation(self, action_type, parameters=None):
        return simulate_remediation(self.con, action_type, parameters, log=self.log)

    def submit_investigation_verdict(self, verdict):
        return submit_investigation_verdict(verdict, log=self.log)

    # metrics the scorer will read (DESIGN.md 6.5)
    def stats(self) -> dict:
        calls = self.log
        sql_calls = [c for c in calls if c["tool"] == "run_sql"]
        norm = [(c.get("tier"), re.sub(r"\s+", " ", c.get("query", "")).strip().lower())
                for c in sql_calls]
        repeats = len(norm) - len(set(norm))
        return {
            "tool_calls": len(calls),
            "sql_calls": len(sql_calls),
            "repeated_sql_calls": repeats,
            "unsafe_attempts": sum(1 for c in calls if c.get("unsafe")),
            "errors": sum(1 for c in calls if c.get("error")),
        }
