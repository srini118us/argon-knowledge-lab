"""Run one batch of questions through one or more arm/model/level configurations.

Shows an estimated cost first and asks for confirmation; stops if actual spend
passes --budget. Every question's raw output, usage, trace and timing is
appended to results/runs/<batch>.jsonl. Score with score.py.

    python run.py --split dev --arms R2 L A --models gemini-4-argon gemini-3.8-flash --levels medium --budget 6
    python run.py --split dev --arms L --models gemini-4-argon --levels medium --questions V01 V08 --dry-run
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from argon_lab import arms, corpus  # noqa: E402
from argon_lab.pricing import cost_usd, estimate_usd  # noqa: E402

OUT_TOKENS = {"low": 1000, "medium": 3000, "high": 6000}   # assumption until the pilot measures it


def estimate(arm: str, docs, level: str) -> tuple[int, int]:
    corpus_tokens = sum(len(d.text) for d in docs.values() if d.kind == "text") // 4 + 1100 * sum(
        1 for d in docs.values() if d.kind == "diagram")
    inp = {"R1": 7000, "R2": 7000, "L": corpus_tokens + 400, "A": 30000}[arm]
    out = OUT_TOKENS[level] + (1500 if arm == "A" else 0)
    return inp, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="small")
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--questions", nargs="*", help="restrict to these question IDs")
    ap.add_argument("--arms", nargs="+", choices=["R1", "R2", "L", "A"], required=True)
    ap.add_argument("--models", nargs="+", default=["gemini-4-argon"])
    ap.add_argument("--levels", nargs="+", default=["medium"], choices=["low", "medium", "high"])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--budget", type=float, required=True, help="hard stop in USD for this batch")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()

    qs = json.loads((ROOT / "corpus" / "spec" / "questions.json").read_text())["questions"]
    qs = [q for q in qs if q["split"] == args.split and (not args.questions or q["id"] in args.questions)]
    docs = corpus.load(args.size)

    configs = list(itertools.product(args.arms, args.models, args.levels, range(args.trials)))
    est = 0.0
    print(f"{len(qs)} questions x {len(configs)} configurations = {len(qs) * len(configs)} runs")
    for arm, model, level, _ in configs:
        i, o = estimate(arm, docs, level)
        c = estimate_usd(model, i, o, runs=len(qs))
        est += c
        print(f"  {arm:2s} {model:17s} {level:6s} ~{i:>6,} in / {o:>5,} out per question  ~${c:.2f}")
    print(f"Estimated total ${est:.2f} (no cache savings assumed). Budget cap ${args.budget:.2f}.")
    if args.dry_run:
        return 0
    if any(a in ("R2", "A") for a in args.arms) and not any(d.text for d in docs.values() if d.kind == "diagram"):
        sys.exit("Diagram captions missing: run make_captions.py first (needed by R2 and A).")
    if est > args.budget:
        print("Estimate exceeds the budget; continuing, but the hard stop will apply.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return 1
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set.")

    from google import genai
    from argon_lab.retrieval import Index
    client = genai.Client()
    indexes = {}
    if "R1" in args.arms:
        indexes["text"] = Index(client, docs, include_captions=False, size=args.size)
    if "R2" in args.arms or "A" in args.arms:
        indexes["cap"] = Index(client, docs, include_captions=True, size=args.size)
    embed_tokens = sum(ix.embed_tokens for ix in indexes.values())

    batch = f"{args.split}_{datetime.now():%Y%m%d_%H%M%S}"
    out = ROOT / "results" / "runs" / f"{batch}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    with out.open("w", encoding="utf-8") as f:
        for arm, model, level, trial in configs:
            for q in qs:
                if spent > args.budget:
                    print(f"BUDGET STOP at ${spent:.2f}")
                    return 2
                t0 = time.time()
                row = {"batch": batch, "arm": arm, "model": model, "level": level, "trial": trial,
                       "qid": q["id"], "question": q["question"], "at": datetime.now().isoformat(timespec="seconds")}
                try:
                    if arm in ("R1", "R2"):
                        answer, run = arms.rag(client, model, level, q["question"], indexes["text" if arm == "R1" else "cap"])
                    elif arm == "L":
                        answer, run = arms.long_context(client, model, level, q["question"], docs)
                    else:
                        answer, run = arms.agentic(client, model, level, q["question"], docs, indexes["cap"])
                    cost = cost_usd(model, run.usage)
                    row |= {"answer": answer, "usage": run.usage, "api_latency_s": round(run.latency, 2),
                            "calls": run.calls, "tool_calls": run.tool_calls, "retrieved": sorted(run.retrieved),
                            "notes": run.notes, "cost_usd": round(cost, 6), "error": None}
                except Exception as e:  # noqa: BLE001
                    cost = 0.0
                    row |= {"answer": None, "error": repr(e), "traceback": traceback.format_exc(limit=3)}
                row["wall_s"] = round(time.time() - t0, 2)
                spent += cost
                f.write(json.dumps(row, default=str) + "\n")
                f.flush()
                status = (row.get("answer") or {}).get("status", "ERROR") if row.get("answer") is not None else "ERROR"
                print(f"{arm:2s} {model:17s} {level:6s} {q['id']}  {status:10s} ${cost:.4f}  total ${spent:.2f}")
    print(f"\nSaved {out}\nSpent about ${spent:.2f} plus embeddings (~{embed_tokens:,} tokens, priced separately).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
