"""Implicit caching probe for Argon (P7b).

P7 sent the same ~11.4K token prefix twice and saw total_cached_tokens = 0
both times. One pair proves nothing either way, so this probe repeats the
test in three patterns and records every request:

  A  same prefix, 6 requests back to back (stateless)
  B  same prefix, 3 requests 30 s apart
  C  stateful chain: first request carries the prefix, 3 follow ups use
     previous_interaction_id (the server holds the history)

A cache hit is claimed only where total_cached_tokens > 0.

    python probes/cache_probe.py              # about $0.30 at introductory pricing
    python probes/cache_probe.py --model gemini-3.8-flash
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
from argon_lab.pricing import cost_usd  # noqa: E402


def prefix_text() -> str:
    clauses = [f"Clause {i}: Invoices for material class HX{i % 9} require a posted goods receipt, "
               f"a matching purchase order line, and a recorded approval for any variance above zero. "
               f"Reference control AP-{1000 + i}." for i in range(260)]
    return "Contoso procurement policy manual.\n" + "\n".join(clauses)


def record(model, ix, t0, label):
    u = ix.usage
    row = {"label": label, "latency_s": round(time.time() - t0, 2),
           "input": u.total_input_tokens, "cached": u.total_cached_tokens or 0,
           "output": u.total_output_tokens, "thought": u.total_thought_tokens or 0,
           "cost_usd": round(cost_usd(model, u), 6), "at": datetime.now().isoformat(timespec="seconds")}
    print(f"{label:12s} input={row['input']:6d} cached={row['cached']:6d} latency={row['latency_s']}s")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-4-argon")
    args = ap.parse_args()
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set.")
    from google import genai
    client = genai.Client()
    prefix = prefix_text()
    cfg = {"thinking_level": "low"}
    rows = []

    for i in range(6):
        t0 = time.time()
        ix = client.interactions.create(model=args.model, input=prefix + f"\n\nQ{i}: Which control covers clause {17 + i}? One line.",
                                        generation_config=cfg)
        rows.append(record(args.model, ix, t0, f"A{i}"))

    for i in range(3):
        time.sleep(30)
        t0 = time.time()
        ix = client.interactions.create(model=args.model, input=prefix + f"\n\nQ{i}: Which control covers clause {40 + i}? One line.",
                                        generation_config=cfg)
        rows.append(record(args.model, ix, t0, f"B{i}"))

    t0 = time.time()
    ix = client.interactions.create(model=args.model, input=prefix + "\n\nRead this manual. Reply OK.", generation_config=cfg)
    rows.append(record(args.model, ix, t0, "C0"))
    prev = ix.id
    for i in range(3):
        t0 = time.time()
        ix = client.interactions.create(model=args.model, previous_interaction_id=prev,
                                        input=f"Which control covers clause {60 + i}? One line.", generation_config=cfg)
        rows.append(record(args.model, ix, t0, f"C{i + 1}"))
        prev = ix.id

    hits = [r["label"] for r in rows if r["cached"] >= 0.5 * r["input"]]
    total = round(sum(r["cost_usd"] for r in rows), 4)
    print(f"\nRequests with cache hits: {hits or 'none'}   total cost ${total}")
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    path = out / f"cache_probe_{args.model}_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps({"model": args.model, "rows": rows, "hits": hits, "total_cost_usd": total}, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
