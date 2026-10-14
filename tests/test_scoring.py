import json
from collections import Counter
from pathlib import Path

import pytest

from argon_lab.scoring import apply_review, norm_cite, score_one

ROOT = Path(__file__).resolve().parents[1]
KEY = {q["id"]: q for q in json.loads((ROOT / "corpus/spec/questions.json").read_text())["questions"]}
MAIN_RUN = ROOT / "results/runs/test_20261013_235517.jsonl"


def row(qid, status="answered", answer="", cites=(), arm="R2", retrieved=()):
    return {"qid": qid, "arm": arm, "model": "m", "retrieved": list(retrieved),
            "answer": {"status": status, "answer": answer, "citations": list(cites)}}


def test_correct_answer_with_required_citation_is_evidence_valid():
    s = score_one(KEY["C01"], row("C01", answer="Apache Kafka", cites=["ADR-019@v1"]))
    assert s["correct"] and s["evidence_valid"] and s["superseded_use"] is None


def test_correct_answer_missing_required_citation_is_not_evidence_valid():
    s = score_one(KEY["X01"], row("X01", answer="100 now; contract allows 120", cites=["ADR-024@v1"]))
    assert s["correct"] and not s["evidence_valid"]


def test_superseded_historical_vs_outdated_authority():
    hist = score_one(KEY["C03"], row("C03", answer="120", cites=["CT-SWIFT-2024@A1", "CT-SWIFT-2024@v1"]))
    old = score_one(KEY["C03"], row("C03", answer="120", cites=["CT-SWIFT-2024@v1"]))
    assert hist["superseded_use"] == "historical" and hist["evidence_valid"]
    assert old["superseded_use"] == "outdated_authority" and not old["evidence_valid"]


def test_unanswerable_abstention_and_hallucination():
    ok = score_one(KEY["U03"], row("U03", status="not_found"))
    bad = score_one(KEY["U03"], row("U03", answer="3 brokers", cites=["ADR-019@v1"]))
    assert ok["correct"] and ok["evidence_valid"] and not ok["answerable"]
    assert not bad["correct"] and bad["hallucinated"]


def test_false_not_found_on_answerable():
    s = score_one(KEY["S01"], row("S01", status="not_found"))
    assert not s["correct"] and s["false_not_found"]


def test_citation_normalization():
    assert norm_cite(" adr-024@v1 ") == "ADR-024@V1"
    assert norm_cite("[CT-SWIFT-2024@A1]") == "CT-SWIFT-2024@A1"


def test_doc_retrieval_recall_is_document_level_and_absent_for_long_context():
    r = score_one(KEY["X01"], row("X01", answer="100 and 120", cites=["ADR-024@v1"], retrieved=["ADR-024@v1"]))
    assert r["doc_retrieval_recall"] == 0.5 and r["retrieval_recall"] == 0.5
    l = score_one(KEY["X01"], row("X01", answer="100 and 120", arm="L", retrieved=["ADR-024@v1"]))
    assert l["doc_retrieval_recall"] is None


def test_known_pattern_limitation_singular_second():
    """The frozen C05 pattern rejects '8 second timeout'. Documented, not silently fixed."""
    s = score_one(KEY["C05"], row("C05", answer="use an 8 second timeout", cites=["SPEC-PAY-INT@v2"]))
    assert s["correct"] is False


def test_manual_review_adds_column_without_changing_original():
    q = KEY["C05"]
    r = row("C05", answer="use an 8 second timeout", cites=["SPEC-PAY-INT@v2"], arm="A")
    s = score_one(q, r)
    k = "stem|A|m|C05"
    reviewed = apply_review(s, {k: {"reviewed_correct": True, "reason": "x"}}, "stem", r)
    assert reviewed["correct"] is False and reviewed["reviewed_correct"] is True
    assert reviewed["reviewed_evidence_valid"] is True
    assert s["correct"] is False


def test_manual_review_entries_point_at_real_rows():
    entries = json.loads((ROOT / "results/review/manual_review.json").read_text())["entries"]
    rows = {f"{MAIN_RUN.stem}|{r['arm']}|{r['model']}|{r['qid']}"
            for r in map(json.loads, MAIN_RUN.read_text(encoding="utf-8").splitlines())}
    assert entries and set(entries) <= rows


@pytest.mark.skipif(not MAIN_RUN.exists(), reason="main run file not present")
def test_historical_main_results_are_unchanged():
    """Regression: the published answer accuracy must be reproducible from the raw JSONL."""
    acc = Counter()
    for r in map(json.loads, MAIN_RUN.read_text(encoding="utf-8").splitlines()):
        acc[(r["arm"], r["model"])] += score_one(KEY[r["qid"]], r)["correct"]
    assert acc == {
        ("L", "gemini-3.8-flash"): 50, ("L", "gemini-4-argon"): 50,
        ("A", "gemini-3.8-flash"): 48, ("A", "gemini-4-argon"): 49,
        ("R2", "gemini-3.8-flash"): 46, ("R2", "gemini-4-argon"): 46,
        ("R1", "gemini-3.8-flash"): 41, ("R1", "gemini-4-argon"): 41,
    }
