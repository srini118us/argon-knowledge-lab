"""Offline tests for the Experiment 2 harness: hard deadline, interrupted calls, budget accounting,
and the separation of completion failures from wrong decisions. No API calls."""
import json
import sys
import threading
import time
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
for p in (HERE, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import arb  # noqa: E402
import run_arb  # noqa: E402
import score_arb  # noqa: E402

TEST_RUN = HERE / "results" / "runs" / "test_20261016_152247.jsonl"
CORRECT = {c: arb.load_key()[c] for c in arb.load_key()}


def answer_for(case_id):
    k = CORRECT[case_id]
    return {"decision": k["decision"], "violations": k["violations"], "conditions": k["conditions"],
            "citations": k["required_citations"], "rationale": ""}


class Fake:
    """Scripted interactions client. mode: ok | slow | disconnect | exhausted | badjson | wrong"""

    def __init__(self, mode="ok", sleep_s=0.0, out_tokens=800, thought=1500):
        self.mode, self.sleep_s, self.out_tokens, self.thought = mode, sleep_s, out_tokens, thought
        self.calls = 0
        self.case = None

    def create(self, **kw):
        self.calls += 1
        text_items = [p["text"] for p in kw["input"]]
        cid = text_items[-1].split(":")[0].replace("Proposal ", "").strip()
        if self.mode == "slow":
            time.sleep(self.sleep_s)
        if self.mode == "disconnect":
            raise ConnectionError("Server disconnected without sending a response.")
        out, thought, text = self.out_tokens, self.thought, json.dumps(answer_for(cid))
        if self.mode == "exhausted":
            out, thought, text = 3, run_arb.MAX_OUTPUT_TOKENS - 3, ""
        elif self.mode == "badjson":
            text = "decision: approve"
        elif self.mode == "wrong":
            a = answer_for(cid)
            a["decision"] = "approve" if a["decision"] != "approve" else "reject"
            text = json.dumps(a)
        u = types.SimpleNamespace(total_input_tokens=5200, total_output_tokens=out, total_thought_tokens=thought,
                                  total_cached_tokens=0, total_tool_use_tokens=0, total_tokens=5200 + out + thought)
        return types.SimpleNamespace(id=f"ix{self.calls}", usage=u, output_text=text)


def client(**kw):
    return types.SimpleNamespace(interactions=Fake(**kw))


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(run_arb, "RESULTS", tmp_path)
    monkeypatch.setattr(run_arb, "LEDGER", tmp_path / "ledger.jsonl")
    return tmp_path


def rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------- hard deadline
def test_call_with_deadline_returns_fast_results():
    assert run_arb.call_with_deadline(lambda: 42, 1.0) == 42


def test_call_with_deadline_stops_waiting_on_a_hung_call():
    t0 = time.time()
    with pytest.raises(run_arb.DeadlineExceeded):
        run_arb.call_with_deadline(lambda: time.sleep(5), 0.2)
    assert time.time() - t0 < 1.5


def test_call_with_deadline_reraises_the_call_error():
    def boom():
        raise ConnectionError("dropped")
    with pytest.raises(ConnectionError):
        run_arb.call_with_deadline(boom, 1.0)


def test_abandoned_call_thread_does_not_block_exit():
    before = threading.active_count()
    with pytest.raises(run_arb.DeadlineExceeded):
        run_arb.call_with_deadline(lambda: time.sleep(2), 0.05)
    hung = [t for t in threading.enumerate() if t.is_alive() and t is not threading.main_thread()]
    assert all(t.daemon for t in hung) and threading.active_count() >= before


def test_runner_times_out_records_status_and_continues(iso):
    cases = arb.load_cases("dev")
    stats = run_arb.run(client(mode="slow", sleep_s=3), cases, [("gemini-3.8-flash", "medium")], 1, cap=5,
                        out_path=iso / "t.jsonl", log=lambda *_: None, deadline_s=0.2)
    out = rows(iso / "t.jsonl")
    assert len(out) == 3 and stats["calls"] == 3
    assert all(r["status"] == "timeout" and r["latency_s"] < 1.5 for r in out)
    assert stats["status"] == {"timeout": 3}


# ---------------------------------------------------------------- interrupted and incomplete calls
def test_disconnect_is_a_connection_error_not_a_wrong_decision(iso):
    cases = arb.load_cases("dev")[:1]
    run_arb.run(client(mode="disconnect"), cases, [("gemini-3.8-flash", "high")], 1, cap=5,
                out_path=iso / "d.jsonl", log=lambda *_: None)
    r = rows(iso / "d.jsonl")[0]
    assert r["status"] == "connection_error" and r["answer"] is None


def test_budget_exhaustion_is_detected(iso):
    cases = arb.load_cases("dev")[:1]
    run_arb.run(client(mode="exhausted"), cases, [("gemini-4-argon", "high")], 1, cap=5,
                out_path=iso / "e.jsonl", log=lambda *_: None)
    r = rows(iso / "e.jsonl")[0]
    assert r["status"] == "budget_exhausted" and r["cost_usd"] > 0


def test_unparseable_text_is_a_parse_error(iso):
    cases = arb.load_cases("dev")[:1]
    run_arb.run(client(mode="badjson"), cases, [("gemini-3.8-flash", "medium")], 1, cap=5,
                out_path=iso / "p.jsonl", log=lambda *_: None)
    assert rows(iso / "p.jsonl")[0]["status"] == "parse_error"


def test_status_of_rows_written_before_the_status_field():
    assert arb.completion_status({"error": "APIConnectionError('Server disconnected without sending a response.')"}) == "connection_error"
    assert arb.completion_status({"error": "RateLimitError('Error code: 429 ...')"}) == "api_error"
    assert arb.completion_status({"error": "DeadlineExceeded('no response within 600 s')"}) == "timeout"
    assert arb.completion_status({"answer": None, "usage": {"total_output_tokens": 3, "total_thought_tokens": 31997}}) == "budget_exhausted"
    assert arb.completion_status({"answer": {"decision": "approve"}}) == "completed"


# ---------------------------------------------------------------- budget accounting
def test_ledger_separates_measured_cost_from_worst_case_reservations(iso):
    dev = arb.load_cases("dev")
    run_arb.run(client(), dev[:2], [("gemini-3.8-flash", "medium")], 1, cap=5, out_path=iso / "a.jsonl",
                log=lambda *_: None)
    run_arb.run(client(mode="disconnect"), dev[2:], [("gemini-3.8-flash", "medium")], 1, cap=5,
                out_path=iso / "b.jsonl", log=lambda *_: None)
    led = rows(iso / "ledger.jsonl")
    measured = [l for l in led if l["basis"] == "measured"]
    reserved = [l for l in led if l["basis"] == "worst_case_reservation"]
    assert len(measured) == 2 and len(reserved) == 1
    assert reserved[0]["charged_usd"] == pytest.approx(reserved[0]["worst_case_usd"])
    assert run_arb.ledger_spent() == pytest.approx(sum(l["charged_usd"] for l in led))


def test_timeouts_count_toward_the_cap(iso):
    dev = arb.load_cases("dev")
    worst = run_arb.worst_case_usd("gemini-4-argon", dev[0])
    stats = run_arb.run(client(mode="slow", sleep_s=2), dev, [("gemini-4-argon", "high")], 1,
                        cap=worst * 1.5, out_path=iso / "c.jsonl", log=lambda *_: None, deadline_s=0.1)
    assert stats["calls"] == 1 and stats["stopped"].startswith("cap")


# ---------------------------------------------------------------- scoring separation
def test_scoring_separates_incomplete_from_incorrect(iso):
    dev = arb.load_cases("dev")
    arm = [("gemini-3.8-flash", "medium")]
    run_arb.run(client(), dev[:1], arm, 1, cap=5, out_path=iso / "s.jsonl", log=lambda *_: None)
    run_arb.run(client(mode="wrong"), dev[1:2], arm, 1, cap=5, out_path=iso / "s.jsonl", log=lambda *_: None)
    run_arb.run(client(mode="disconnect"), dev[2:], arm, 1, cap=5, out_path=iso / "s.jsonl", log=lambda *_: None)
    s = score_arb.summarize(rows(iso / "s.jsonl"))[0]
    assert s["fully_correct"] == 1 and s["completed"] == 2
    assert s["fully_correct_on_completed"] == "1/2"
    assert s["incorrect_completed_cases"] == ["DEV2"] and s["incomplete_cases"] == {"DEV3": "connection_error"}


# ---------------------------------------------------------------- frozen results reproduce
@pytest.mark.skipif(not TEST_RUN.exists(), reason="test run file not present")
def test_published_experiment2_results_reproduce():
    rs = [r for r in rows(TEST_RUN) if r.get("type") == "row"]
    got = {(s["model"], s["level"]): s for s in score_arb.summarize(rs)}
    expect = {("gemini-3.8-flash", "medium"): (12, 12, {}), ("gemini-4-argon", "medium"): (12, 12, {}),
              ("gemini-4-argon", "high"): (11, 11, {"T12": "budget_exhausted"}),
              ("gemini-3.8-flash", "high"): (10, 10, {"T05": "connection_error", "T12": "connection_error"})}
    for arm, (full, done, incomplete) in expect.items():
        s = got[arm]
        assert (s["fully_correct"], s["completed"], s["incomplete_cases"]) == (full, done, incomplete), arm
        assert s["incorrect_completed_cases"] == []


@pytest.mark.skipif(not TEST_RUN.exists(), reason="test run file not present")
def test_report_tables_match_scoring_output():
    """REPORT.md must quote the scoring output exactly (rounded as printed)."""
    report = (HERE / "REPORT.md").read_text(encoding="utf-8").splitlines()
    rs = [r for r in rows(TEST_RUN) if r.get("type") == "row"]
    names = {("gemini-3.8-flash", "medium"): "Flash, medium", ("gemini-4-argon", "medium"): "Argon, medium",
             ("gemini-4-argon", "high"): "Argon, high", ("gemini-3.8-flash", "high"): "Flash, high"}
    for s in score_arb.summarize(rs):
        name = names[(s["model"], s["level"])]
        cost_row = next(l for l in report if l.startswith(f"| {name} | $"))
        exact = sum(r["cost_usd"] or 0 for r in rs if (r["model"], r["level"]) == (s["model"], s["level"]))
        for v in (f"${exact:.3f}", f"{s['median_latency_s']:.1f} s", f"{s['mean_output_plus_thinking']:,}",
                  f"{round(100 * s['completed'] / s['n'])}%"):
            assert v in cost_row, (name, v, cost_row)
        result_row = next(l for l in report if l.startswith(f"| {name} | ") and "/12" in l)
        assert f"| {s['completed']}/12 | {s['fully_correct']}/{s['completed']} | {s['fully_correct']}/12 |" in result_row
