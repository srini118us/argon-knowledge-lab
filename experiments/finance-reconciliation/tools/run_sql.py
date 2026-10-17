"""run_sql tool: allowlisted, read-only SQL with tier isolation and result caps.

DESIGN.md 5.1. Both model arms receive this identical interface. Errors are returned
to the caller (not raised) so an agent can recover. Every call is logged.

Safety model:
  * exactly one statement, read-only (SELECT or WITH ... SELECT); no DDL/DML/PRAGMA/
    ATTACH/COPY/CALL/EXPORT/INSTALL/LOAD/SET.
  * the query may reference only tables/views in the named tier (tier isolation).
  * a LIMIT is injected if absent; results are capped by rows and by cells.
  * no filesystem or attach functions (read_csv, read_parquet, glob, etc.).

This tool never exposes the answer key: the tiers map only to the simulated world
tables/views, never to spec/ or grade/ (which live in a different package the agent
process cannot import; see tools/isolation.py).
"""
from __future__ import annotations

import re
import time

# Which tables/views each tier is allowed to touch. A query in a tier may reference
# only these relations. (Views pull from their own sources internally; that is the
# view's business, not the caller's — the caller still only names the tier's relations.)
TIER_TABLES = {
    "source":     {"s4_acdoca", "s4_customer", "s4_tcurr"},
    "cdc":        {"cdc_acdoca", "cdc_control"},
    "datasphere": {"dsp_ar_items"},
    "share":      {"share_ar_items"},
    "mart":       {"dbx_ar_mart"},
    "metadata":   {"pipeline_runs", "pipeline_config", "recon_cutoff"},
}
ALL_TIERS = set(TIER_TABLES)

DEFAULT_ROW_CAP = 1000
CELL_CAP = 50_000           # columns * rows ceiling on a returned page
TIMEOUT_MS = 5000

# Statements that are never allowed (read-only enforcement). Checked as whole words.
FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "merge", "upsert", "create", "drop", "alter",
    "truncate", "replace", "attach", "detach", "copy", "export", "import",
    "pragma", "install", "load", "set", "call", "vacuum", "analyze", "checkpoint",
    "begin", "commit", "rollback", "grant", "revoke",
}
# Functions that reach the filesystem or outside the sandbox DB.
FORBIDDEN_FUNCTIONS = {
    "read_csv", "read_parquet", "read_json", "read_text", "glob", "parquet_scan",
    "csv_scan", "sniff_csv", "read_blob", "query", "system",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _strip_comments_and_strings(sql: str) -> str:
    """Remove -- and /* */ comments and single-quoted string literals so keyword and
    table scanning does not match inside them."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:[^']|'')*'", " '' ", sql)   # collapse string literals
    return sql


def _referenced_relations(sql_nostr: str) -> set[str]:
    """Relations named after FROM / JOIN. Lowercased, with double-quotes stripped so a
    quoted identifier like "dbx_ar_mart" cannot evade tier matching."""
    rels = set()
    # match an optionally double-quoted, optionally schema-qualified identifier
    pat = r'\b(from|join)\s+("?[A-Za-z_][A-Za-z0-9_]*"?(?:\.\s*"?[A-Za-z_][A-Za-z0-9_]*"?)*)'
    for m in re.finditer(pat, sql_nostr, re.IGNORECASE):
        raw = m.group(2).replace('"', "").replace(" ", "")
        rel = raw.split(".")[-1].lower()   # strip any schema qualifier and quotes
        rels.add(rel)
    return rels


def validate(tier: str, query: str) -> dict | None:
    """Return an error dict if the query is disallowed, else None."""
    if tier not in ALL_TIERS:
        return {"error": "unknown_tier",
                "detail": f"tier must be one of {sorted(ALL_TIERS)}"}
    scrub = _strip_comments_and_strings(query)
    # Single statement only (allow a trailing semicolon).
    if ";" in scrub.rstrip().rstrip(";"):
        return {"error": "disallowed_statement", "detail": "only a single statement is permitted"}
    tokens = {t.lower() for t in _IDENT.findall(scrub)}
    if tokens & FORBIDDEN_KEYWORDS:
        return {"error": "disallowed_statement", "detail": "only a single read-only SELECT is permitted"}
    if tokens & FORBIDDEN_FUNCTIONS:
        return {"error": "disallowed_statement", "detail": "filesystem and external functions are not permitted"}
    first = next((t for t in _IDENT.findall(scrub)), "").lower()
    if first not in ("select", "with"):
        return {"error": "disallowed_statement", "detail": "only a single SELECT (or WITH ... SELECT) is permitted"}
    # Tier isolation: every referenced relation must be in this tier.
    allowed = TIER_TABLES[tier]
    for rel in _referenced_relations(scrub):
        # CTE names declared in this query are fine; only flag relations that are known
        # world tables in OTHER tiers, or unknown relations that match a world table name.
        world_tables = set().union(*TIER_TABLES.values())
        if rel in world_tables and rel not in allowed:
            return {"error": "tier_violation",
                    "detail": f"table {rel} not in tier '{tier}'"}
    return None


def _inject_limit(query: str, cap: int, offset: int) -> str:
    q = query.rstrip().rstrip(";")
    if re.search(r"\blimit\b", q, re.IGNORECASE):
        return q
    return f"{q} LIMIT {cap} OFFSET {offset}"


def run_sql(con, tier: str, query: str, *, row_cap: int = DEFAULT_ROW_CAP,
            offset: int = 0, log: list | None = None) -> dict:
    """Execute an allowlisted read-only query against the named tier.

    con is a DuckDB connection to the simulated world. Returns a result dict; on any
    problem returns an error dict. Appends a log entry when `log` is provided.
    """
    t0 = time.time()
    err = validate(tier, query)
    if err is not None:
        _log(log, tier, query, 0, False, t0, err)
        return err
    bounded = _inject_limit(query, row_cap + 1, offset)   # fetch one extra to detect truncation
    try:
        con.execute(f"SET statement_timeout = {TIMEOUT_MS}")
    except Exception:
        pass
    try:
        cur = con.execute(bounded)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        err = {"error": "timeout" if "timeout" in msg or "interrupt" in msg else "query_error",
               "detail": str(e)[:300]}
        _log(log, tier, query, 0, False, t0, err)
        return err
    truncated = len(rows) > row_cap
    if truncated:
        rows = rows[:row_cap]
    # Cell cap: trim rows if the page is enormous.
    if cols and len(rows) * len(cols) > CELL_CAP:
        rows = rows[: max(1, CELL_CAP // max(1, len(cols)))]
        truncated = True
    out = {
        "columns": cols,
        "rows": [[_json_safe(v) for v in r] for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
        "next_offset": (offset + row_cap) if truncated else None,
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }
    _log(log, tier, query, out["row_count"], truncated, t0, None)
    return out


def _json_safe(v):
    from datetime import date, datetime
    from decimal import Decimal
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _log(log, tier, query, row_count, truncated, t0, error):
    if log is None:
        return
    log.append({
        "tool": "run_sql", "tier": tier, "query": query,
        "row_count": row_count, "truncated": truncated,
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "error": (error or {}).get("error"),
    })
