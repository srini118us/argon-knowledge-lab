"""Phase 7 capability-probe tests. OFFLINE — zero API calls (uses the mock client).

Validates the mechanics the real Flash/Argon run depends on:
  * both arms receive the identical shared schema + system prompt
  * the multistep tool loop drives the five tools and reaches a verdict
  * verdict handling + usage/thinking-token accounting
  * timeout / incomplete / no-call handling
  * the runner exposes only the five controlled tools, no ground-truth access
  * the frozen Phase 6 benchmark is unchanged

Run:  python -m pytest experiments/finance-reconciliation/tests/test_probe.py -q
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pytest  # noqa: E402

from agent import loop, schemas  # noqa: E402
from agent.mock_client import MockClient  # noqa: E402
from agent.loop import run_investigation  # noqa: E402
from grade import scorer  # noqa: E402
from spec import freeze, testset, validate_testset  # noqa: E402
from tools.tools import Tools  # noqa: E402


def test_shared_schema_has_five_tools():
    assert set(schemas.TOOL_NAMES) == {
        "run_sql", "get_pipeline_metadata", "inspect_transformation_logic",
        "simulate_remediation", "submit_investigation_verdict"}


def test_schema_and_prompt_leak_no_ground_truth():
    blob = (str(schemas.FUNCTION_DECLARATIONS) + schemas.SYSTEM_PROMPT).lower()
    # ground-truth leak patterns: defect labels, planted keys, answer-key column names.
    # (The bare word "answer" in an instruction like "do not answer in prose" is fine;
    # we look for answer-KEY leaks, not the English word.)
    for forbidden in ["is_anomaly", "4910000", "cgone", "answer_key", "answerkey",
                      "injector", "planted", "ground_truth", "expected_discrepancy"]:
        assert forbidden not in blob


@pytest.mark.parametrize("case", testset.TEST_CASES, ids=[c["id"] for c in testset.TEST_CASES])
def test_loop_completes_and_scores(case):
    con, truth = testset.build_case(case)
    key = validate_testset._key_from_truth(case, truth)
    r = run_investigation(con, MockClient(con, mode="competent"))
    assert r["status"] == "completed" and r["verdict"] is not None
    g = scorer.grade(con, key, r["verdict"], log=r["log"], tool_stats=r["tool_stats"])
    assert g["score"] == 100.0   # a correct investigation scores full marks through the loop


def test_usage_accounting_accumulates_thinking():
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, MockClient(con, mode="competent"))
    assert r["usage"]["input_tokens"] > 0
    assert r["usage"]["output_tokens"] > 0
    assert r["usage"]["thinking_tokens"] > 0
    # totals equal per-turn usage times turns (competent mock uses a fixed per-turn profile)
    assert r["usage"]["thinking_tokens"] == 300 * r["turns"]


def test_timeout_is_handled():
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, MockClient(con, mode="timeout"))
    assert r["status"] == "timeout" and r["verdict"] is None


def test_incomplete_thinking_budget_is_handled():
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, MockClient(con, mode="incomplete"))
    assert r["status"] == "incomplete" and r["verdict"] is None
    assert r["usage"]["thinking_tokens"] > r["usage"]["output_tokens"]   # the tell


def test_no_call_stall_is_handled():
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, MockClient(con, mode="no_call"))
    assert r["status"] == "incomplete" and r["verdict"] is None


def test_loop_respects_max_turns():
    con, _ = testset.build_case(testset.TEST_CASES[0])
    # a client that never submits a verdict must stop at max_turns, not loop forever
    class Spinner:
        def create(self, messages, tools, system):
            return {"function_call": {"name": "run_sql",
                    "args": {"tier": "mart", "query": "SELECT 1"}},
                    "verdict": None, "usage": {"input_tokens": 10, "output_tokens": 10, "thinking_tokens": 0},
                    "status": "ok", "error": None}
    r = run_investigation(con, Spinner(), max_turns=6)
    assert r["turns"] == 6 and r["status"] == "incomplete"


def test_loop_references_no_ground_truth():
    src = inspect.getsource(loop)
    for forbidden in ["grade", "spec.key", "frozen_testset", "answer", "injector", "build_key"]:
        assert forbidden not in src


def test_tools_surface_is_exactly_five_plus_stats():
    con, _ = testset.build_case(testset.TEST_CASES[0])
    T = Tools(con)
    surface = {m for m in dir(T) if not m.startswith("_") and callable(getattr(T, m))}
    assert surface == {"run_sql", "get_pipeline_metadata", "inspect_transformation_logic",
                       "simulate_remediation", "submit_investigation_verdict", "stats"}


def test_frozen_benchmark_unchanged_by_phase7():
    ok, diffs = freeze.verify_frozen()
    assert ok, f"frozen benchmark changed: {diffs}"


def test_cost_estimate_is_conservative_and_bounded():
    from agent import cost_estimate as ce
    arms = ["gemini-3.8-flash", "gemini-4-argon"]
    pilot = ce.estimate(5, arms, "medium")
    full = ce.estimate(10, arms, "medium")
    # sanity: estimates are positive, Argon costs more than Flash, within a small budget
    assert pilot["per_case_usd"]["gemini-4-argon"] > pilot["per_case_usd"]["gemini-3.8-flash"]
    assert pilot["total_usd"] < 2.0 and full["total_usd"] < 3.0


def test_force_submit_converts_stubborn_model_to_completed():
    """A model that never volunteers a verdict (like the live Flash/Argon) must still complete,
    because the final turns offer only the submit tool. Validated offline, no API."""
    from agent.loop import run_investigation
    from agent.mock_client import MockClient
    from grade.key import build_key
    from grade import scorer
    for name in ["incident1_skipped_cdc", "incident5_compound"]:
        con, key = build_key(name)
        r = run_investigation(con, MockClient(con, mode="stubborn"), max_turns=8)
        assert r["status"] == "completed", f"{name}: {r['status']}"
        assert r["verdict"] is not None
        g = scorer.grade(con, key, r["verdict"], log=r["log"], tool_stats=r["tool_stats"])
        assert g["score"] > 0
