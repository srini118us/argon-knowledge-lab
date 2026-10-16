"""Deterministic scoring for Experiment 2. Offline.

    python experiments/arb/score_arb.py experiments/arb/results/runs/<file>.jsonl

Per case:
  decision_correct   exact match of approve / approve_with_conditions / reject
  violations P/R     set of rule IDs against the key
  conditions P/R     set of rule IDs against the key
  fully_correct      decision, violations and conditions all exact
  evidence_valid     fully_correct AND every required citation present
  superseded_reliance  cites SEC-POL@v2 for a clause without citing SEC-POL@v3 for the same clause
  unknown_citations  citations naming a document or clause that does not exist in the pack
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import arb  # noqa: E402
from check_cases import pack_docs  # noqa: E402

RULE_IDS = sorted(json.loads((HERE / "spec" / "policy.json").read_text(encoding="utf-8"))["rules"], key=len, reverse=True)


def norm_ids(items) -> set[str]:
    """Known rule IDs found in each item, tolerant of forms like 'SEC-POL@v3#SP-3.1' or 'SP-3.1 (transport)'.
    Waiver IDs (W-xx) are citations, not rules, and are ignored here."""
    out = set()
    for s in items or []:
        s = str(s).upper().split("#")[-1]
        for rid in RULE_IDS:
            if re.search(rf"(?<![\w.-]){re.escape(rid)}(?![\w.])", s):
                out.add(rid)
                break
    return out


def norm_cite(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).strip("[]()").upper()


def cite_valid(c: str, docs: dict) -> bool:
    doc, _, clause = norm_cite(c).partition("#")
    match = {k.upper(): v for k, v in docs.items()}
    if doc not in match:
        return False
    return not clause or f"**{clause}" in match[doc].upper()


def score_one(key: dict, ans: dict | None, docs: dict) -> dict:
    if not ans:
        return {"parsed": False, "decision_correct": False, "fully_correct": False, "evidence_valid": False,
                "viol_tp": 0, "viol_fp": 0, "viol_fn": len(key["violations"]),
                "cond_tp": 0, "cond_fp": 0, "cond_fn": len(key["conditions"]),
                "superseded_reliance": False, "unknown_citations": 0}
    gv, gc = set(key["violations"]), set(key["conditions"])
    pv, pc = norm_ids(ans.get("violations")), norm_ids(ans.get("conditions"))
    cites = {norm_cite(c) for c in ans.get("citations") or []}
    dec_ok = ans.get("decision") == key["decision"]
    full = dec_ok and pv == gv and pc == gc
    req_ok = all(any(c == r.upper() or c.startswith(r.upper() + "#") for c in cites) for r in key["required_citations"])
    v2 = {c.split("#")[1] for c in cites if c.startswith("SEC-POL@V2#")}
    v3 = {c.split("#")[1] for c in cites if c.startswith("SEC-POL@V3#")}
    return {"parsed": True, "decision_correct": dec_ok, "fully_correct": full, "evidence_valid": full and req_ok,
            "viol_tp": len(pv & gv), "viol_fp": len(pv - gv), "viol_fn": len(gv - pv),
            "cond_tp": len(pc & gc), "cond_fp": len(pc - gc), "cond_fn": len(gc - pc),
            "superseded_reliance": bool(v2 - v3),
            "unknown_citations": sum(1 for c in cites if not cite_valid(c, docs))}


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def summarize(rows: list[dict]) -> list[dict]:
    key, docs = arb.load_key(), pack_docs()
    groups = defaultdict(list)
    for r in rows:
        s = score_one(key[r["case"]], r.get("answer"), docs)
        s |= {"case": r["case"], "cost": r.get("cost_usd") or 0.0, "latency": r.get("latency_s") or 0.0,
              "usage": r.get("usage") or {}, "error": r.get("error")}
        groups[(r["model"], r["level"])].append(s)
    out = []
    for (model, level), g in groups.items():
        n = len(g)
        vp, vr, vf = prf(sum(s["viol_tp"] for s in g), sum(s["viol_fp"] for s in g), sum(s["viol_fn"] for s in g))
        cp, cr, cf = prf(sum(s["cond_tp"] for s in g), sum(s["cond_fp"] for s in g), sum(s["cond_fn"] for s in g))
        full = sum(s["fully_correct"] for s in g)
        cost = sum(s["cost"] for s in g)
        out.append({
            "model": model, "level": level, "n": n, "errors": sum(1 for s in g if s["error"]),
            "decision_correct": sum(s["decision_correct"] for s in g), "fully_correct": full,
            "evidence_valid": sum(s["evidence_valid"] for s in g),
            "violation_f1": round(vf, 3), "violation_precision": round(vp, 3), "violation_recall": round(vr, 3),
            "condition_f1": round(cf, 3),
            "superseded_reliance": sum(s["superseded_reliance"] for s in g),
            "unknown_citations": sum(s["unknown_citations"] for s in g),
            "cost_usd": round(cost, 4), "cost_per_fully_correct": round(cost / full, 4) if full else None,
            "median_latency_s": round(median(s["latency"] for s in g), 2),
            "mean_input_tokens": round(mean(s["usage"].get("total_input_tokens", 0) for s in g)),
            "mean_output_plus_thinking": round(mean(s["usage"].get("total_output_tokens", 0)
                                                    + s["usage"].get("total_thought_tokens", 0) for s in g)),
            "missed_cases": [s["case"] for s in g if not s["fully_correct"]],
        })
    return sorted(out, key=lambda d: (d["model"], d["level"]))


def main(path: str) -> None:
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r.get("type") == "row"]
    for s in summarize(rows):
        print(json.dumps(s))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
