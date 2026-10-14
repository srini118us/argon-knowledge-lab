"""Deterministic scoring against the frozen answer key. No model grades anything."""
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
    if q["status"] == "not_found":
        out["correct"] = status == "not_found"
        out["hallucinated"] = status == "answered"
        out["false_not_found"] = None
    else:
        facts_ok = all(re.search(f, text, re.I) for f in q["key_facts"])
        out["correct"] = status == "answered" and facts_ok
        out["hallucinated"] = None
        out["false_not_found"] = status == "not_found"
        out["citation_recall"] = len(cites & required) / len(required) if required else None
        out["citation_precision"] = (len(cites & required) / len(cites)) if cites else 0.0
        out["superseded_cited"] = bool(cites & superseded)
        out["retrieval_recall"] = len(retrieved & required) / len(required) if required and row.get("arm") != "L" else None
    return out
