"""P7c: load the corpus once, branch every question from that one interaction.

Every question uses previous_interaction_id = the corpus loading interaction,
so questions never see each other (no cross contamination) while the server
holds the shared corpus. Records cached tokens, latency, and whether each
answer is right (clause N is covered by control AP-(1000+N)).

    python probes/cache_branch_probe.py                 # about $0.25
    python probes/cache_branch_probe.py --model gemini-3.8-flash
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "probes"))
from argon_lab.pricing import cost_usd  # noqa: E402
from cache_probe import prefix_text  # noqa: E402

CLAUSES_NOW = [17, 83, 140, 201, 255]
CLAUSES_LATER = [9, 230]


def ask(client, model, base_id, clause, label):
    t0 = time.time()
    ix = client.interactions.create(model=model, previous_interaction_id=base_id,
                                    input=f"Which control covers clause {clause}? Reply with the control ID only.",
                                    generation_config={"thinking_level": "low"})
    u = ix.usage
    expected = f"AP-{1000 + clause}"
    row = {"label": label, "clause": clause, "latency_s": round(time.time() - t0, 2),
           "input": u.total_input_tokens, "cached": u.total_cached_tokens or 0,
           "output": u.total_output_tokens, "answer": (ix.output_text or "").strip(),
           "correct": expected in (ix.output_text or ""), "cost_usd": round(cost_usd(model, u), 6)}
    print(f"{label:4s} clause={clause:3d} input={row['input']:6d} cached={row['cached']:6d} "
          f"latency={row['latency_s']:6.2f}s correct={row['correct']}")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-4-argon")
    args = ap.parse_args()
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set.")
    from google import genai
    client = genai.Client()

    t0 = time.time()
    base = client.interactions.create(model=args.model, input=prefix_text() + "\n\nRead this manual. Reply OK.",
                                      generation_config={"thinking_level": "low"})
    rows = [{"label": "BASE", "latency_s": round(time.time() - t0, 2), "input": base.usage.total_input_tokens,
             "cached": base.usage.total_cached_tokens or 0, "cost_usd": round(cost_usd(args.model, base.usage), 6)}]
    print(f"BASE input={rows[0]['input']} cached={rows[0]['cached']} latency={rows[0]['latency_s']}s")

    for i, c in enumerate(CLAUSES_NOW):
        rows.append(ask(client, args.model, base.id, c, f"N{i}"))
    print("waiting 60 s ...")
    time.sleep(60)
    for i, c in enumerate(CLAUSES_LATER):
        rows.append(ask(client, args.model, base.id, c, f"L{i}"))

    branches = [r for r in rows if r["label"] != "BASE"]
    # A hit counts only if at least half the input was served from cache; a
    # small constant (22 tokens was seen even on the very first request) is
    # not a corpus cache hit.
    hits = sum(1 for r in branches if r["cached"] >= 0.5 * r["input"])
    correct = sum(1 for r in branches if r["correct"])
    total = round(sum(r["cost_usd"] for r in rows), 4)
    print(f"\nBranches with substantial cache hits (>=50% of input): {hits}/{len(branches)}   correct answers: {correct}/{len(branches)}   total cost ${total}")
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    path = out / f"cache_branch_{args.model}_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps({"model": args.model, "rows": rows, "hits": hits, "correct": correct,
                                "total_cost_usd": total}, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
