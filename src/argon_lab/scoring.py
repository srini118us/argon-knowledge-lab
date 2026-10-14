"""Deterministic scoring against the frozen answer key. No model grades anything.

Metrics per question (all deterministic):
  correct              answer accuracy as originally scored (key fact regexes, or not_found)
  evidence_valid       correct AND every required current citation is cited (answerable);
                       for unanswerable questions, equal to a correct abstention
  superseded_use       None, "historical" (a superseded version is cited alongside every
                       required current citation), or "outdated_authority" (a superseded
                       version is cited while a required current citation is missing)
  doc_retrieval_recall share of required DOCUMENTS present among retrieved or read
                       documents (RAG and agent only). Document level only: it does not
                       show that the specific evidence passage was retrieved.
`retrieval_recall` is kept as an alias of doc_retrieval_recall so historical score
files keep their meaning.
"""
from __future__ import annotations

import re


def norm_cite(c: str) -> str:
    c = str(c).strip().upper().replace(" ", "")
    c = re.sub(r"^\[|\]$", "", c)
    return c


def score_one(q: dict, row: dict) -> dict:
    ans = row.get("answer") or {}
    status = ans.get("status") if isinstance(ans, dict) else None
    text = (ans.get("answer") or "") if isinstance(ans, dict) else ""
    cites = {norm_cite(c) for c in (ans.get("citations") or [])} if isinstance(ans, dict) else set()
    required = {norm_cite(c) for c in q["required_citations"]}
    superseded = {norm_cite(c) for c in q["superseded_citations"]}
    retrieved = {norm_cite(c) for c in row.get("retrieved", [])}

    out = {"qid": q["id"], "category": q["category"], "valid_output": status in ("answered", "not_found")}
    out["answerable"] = q["status"] != "not_found"
    if q["status"] == "not_found":
        out["correct"] = status == "not_found"
        out["hallucinated"] = status == "answered"
        out["false_not_found"] = None
        out["evidence_valid"] = out["correct"]
        out["all_required_cited"] = True
        out["superseded_use"] = None
    else:
        facts_ok = all(re.search(f, text, re.I) for f in q["key_facts"])
        out["correct"] = status == "answered" and facts_ok
        out["hallucinated"] = None
        out["false_not_found"] = status == "not_found"
        out["citation_recall"] = len(cites & required) / len(required) if required else None
        out["citation_precision"] = (len(cites & required) / len(cites)) if cites else 0.0
        out["superseded_cited"] = bool(cites & superseded)
        all_required = required <= cites
        out["all_required_cited"] = all_required
        out["evidence_valid"] = out["correct"] and all_required
        out["superseded_use"] = (None if not out["superseded_cited"]
                                 else "historical" if all_required else "outdated_authority")
        recall = len(retrieved & required) / len(required) if required and row.get("arm") != "L" else None
        out["doc_retrieval_recall"] = recall
        out["retrieval_recall"] = recall
    return out


def apply_review(scored: dict, overrides: dict, run_stem: str, row: dict) -> dict:
    """Return a copy with `reviewed_correct`: the original `correct` unless a documented
    manual review entry overrides it. The original `correct` is never changed."""
    k = f"{run_stem}|{row.get('arm')}|{row.get('model')}|{row.get('qid')}"
    s = dict(scored)
    entry = overrides.get(k)
    s["reviewed_correct"] = entry["reviewed_correct"] if entry else scored["correct"]
    s["reviewed_evidence_valid"] = s["reviewed_correct"] and scored["all_required_cited"]
    s["review_note"] = entry["reason"] if entry else None
    return s
