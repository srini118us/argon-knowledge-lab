"""Pricing math and the documented behavior of the run.py budget guardrail (offline)."""
import sys
import types
from datetime import date

import pytest

from argon_lab import pricing


def test_introductory_and_standard_rates():
    assert pricing.rates("gemini-4-argon", date(2026, 11, 30)) == (2.00, 10.00, 0.10)
    assert pricing.rates("gemini-4-argon", date(2026, 12, 1)) == (4.00, 20.00, 0.20)
    assert pricing.rates("gemini-3.8-flash", date(2027, 1, 1)) == (1.50, 7.50, 0.15)


def test_cost_counts_cached_input_at_cached_rate():
    u = {"total_input_tokens": 1_000_000, "total_cached_tokens": 500_000, "total_output_tokens": 0}
    assert pricing.cost_usd("gemini-4-argon", u, date(2026, 10, 14)) == pytest.approx(0.5 * 2.00 + 0.5 * 0.10)


def test_cost_counts_thought_tokens_as_output():
    u = {"total_input_tokens": 0, "total_output_tokens": 100_000, "total_thought_tokens": 100_000}
    assert pricing.cost_usd("gemini-4-argon", u, date(2026, 10, 14)) == pytest.approx(2.00)


def test_reproduces_logged_long_context_cost():
    """Argon long context, mean usage from the main run: ~45,556 input, ~95 output, ~73 thinking."""
    u = {"total_input_tokens": 45_556, "total_output_tokens": 95, "total_thought_tokens": 73}
    assert pricing.cost_usd("gemini-4-argon", u, date(2026, 10, 14)) == pytest.approx(0.0928, abs=0.001)


# ---------------------------------------------------------------- budget guardrail
@pytest.fixture
def run_module(tmp_path, monkeypatch):
    import run
    from argon_lab import arms
    monkeypatch.setattr(run, "OUT_DIR", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test")
    fake_genai = types.SimpleNamespace(Client=lambda: object())
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setattr(sys.modules.get("google", types.ModuleType("google")), "genai", fake_genai, raising=False)
    return run, arms


def fake_arm(cost_input_tokens):
    def _arm(client, model, level, question, docs):
        from argon_lab.arms import Run
        r = Run()
        r.usage["total_input_tokens"] = cost_input_tokens
        r.calls = 1
        return {"status": "answered", "answer": "x", "citations": []}, r
    return _arm


def run_batch(run, monkeypatch, budget):
    monkeypatch.setattr(sys, "argv", ["run.py", "--split", "dev", "--arms", "L", "--models", "gemini-4-argon",
                                      "--levels", "medium", "--budget", str(budget), "--yes"])
    return run.main()


def test_budget_stops_before_next_question_and_overshoots_by_at_most_one(run_module, monkeypatch, tmp_path):
    run, arms = run_module
    monkeypatch.setattr(arms, "long_context", fake_arm(50_000))     # $0.10 per question at $2 per 1M
    assert run_batch(run, monkeypatch, budget=0.15) == 2
    lines = next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    assert len(lines) == 2          # $0.10, then $0.20 > $0.15, stop before the third question
    # spend reached $0.20: over the cap by less than one question's cost


def test_failed_question_is_recorded_at_zero_cost(run_module, monkeypatch, tmp_path):
    run, arms = run_module

    def boom(*a, **k):
        raise RuntimeError("simulated API failure")
    monkeypatch.setattr(arms, "long_context", boom)
    assert run_batch(run, monkeypatch, budget=1) == 0
    import json
    rows = [json.loads(l) for l in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert len(rows) == 10 and all(r["error"] and r.get("cost_usd") is None for r in rows)
