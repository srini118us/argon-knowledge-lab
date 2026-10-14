"""Offline analysis of committed results. No API calls; never modifies existing files.

Writes two new files under results/analysis/:
  results_table.md   accuracy, cost, latency and token usage per arm and model
  error_report.md    every incorrect answer, superseded citation and hallucination,
                     with the model's actual answer and citations

    python analyze_results.py results/runs/test_20261013_235517.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from argon_lab.scoring import score_one  # noqa: E402


def fmt(x, d=0):
    return "n/a" if x is None else (f"{x:,.{d}f}" if isinstance(x, (int, float)) else str(x))


def main(path: str) -> None:
    key = {q["id"]: q for q in json.loads((ROOT / "corpus/spec/questions.json").read_text())["questions"]}
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = ROOT / "results" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(path).stem

    groups = defaultdict(list)
    for r in rows:
        groups[(r["arm"], r["model"])].append((r, score_one(key[r["qid"]], r)))

    lines = [f"# Results table: {stem}", "",
             "| Arm | Model | Accuracy | Total cost | Cost per question | Mean latency (s) | Median latency (s) | "
             "Mean input tokens | Mean output tokens | Mean thought tokens | Cached tokens (total) | Share of input cached | Mean tool calls |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (arm, model), g in sorted(groups.items()):
        u = [r.get("usage") or {} for r, _ in g]
        tin = sum(x.get("total_input_tokens", 0) for x in u)
        cached = sum(x.get("total_cached_tokens", 0) for x in u)
        lat = [r.get("api_latency_s") or 0 for r, _ in g]
        cost = sum(r.get("cost_usd") or 0 for r, _ in g)
        lines.append("| " + " | ".join([
            arm, model, f"{sum(s['correct'] for _, s in g)}/{len(g)}", f"${cost:.2f}", f"${cost / len(g):.4f}",
            fmt(mean(lat), 1), fmt(median(lat), 1),
            fmt(mean(x.get("total_input_tokens", 0) for x in u)), fmt(mean(x.get("total_output_tokens", 0) for x in u)),
            fmt(mean(x.get("total_thought_tokens", 0) for x in u)), fmt(cached),
            f"{(cached / tin * 100) if tin else 0:.0f}%", fmt(mean(len(r.get("tool_calls") or []) for r, _ in g), 1)]) + " |")
    (out / f"{stem}_results_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    err = [f"# Error report: {stem}", ""]
    for (arm, model), g in sorted(groups.items()):
        bad = [(r, s) for r, s in g if not s["correct"] or s.get("superseded_cited")]
        err.append(f"## {arm} / {model}: {sum(1 for _, s in g if not s['correct'])} incorrect, "
                   f"{sum(1 for _, s in g if s.get('superseded_cited'))} with a superseded citation")
        for r, s in bad:
            a = r.get("answer") or {}
            tag = "INCORRECT" if not s["correct"] else "correct, but cites a superseded version"
            err.append(f"* **{r['qid']}** ({s['category']}) {tag}. Q: {key[r['qid']]['question']}  "
                       f"\n  Status: {a.get('status')}. Answer: {str(a.get('answer'))[:300]}  "
                       f"\n  Cited: {a.get('citations')}. Required: {key[r['qid']]['required_citations']}. "
                       f"Superseded: {key[r['qid']]['superseded_citations']}")
        err.append("")
    (out / f"{stem}_error_report.md").write_text("\n".join(err), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {out / (stem + '_results_table.md')} and {out / (stem + '_error_report.md')}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
