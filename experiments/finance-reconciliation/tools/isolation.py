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


FORBIDDEN_MODULE_DIRS = ("grade", "spec")   # directories the agent path must not include


def assert_key_dirs_off_path(search_path: list[str]) -> None:
    """The agent entrypoint passes its OWN module search path (its sys.path). This asserts
    that path contains no directory exposing grade/ or spec/.

    In the real harness the agent process is launched with only the experiment's sim/, tools/
    and agent/ reachable; grade/ and spec/ are deliberately NOT on its path. We check the
    configured path rather than the global import system, because in a monorepo checkout every
    sibling package is importable from a shared root -- which is exactly the condition the
    launcher must avoid, and which this check detects.
    """
    import os
    bad = []
    for entry in search_path:
        for d in FORBIDDEN_MODULE_DIRS:
            if os.path.isdir(os.path.join(entry, d)) and \
               os.path.exists(os.path.join(entry, d, "__init__.py")):
                bad.append(os.path.join(entry, d))
    if bad:
        raise RuntimeError(
            f"isolation breach: agent search path exposes the grader/key: {bad}. "
            f"Launch the agent with only sim/, tools/, agent/ on its path.")


# NOTE (honest limitation): in this monorepo checkout grade/ and spec/ sit beside sim/ and
# tools/ under the experiment root, so any path that reaches sim/ also reaches grade/. The
# correct deployment is process-level isolation: launch the agent in a working directory that
# contains ONLY sim/ and tools/ (copied or an allowlisted path), with grade/ and spec/ absent.
# assert_key_dirs_off_path() checks exactly that property for whatever path it is given; it is
# the launcher's responsibility to pass an isolated path. The guard verifies the invariant; it
# cannot create isolation that the launcher did not set up.


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


def assert_agent_isolation(con, search_path: list[str]) -> None:
    """Called at the agent entrypoint with the agent's own sys.path. Verifies the path does
    not expose grade/ or spec/, and the world carries no answer labels."""
    assert_key_dirs_off_path(search_path)
    assert_no_label_columns(con)
