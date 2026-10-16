"""Offline tests for Experiment 2. No test makes an API call."""
import json
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
for p in (HERE, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import arb  # noqa: E402
import check_cases  # noqa: E402
import engine  # noqa: E402
import run_arb  # noqa: E402
import score_arb  # noqa: E402


# ---------------------------------------------------------------- key and cases
def test_frozen_key_matches_engine():
    key = arb.load_key()
    for c in arb.load_cases():
        r = engine.evaluate(c)
        assert (key[c["id"]]["decision"], key[c["id"]]["violations"], key[c["id"]]["conditions"]) == \
               (r["decision"], r["violations"], r["conditions"]), c["id"]


def test_pack_states_every_rule_waiver_and_number():
    assert check_cases.check_pack(engine.load_policy()) == []


def test_every_case_needs_multiple_steps_and_renders_all_facts():
    for c in arb.load_cases():
        _, _, _, problems = check_cases.check_case(c)
        assert problems == [], problems


def test_test_split_mixes_decisions():
    decisions = {engine.evaluate(c)["decision"] for c in arb.load_cases("test")}
    assert decisions == {"approve", "approve_with_conditions", "reject"}


def test_specific_reasoning_chains():
    by_id = {c["id"]: c for c in arb.load_cases()}
    # Waiver covers the global rule but not the stricter EU annex: still reject.
    assert engine.evaluate(by_id["T09"])["violations"] == ["AX-EU-1"]
    # Waiver expired one day before go live window: no cover.
    assert engine.evaluate(by_id["T11"])["decision"] == "reject"
    # Last freeze day is inclusive; the day after is clear.
    assert "CF-1" in engine.evaluate(by_id["T10"])["conditions"]
    assert engine.evaluate(by_id["T01"])["decision"] == "approve"
    # The superseded policy would have approved T11 (TLS allowed for C2 under v2).
    assert engine.evaluate(by_id["T11"], mutation="superseded")["decision"] == "approve"


def test_models_never_see_structured_fields():
    text = json.dumps(arb.prompt(arb.load_cases("test")[0]))
    for leak in ('"data_subjects"', '"encrypted_at_rest"', '"via_gateway"', "key.json", '"retention_days"'):
        assert leak not in text


# ---------------------------------------------------------------- scoring
def _key(cid):
    return arb.load_key()[cid]


def test_fully_correct_and_evidence_valid():
    k = _key("T09")
    ans = {"decision": "reject", "violations": ["AX-EU@v1#AX-EU-1"], "conditions": [],
           "citations": ["AX-EU@v1#AX-EU-1"], "rationale": ""}
    s = score_arb.score_one(k, ans, check_cases.pack_docs())
    assert s["fully_correct"] and s["evidence_valid"] and s["unknown_citations"] == 0


def test_right_decision_wrong_violation_set_is_not_fully_correct():
    k = _key("T09")
    ans = {"decision": "reject", "violations": ["SP-4.1", "AX-EU-1"], "conditions": [], "citations": []}
    s = score_arb.score_one(k, ans, check_cases.pack_docs())
    assert s["decision_correct"] and not s["fully_correct"] and s["viol_fp"] == 1


def test_superseded_reliance_and_unknown_citations():
    k = _key("T11")
    ans = {"decision": "approve", "violations": [], "conditions": [],
           "citations": ["SEC-POL@v2#SP-3.1", "SEC-POL@v3#SP-9.9", "MADE-UP@v1"]}
    s = score_arb.score_one(k, ans, check_cases.pack_docs())
    assert s["superseded_reliance"] and s["unknown_citations"] == 2 and not s["decision_correct"]


def test_unparsed_answer_scores_zero():
    s = score_arb.score_one(_key("T03"), None, check_cases.pack_docs())
    assert not s["parsed"] and s["viol_fn"] == 3


# ---------------------------------------------------------------- spending guard
class FakeInteractions:
    def __init__(self, out_tokens=1000, fail=False):
        self.out_tokens, self.fail, self.calls = out_tokens, fail, 0

    def create(self, **kw):
        self.calls += 1
        assert kw["generation_config"]["max_output_tokens"] == run_arb.MAX_OUTPUT_TOKENS
        if self.fail:
            raise RuntimeError("simulated failure")
        u = types.SimpleNamespace(total_input_tokens=5000, total_output_tokens=self.out_tokens,
                                  total_thought_tokens=0, total_cached_tokens=0, total_tool_use_tokens=0,
                                  total_tokens=5000 + self.out_tokens)
        return types.SimpleNamespace(id=f"ix{self.calls}", usage=u, output_text=json.dumps(
            {"decision": "approve", "violations": [], "conditions": [], "citations": [], "rationale": ""}))


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(run_arb, "RESULTS", tmp_path)
    monkeypatch.setattr(run_arb, "LEDGER", tmp_path / "ledger.jsonl")
    return tmp_path


def test_guard_stops_before_a_call_that_could_exceed_the_cap(isolated):
    cases = arb.load_cases("test")
    arm = [("gemini-4-argon", "high")]
    worst = run_arb.worst_case_usd("gemini-4-argon", cases[0])
    fake = types.SimpleNamespace(interactions=FakeInteractions(out_tokens=15_000))
    stats = run_arb.run(fake, cases, arm, 1, cap=worst * 2.5, out_path=isolated / "r.jsonl", log=lambda *_: None)
    assert stats["stopped"] and run_arb.ledger_spent() <= worst * 2.5
    assert fake.interactions.calls >= 2


def test_ledger_persists_across_runs_and_counts_toward_cap(isolated):
    cases = arb.load_cases("dev")
    fake = types.SimpleNamespace(interactions=FakeInteractions())
    run_arb.run(fake, cases, [("gemini-3.8-flash", "medium")], 1, cap=5, out_path=isolated / "a.jsonl",
                log=lambda *_: None)
    first = run_arb.ledger_spent()
    stats = run_arb.run(fake, cases, [("gemini-3.8-flash", "medium")], 1, cap=first + 0.0001,
                        out_path=isolated / "b.jsonl", log=lambda *_: None)
    assert first > 0 and stats["calls"] == 0 and stats["stopped"]


def test_failed_call_is_charged_at_worst_case_not_zero(isolated):
    cases = arb.load_cases("dev")[:1]
    fake = types.SimpleNamespace(interactions=FakeInteractions(fail=True))
    run_arb.run(fake, cases, [("gemini-4-argon", "medium")], 1, cap=5, out_path=isolated / "f.jsonl",
                log=lambda *_: None)
    row = json.loads((isolated / "ledger.jsonl").read_text().splitlines()[0])
    assert row["error"] and row["charged_usd"] == pytest.approx(row["worst_case_usd"])


def test_stops_if_output_cap_not_honoured(isolated):
    cases = arb.load_cases("dev")
    fake = types.SimpleNamespace(interactions=FakeInteractions(out_tokens=run_arb.MAX_OUTPUT_TOKENS * 3))
    stats = run_arb.run(fake, cases, [("gemini-4-argon", "high")], 1, cap=5, out_path=isolated / "o.jsonl",
                        log=lambda *_: None)
    assert stats["calls"] == 1 and "not honoured" in stats["stopped"]


def test_cap_stop_leaves_every_arm_on_the_same_cases(isolated):
    cases = arb.load_cases("test")
    fake = types.SimpleNamespace(interactions=FakeInteractions(out_tokens=8_000))
    out = isolated / "c.jsonl"
    run_arb.run(fake, cases, run_arb.ARMS, 1, cap=0.5, out_path=out, log=lambda *_: None)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    per_arm = {}
    for r in rows:
        per_arm.setdefault((r["model"], r["level"]), []).append(r["case"])
    done = sorted(per_arm.values(), key=len)
    assert len(done[-1]) - len(done[0]) <= 1          # arms differ by at most the case in progress


def test_estimate_includes_input_margin():
    c = arb.load_cases("dev")[0]
    raw = (len(arb.SYSTEM) + sum(len(p["text"]) for p in arb.prompt(c))) // 4 + 50
    assert run_arb.input_tokens_estimate(c) == int(raw * run_arb.INPUT_MARGIN) > raw
