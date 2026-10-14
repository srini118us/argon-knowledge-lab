"""Score run files against the frozen key and print a summary per configuration.

    python score.py results/runs/dev_20261014_101500.jsonl [more.jsonl ...]
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from argon_lab.scoring import score_one  # noqa: E402


def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(mean(xs), 3) if xs else None


def main(paths: list[str]) -> None:
    key = {q["id"]: q for q in json.loads((ROOT / "corpus" / "spec" / "questions.json").read_text())["questions"]}
    rows = [json.loads(line) for p in paths for line in Path(p).read_text(encoding="utf-8").splitlines() if line.strip()]
    scored = []
    for r in rows:
        s = score_one(key[r["qid"]], r)
        u = r.get("usage") or {}
        scored.append(s | {k: r.get(k) for k in ("arm", "model", "level", "trial")} | {
            "error": r.get("error"), "cost_usd": r.get("cost_usd") or 0, "latency_s": r.get("api_latency_s"),
            "calls": r.get("calls"), "tool_calls": len(r.get("tool_calls") or []),
            "input_tokens": u.get("total_input_tokens"), "thought_tokens": u.get("total_thought_tokens"),
            "cached_tokens": u.get("total_cached_tokens"), "answer": json.dumps(r.get("answer"))})

    out = ROOT / "results" / "scores"
    out.mkdir(parents=True, exist_ok=True)
    name = Path(paths[0]).stem + ("_plus" if len(paths) > 1 else "")
    with (out / f"{name}_rows.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for s in scored for k in s}))
        w.writeheader()
        w.writerows(scored)

    groups = defaultdict(list)
    for s in scored:
        groups[(s["arm"], s["model"], s["level"])].append(s)
    summary = []
    for (arm, model, level), g in sorted(groups.items()):
        ans = [s for s in g if s["false_not_found"] is not None]
        una = [s for s in g if s["hallucinated"] is not None]
        summary.append({
            "arm": arm, "model": model, "level": level, "n": len(g),
            "errors": sum(1 for s in g if s["error"]),
            "accuracy_all": avg([s["correct"] for s in g]),
            "accuracy_answerable": avg([s["correct"] for s in ans]),
            "abstain_correct_unanswerable": avg([s["correct"] for s in una]),
            "false_not_found": avg([s["false_not_found"] for s in ans]),
            "citation_recall": avg([s.get("citation_recall") for s in ans]),
            "superseded_cited": avg([s.get("superseded_cited") for s in ans]),
            "retrieval_recall": avg([s.get("retrieval_recall") for s in ans]),
            "mean_latency_s": avg([s["latency_s"] for s in g]),
            "mean_input_tokens": avg([s["input_tokens"] for s in g]),
            "mean_thought_tokens": avg([s["thought_tokens"] for s in g]),
            "cached_tokens_total": sum(s["cached_tokens"] or 0 for s in g),
            "mean_tool_calls": avg([s["tool_calls"] for s in g]),
            "cost_usd": round(sum(s["cost_usd"] for s in g), 4),
        })
    with (out / f"{name}_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    cols = ["arm", "model", "level", "n", "errors", "accuracy_all", "abstain_correct_unanswerable",
            "citation_recall", "superseded_cited", "retrieval_recall", "mean_latency_s", "cached_tokens_total", "cost_usd"]
    print(" | ".join(cols))
    for s in summary:
        print(" | ".join(str(s[c]) for c in cols))
    print(f"\nPer category accuracy:")
    cat = defaultdict(list)
    for s in scored:
        cat[(s["arm"], s["model"], s["level"], s["category"])].append(s["correct"])
    for k, v in sorted(cat.items()):
        print(f"  {k[0]:2s} {k[1]:17s} {k[2]:6s} {k[3]:22s} {sum(v)}/{len(v)}")
    print(f"\nSaved {out / (name + '_summary.csv')} and {out / (name + '_rows.csv')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
