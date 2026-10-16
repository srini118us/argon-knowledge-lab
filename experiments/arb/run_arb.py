"""Experiment 2 runner: Architecture Review Board decisions. Paid API calls; requires approval.

    python experiments/arb/run_arb.py --split dev  --cap 5 --dry-run     # free: preflight estimate
    python experiments/arb/run_arb.py --split dev  --cap 5               # pilot, asks for typed confirmation
    python experiments/arb/run_arb.py --split test --cap 5

Spending guard (stricter than Experiment 1's):
  * Before EVERY call, the worst case for that call (input estimate at the input rate plus
    max_output_tokens at the output rate) is added to everything already spent in the ledger for this
    experiment. If that would exceed --cap, the run stops before the call. The cap therefore cannot
    be exceeded unless the API ignores max_output_tokens.
  * After every call, if actual cost exceeds the worst case assumed for it, the run stops and says so
    (this detects an output cap that is not honoured, for example if thinking is not counted in it).
  * Every call, successful or failed, is appended to results/ledger.jsonl with its interaction ID and
    UTC timestamp, so the ledger can be reconciled against billing. A failed call is logged with a
    worst case cost, not $0.
  * No retries: a failed call is recorded and the run continues with the next case.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import arb  # noqa: E402
import engine  # noqa: E402
from argon_lab.pricing import cost_usd, rates  # noqa: E402

RESULTS = HERE / "results"
LEDGER = RESULTS / "ledger.jsonl"
ARMS = [("gemini-3.8-flash", "medium"), ("gemini-3.8-flash", "high"),
        ("gemini-4-argon", "medium"), ("gemini-4-argon", "high")]
MAX_OUTPUT_TOKENS = 16_000
# Planning assumptions for the estimate only (output plus thinking tokens per case). Replaced by
# measured values after the pilot.
ASSUMED_OUTPUT = {"medium": 3_000, "high": 8_000}


class CapReached(Exception):
    pass


def input_tokens_estimate(case: dict) -> int:
    chars = len(arb.SYSTEM) + sum(len(p["text"]) for p in arb.prompt(case))
    return chars // 4 + 50


def worst_case_usd(model: str, case: dict) -> float:
    inp, out, _ = rates(model)
    return (input_tokens_estimate(case) * inp + MAX_OUTPUT_TOKENS * out) / 1_000_000


def expected_usd(model: str, level: str, case: dict) -> float:
    inp, out, _ = rates(model)
    return (input_tokens_estimate(case) * inp + ASSUMED_OUTPUT[level] * out) / 1_000_000


def ledger_spent() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(l)["charged_usd"] for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip())


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def verify_key() -> None:
    """Refuse to run if the frozen key no longer matches the engine and cases."""
    key = arb.load_key()
    for c in arb.load_cases():
        r = engine.evaluate(c)
        k = key[c["id"]]
        if (k["decision"], k["violations"], k["conditions"]) != (r["decision"], r["violations"], r["conditions"]):
            sys.exit(f"spec/key.json is stale for {c['id']}: run check_cases.py --write and commit before running.")


def call_model(client, model: str, level: str, case: dict):
    """One structured call. Returns (interaction, parsed answer or None, raw text)."""
    ix = client.interactions.create(
        model=model, input=arb.prompt(case), system_instruction=arb.SYSTEM,
        generation_config={"thinking_level": level, "max_output_tokens": MAX_OUTPUT_TOKENS},
        response_format={"type": "text", "mime_type": "application/json", "schema": arb.SCHEMA})
    text = getattr(ix, "output_text", "") or ""
    try:
        ans = json.loads(text)
    except json.JSONDecodeError:
        ans = None
    return ix, ans, text


def usage_dict(ix) -> dict:
    u = getattr(ix, "usage", None)
    keys = ["total_input_tokens", "total_output_tokens", "total_thought_tokens",
            "total_cached_tokens", "total_tool_use_tokens", "total_tokens"]
    return {k: (getattr(u, k, 0) or 0) if u else 0 for k in keys}


def run(client, cases, arms, trials, cap, out_path, log=print) -> dict:
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = {"calls": 0, "spent": 0.0, "stopped": None}
    with out_path.open("a", encoding="utf-8") as f, LEDGER.open("a", encoding="utf-8") as ledger:
        for trial in range(trials):
            for model, level in arms:
                for case in cases:
                    worst = worst_case_usd(model, case)
                    already = ledger_spent()
                    if already + worst > cap:
                        stats["stopped"] = f"cap: spent ${already:.4f} + worst case ${worst:.4f} > ${cap:.2f}"
                        log("STOP " + stats["stopped"])
                        return stats
                    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    t0 = time.time()
                    row = {"type": "row", "case": case["id"], "split": case["split"], "model": model,
                           "level": level, "trial": trial, "at_utc": at}
                    try:
                        ix, ans, text = call_model(client, model, level, case)
                        usage = usage_dict(ix)
                        cost = cost_usd(model, usage)
                        row |= {"interaction_id": getattr(ix, "id", None), "answer": ans,
                                "raw_text": None if ans else text[:2000], "usage": usage,
                                "cost_usd": round(cost, 6), "error": None}
                        charged = cost
                    except Exception as e:  # noqa: BLE001
                        row |= {"interaction_id": None, "answer": None, "usage": None, "cost_usd": None,
                                "error": repr(e)[:500]}
                        charged = worst   # unknown actual: assume the worst for the cap
                    row["latency_s"] = round(time.time() - t0, 2)
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                    ledger.write(json.dumps({"at_utc": at, "experiment": "arb", "model": model, "level": level,
                                             "case": case["id"], "interaction_id": row["interaction_id"],
                                             "usage": row["usage"], "charged_usd": round(charged, 6),
                                             "worst_case_usd": round(worst, 6), "error": row["error"]}) + "\n")
                    ledger.flush()
                    stats["calls"] += 1
                    stats["spent"] += charged
                    dec = (row["answer"] or {}).get("decision", "ERROR")
                    log(f"{model:17s} {level:6s} {case['id']:5s} {dec:24s} ${charged:.4f}  "
                        f"ledger ${already + charged:.4f}")
                    if row["error"] is None and charged > worst:
                        stats["stopped"] = f"actual ${charged:.4f} exceeded worst case ${worst:.4f}: output cap not honoured"
                        log("STOP " + stats["stopped"])
                        return stats
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--cap", type=float, required=True, help="hard cap in USD across ALL runs of this experiment")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--cases", nargs="*", help="limit to these case IDs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verify_key()
    cases = [c for c in arb.load_cases(args.split) if not args.cases or c["id"] in args.cases]
    est = worst = 0.0
    print(f"{len(cases)} {args.split} cases x {len(ARMS)} arms x {args.trials} trial(s) = "
          f"{len(cases) * len(ARMS) * args.trials} calls; pack ~{len(arb.pack_text()) // 4:,} tokens")
    for model, level in ARMS:
        e = sum(expected_usd(model, level, c) for c in cases) * args.trials
        w = sum(worst_case_usd(model, c) for c in cases) * args.trials
        est, worst = est + e, worst + w
        print(f"  {model:17s} {level:6s} expected ~${e:.3f}   worst case ${w:.3f}")
    spent = ledger_spent()
    print(f"Expected ~${est:.2f}; worst case ${worst:.2f}. Already spent on this experiment: ${spent:.2f}. "
          f"Hard cap ${args.cap:.2f}.")
    if args.dry_run:
        return 0
    if input('Type "run" to make paid API calls: ').strip() != "run":
        print("Not confirmed; nothing sent.")
        return 1
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set.")
    from google import genai
    import google.genai as gg
    client = genai.Client()
    out = RESULTS / "runs" / f"{args.split}_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = {"type": "header", "sdk": getattr(gg, "__version__", "unknown"), "python": platform.python_version(),
              "split": args.split, "trials": args.trials, "arms": ARMS, "max_output_tokens": MAX_OUTPUT_TOKENS,
              "pack_sha256": sha256(arb.pack_text()),
              "key_sha256": sha256((arb.SPEC / "key.json").read_text(encoding="utf-8")),
              "rates": {m: rates(m) for m, _ in ARMS}, "retries": "none"}
    out.write_text(json.dumps(header) + "\n", encoding="utf-8")
    stats = run(client, cases, ARMS, args.trials, args.cap, out)
    print(f"\nSaved {out}\nCalls {stats['calls']}, charged ${stats['spent']:.4f}, "
          f"experiment total ${ledger_spent():.4f}" + (f"\nStopped: {stats['stopped']}" if stats["stopped"] else ""))
    return 2 if stats["stopped"] else 0


if __name__ == "__main__":
    sys.exit(main())
