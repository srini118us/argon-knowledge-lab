"""Offline tests for the real Gemini adapter and the spending guard. ZERO API calls.

A fake google.genai is injected into sys.modules so GeminiClient constructs and runs offline,
exercising ix.steps parsing, multi-turn continuity, usage accounting, and failure handling.
No real key is ever used; a placeholder is set only so the lazy client builds.

The spending-guard math (worst-case reservation, actual cost, cap stop) is tested directly.

Run:  python -m pytest experiments/finance-reconciliation/tests/test_live_adapter.py -q
"""
from __future__ import annotations

import sys
import types as T
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "src"))

import pytest  # noqa: E402

from spec import testset  # noqa: E402


# ---- fake SDK --------------------------------------------------------------------
class _Step:
    def __init__(self, name, arguments, id):
        self.type, self.name, self.arguments, self.id = "function_call", name, arguments, id


class _Usage:
    def __init__(self, **kw):
        for k in ["total_input_tokens", "total_output_tokens", "total_thought_tokens",
                  "total_cached_tokens", "total_tool_use_tokens", "total_tokens"]:
            setattr(self, k, kw.get(k, 0))


class _Ix:
    def __init__(self, steps=None, output_text="", usage=None, id="ix"):
        self.steps, self.output_text, self.usage, self.id = steps or [], output_text, usage, id


class _Interactions:
    def __init__(self, scripted): self._s, self._i = scripted, 0
    def create(self, **kw):
        r = self._s[min(self._i, len(self._s) - 1)]
        self._i += 1
        if isinstance(r, Exception):
            raise r
        return r


def _install_fake(scripted):
    genai = T.ModuleType("google.genai")
    gtypes = T.ModuleType("google.genai.types")
    gtypes.HttpOptions = lambda **k: None
    gtypes.HttpRetryOptions = lambda **k: None

    class _Client:
        def __init__(self, **kw): self.interactions = _Interactions(scripted)
    genai.Client = _Client
    genai.types = gtypes
    google = T.ModuleType("google")
    google.genai = genai
    sys.modules["google"] = google
    sys.modules["google.genai"] = genai
    sys.modules["google.genai.types"] = gtypes


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "FAKE_OFFLINE_ONLY")
    # clear any cached fake modules between tests
    for m in ("google", "google.genai", "google.genai.types"):
        sys.modules.pop(m, None)
    yield


def _u():
    return _Usage(total_input_tokens=1500, total_output_tokens=100, total_thought_tokens=300,
                 total_tokens=1900)


# ---- adapter mechanics -----------------------------------------------------------
def test_adapter_completes_multiturn_and_parses_steps():
    _install_fake([
        _Ix(steps=[_Step("run_sql", {"tier": "mart", "query": "SELECT belnr FROM dbx_ar_mart"}, "c1")], usage=_u(), id="ix1"),
        _Ix(steps=[_Step("submit_investigation_verdict",
            {"root_causes": [{"incident_class": "duplicate_replay", "layer": "L4"}],
             "affected_business_keys": [], "proposed_remediations": [{"action_type": "dedupe_target"}],
             "verification": {"discrepancy_after": 0.0, "invariants_ok": True}}, "c2")], usage=_u(), id="ix2"),
    ])
    from agent.gemini_client import GeminiClient
    from agent.loop import run_investigation
    con, _ = testset.build_case(testset.TEST_CASES[2])
    r = run_investigation(con, GeminiClient("gemini-3.8-flash", "medium"))
    assert r["status"] == "completed" and r["verdict"] is not None
    assert r["turns"] == 2
    assert r["usage"]["input_tokens"] == 3000   # accumulated across 2 turns
    assert any(c["tool"] == "run_sql" for c in r["log"])


def test_adapter_never_exposes_key():
    _install_fake([_Ix(steps=[_Step("run_sql", {"tier": "mart", "query": "SELECT 1"}, "c1")], usage=_u())])
    from agent.gemini_client import GeminiClient
    from agent.loop import run_investigation
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, GeminiClient("gemini-4-argon", "medium"), max_turns=2)
    assert "FAKE_OFFLINE_ONLY" not in str(r)


def test_adapter_handles_incomplete_thinking_budget():
    _install_fake([_Ix(steps=[], output_text="",
                      usage=_Usage(total_input_tokens=1500, total_output_tokens=2,
                                   total_thought_tokens=7000, total_tokens=8502))])
    from agent.gemini_client import GeminiClient
    from agent.loop import run_investigation
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, GeminiClient("gemini-4-argon", "medium"), max_turns=2)
    assert r["status"] == "incomplete"


def test_adapter_handles_api_error():
    _install_fake([RuntimeError("503 Service Unavailable")])
    from agent.gemini_client import GeminiClient
    from agent.loop import run_investigation
    con, _ = testset.build_case(testset.TEST_CASES[0])
    r = run_investigation(con, GeminiClient("gemini-3.8-flash", "medium"), max_turns=2)
    assert r["status"] == "error"


def test_adapter_raises_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _install_fake([_Ix()])
    from agent.gemini_client import GeminiClient
    c = GeminiClient("gemini-3.8-flash", "medium")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        c.create(messages=[{"role": "user", "content": "x"}], tools=[], system="s")


# ---- spending guard math ---------------------------------------------------------
def test_worst_case_is_bounded_and_ordered():
    from agent import run_live
    f = run_live.case_worst_case("gemini-3.8-flash")
    a = run_live.case_worst_case("gemini-4-argon")
    assert 0 < f < a            # Argon costs more
    assert a < 2.0              # one case worst-case is bounded (8k in + 8k out, 15 turns)


def test_actual_cost_uses_thinking_as_output():
    from agent import run_live
    usage = {"input_tokens": 10_000, "output_tokens": 500, "thinking_tokens": 2_000, "cached_tokens": 0}
    cost = run_live.actual_cost("gemini-4-argon", usage)
    # (10000*2 + 2500*10)/1e6 = 0.045
    assert abs(cost - 0.045) < 1e-6


def test_tool_schema_matches_five_tools():
    from agent import schemas
    assert [t["name"] for t in schemas.GEMINI_TOOLS] == schemas.TOOL_NAMES
    assert all(t["type"] == "function" for t in schemas.GEMINI_TOOLS)
    assert len(schemas.GEMINI_TOOLS) == 5


def test_preflight_is_offline_and_frozen_hash_checked(capsys):
    from agent import run_live
    run_live.preflight("test", 3.0)
    out = capsys.readouterr().out
    assert "frozen benchmark hash: OK" in out
    assert "allowance: $10.00" in out
