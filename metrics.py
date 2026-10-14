"""Publication metrics from committed results. Offline: no API calls, no edits to existing files.

Adds, next to the original answer accuracy (unchanged):
  * accuracy on answerable questions and correct abstention on unanswerable ones, separately
  * evidence valid accuracy: correct AND every required current citation cited
  * superseded citations split into historical reference vs outdated authority
  * document level retrieval recall (not passage level)
  * a manual review column from results/review/manual_review.json (documented overrides only)

Writes results/analysis/<run>_metrics.md and results/analysis/<run>_metrics.csv.

    python metrics.py results/runs/test_20261013_235517.jsonl
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
from argon_lab.scoring import apply_review, score_one  # noqa: E402

ARM_NAMES = {"L": "Long context", "A": "Agentic retrieval", "R2": "RAG with captions", "R1": "Text RAG"}


def load_overrides() -> dict:
    p = ROOT / "results" / "review" / "manual_review.json"
    return json.loads(p.read_text(encoding="utf-8"))["entries"] if p.exists() else {}


def compute(path: Path) -> tuple[list[dict], dict]:
    key = {q["id"]: q for q in json.loads((ROOT / "corpus/spec/questions.json").read_text())["questions"]}
    overrides = load_overrides()
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    groups = defaultdict(list)
    for r in rows:
        s = apply_review(score_one(key[r["qid"]], r), overrides, path.stem, r)
        s["cost_usd"] = r.get("cost_usd") or 0
        groups[(r["arm"], r["model"])].append(s)

    summary = []
    for (arm, model), g in sorted(groups.items(), key=lambda kv: (list(ARM_NAMES).index(kv[0][0]), kv[0][1])):
        ans = [s for s in g if s["answerable"]]
        una = [s for s in g if not s["answerable"]]
        recall = [s["doc_retrieval_recall"] for s in ans if s.get("doc_retrieval_recall") is not None]
        summary.append({
            "arm": arm, "approach": ARM_NAMES[arm], "model": model, "n": len(g),
            "answer_accuracy": sum(s["correct"] for s in g),
            "answerable_correct": sum(s["correct"] for s in ans), "answerable_n": len(ans),
            "abstention_correct": sum(s["correct"] for s in una), "unanswerable_n": len(una),
            "evidence_valid": sum(s["evidence_valid"] for s in g),
            "reviewed_accuracy": sum(s["reviewed_correct"] for s in g),
            "reviewed_evidence_valid": sum(s["reviewed_evidence_valid"] for s in g),
            "superseded_historical": sum(1 for s in ans if s.get("superseded_use") == "historical"),
            "superseded_outdated_authority": sum(1 for s in ans if s.get("superseded_use") == "outdated_authority"),
            "false_not_found": sum(1 for s in ans if s["false_not_found"]),
            "hallucinated_on_unanswerable": sum(1 for s in una if s["hallucinated"]),
            "doc_retrieval_recall": round(mean(recall), 3) if recall else None,
            "usage_cost_estimate_usd": round(sum(s["cost_usd"] for s in g), 4),
        })
    detail = {"groups": groups}
    return summary, detail


def main(path_str: str) -> None:
    path = Path(path_str)
    summary, detail = compute(path)
    out = ROOT / "results" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"{path.stem}_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    md = [f"# Publication metrics: {path.stem}", "",
          "Original answer accuracy is unchanged. Evidence valid accuracy additionally requires every required "
          "current citation. Reviewed columns apply only the documented entries in results/review/manual_review.json. "
          "Retrieval recall is document level. Costs are usage based estimates.", "",
          "| Approach | Model | Answer accuracy | Answerable correct | Correct abstentions | Evidence valid | "
          "Reviewed accuracy | Reviewed evidence valid | Superseded: historical | Superseded: outdated authority | "
          "Doc level retrieval recall | Usage cost estimate |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        md.append("| " + " | ".join([
            s["approach"], s["model"], f"{s['answer_accuracy']}/{s['n']}",
            f"{s['answerable_correct']}/{s['answerable_n']}", f"{s['abstention_correct']}/{s['unanswerable_n']}",
            f"{s['evidence_valid']}/{s['n']}", f"{s['reviewed_accuracy']}/{s['n']}",
            f"{s['reviewed_evidence_valid']}/{s['n']}", str(s["superseded_historical"]),
            str(s["superseded_outdated_authority"]),
            "n/a" if s["doc_retrieval_recall"] is None else f"{s['doc_retrieval_recall']:.3f}",
            f"${s['usage_cost_estimate_usd']:.2f}"]) + " |")

    md += ["", "## Answers that are correct but not evidence valid", ""]
    any_miss = False
    for (arm, model), g in sorted(detail["groups"].items()):
        miss = [s for s in g if s["reviewed_correct"] and not s["reviewed_evidence_valid"]]
        if miss:
            any_miss = True
            md.append(f"* {ARM_NAMES[arm]} / {model}: " + ", ".join(f"{s['qid']}" for s in miss))
    if not any_miss:
        md.append("None: every correct answer cited all required current documents.")
    md += ["", "## Evidence valid by category (reviewed)", "",
           "| Approach | Model | " + " | ".join(["single_fact", "cross_document", "conflicting_versions", "diagram", "unanswerable"]) + " |",
           "|---|---|---|---|---|---|---|"]
    for (arm, model), g in sorted(detail["groups"].items(), key=lambda kv: (list(ARM_NAMES).index(kv[0][0]), kv[0][1])):
        cells = []
        for cat in ["single_fact", "cross_document", "conflicting_versions", "diagram", "unanswerable"]:
            c = [s for s in g if s["category"] == cat]
            cells.append(f"{sum(s['reviewed_evidence_valid'] for s in c)}/{len(c)}")
        md.append(f"| {ARM_NAMES[arm]} | {model} | " + " | ".join(cells) + " |")
    (out / f"{path.stem}_metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nWrote {out / (path.stem + '_metrics.md')} and {out / (path.stem + '_metrics.csv')}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
