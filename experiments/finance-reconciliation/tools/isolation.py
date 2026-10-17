"""Hidden-key isolation guard for the agent process (DESIGN.md 6.1.1 item 1).

The agent process may import sim/, tools/ and (later) agent/ only. It must NOT be able to
import the grader or the answer key. assert_agent_isolation() is called at the agent
entrypoint; it aborts if grade/ or spec.key is reachable, and it confirms the world
database the agent is handed carries no defect-label columns.
"""
from __future__ import annotations

import importlib.util

# Columns/relations that would leak the answer if present in the agent-visible DB.
FORBIDDEN_COLUMN_PATTERNS = ("is_anomaly", "defect", "planted", "expected_", "bug",
                             "answer", "root_cause", "injected")


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def assert_no_key_modules() -> None:
    """The agent entrypoint must not be able to import the grader or the key."""
    leaks = [m for m in ("grade", "grade.engine", "spec.key") if _module_importable(m)]
    if leaks:
        raise RuntimeError(f"isolation breach: agent process can import {leaks}")


def assert_no_label_columns(con) -> None:
    """The agent-visible world must carry no defect-label columns or tables."""
    rows = con.execute(
        "SELECT table_name, column_name FROM information_schema.columns"
    ).fetchall()
    bad = []
    for table, col in rows:
        lc = col.lower()
        if any(p in lc for p in FORBIDDEN_COLUMN_PATTERNS):
            bad.append(f"{table}.{col}")
    tnames = [r[0].lower() for r in con.execute(
        "SELECT table_name FROM information_schema.tables").fetchall()]
    for t in tnames:
        if any(p in t for p in FORBIDDEN_COLUMN_PATTERNS):
            bad.append(f"table {t}")
    if bad:
        raise RuntimeError(f"isolation breach: answer-label columns/tables present: {bad}")


def assert_agent_isolation(con) -> None:
    assert_no_key_modules()
    assert_no_label_columns(con)
