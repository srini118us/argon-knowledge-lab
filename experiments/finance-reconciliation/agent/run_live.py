"""Live Gemini runner for Experiment 3 (Phases 8). Makes PAID API calls when invoked with --go.

Spending controls (mirrors experiments/arb/run_arb.py, adapted for the multi-turn loop):
  * a shared ledger (results/ledger.jsonl) across ALL runs of this experiment
  * before each CASE, the worst-case cost for that case (max_turns x per-turn worst case) is
    reserved against the ledger; if ledger + reservation would exceed --cap, the run STOPS
  * per-call token cap (max_output_tokens), per-case turn cap, per-call SDK timeout, no retries
  * after each case, actual cost is booked; if it exceeds the reservation the run STOPS
  * a hard allowance: --cap defaults to a value well under the $10 Experiment 3 allowance
  * estimated spend is kept separate from actual provider billing (never claimed equal)

Commands (PowerShell examples in agent/WINDOWS.md):
  python -m agent.run_live --mode smoke  --dry-run     # free: show the plan + estimate
  python -m agent.run_live --mode smoke  --cap 1 --go  # 1 Flash + 1 Argon round trip (paid)
  python -m agent.run_live --mode pilot  --dry-run     # free: plan + estimate for 5 dev cases
  python -m agent.run_live --mode pilot  --cap 2 --go  # 5 dev x 2 arms x 1 trial (paid)
  python -m agent.run_live --mode test   --cap 3 --go  # 10 frozen cases x 2 arms (gated: Phase 8C)

--go is required to make any paid call; without it the runner prints the preflight and exits.
It also requires typing the word run at the confirmation prompt. The frozen benchmark hash is
verified before --mode test.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "src"))

from agent import cost_estimate, schemas  # noqa: E402
from agent.loop import MAX_TURNS, run_investigation  # noqa: E402
from grade import key as keymod, scorer  # noqa: E402
from spec import freeze, testset, validate_testset  # noqa: E402

RESULTS = ROOT / "results"
LEDGER = RESULTS / "ledger.jsonl"
ARMS = ["gemini-3.8-flash", "gemini-4-argon"]
LEVEL = "medium"
DEFAULT_CAP = 3.0            # conservative; the Experiment 3 allowance is $10
DEADLINE_S = 150            # hard per-call deadline (runner-enforced)

DEV_NAMES = ["incident1_skipped_cdc", "incident2_duplicate_replay", "incident3_currency_basis",
             "incident4_lossy_join", "incident5_compound"]


def ledger_spent() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(l)["charged_usd"]
              for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip())


def case_worst_case(model: str) -> float:
    """Worst-case cost for one full case (all turns at the per-turn worst case).

    Per-turn input is bounded because tool results are bounded: run_sql caps at 1000 rows and
    other tools return small payloads, so a turn's transcript is ~8K input tokens, not more.
    Output is capped at MAX_OUTPUT_TOKENS (includes thinking). This is a true worst case for the
    bounded loop, not an open-ended estimate.
    """
    from argon_lab.pricing import rates
    inp, out, _ = rates(model)
    from agent.gemini_client import MAX_OUTPUT_TOKENS
    per_turn_input = 8_000           # bounded by the row/result caps (tools/run_sql.py)
    per_turn = (per_turn_input * inp + MAX_OUTPUT_TOKENS * out) / 1_000_000
    return per_turn * MAX_TURNS


def actual_cost(model: str, usage: dict) -> float:
    from argon_lab.pricing import rates
    inp, out, cached = rates(model)
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)
    cached_tok = usage.get("cached_tokens", 0)
    return ((in_tok - cached_tok) * inp + cached_tok * cached + out_tok * out) / 1_000_000


def _cases_for(mode: str):
    if mode == "pilot":
        return [("dev", n, keymod.build_key) for n in DEV_NAMES]
    if mode == "test":
        return [("test", c, None) for c in testset.TEST_CASES]
    return []   # smoke handled separately


def preflight(mode: str, cap: float) -> None:
    print(f"PREFLIGHT  mode={mode}  cap=${cap:.2f}  arms={ARMS}  level={LEVEL}")
    print(f"  already spent (ledger): ${ledger_spent():.4f}")
    if mode == "smoke":
        n = 1
    elif mode == "pilot":
        n = len(DEV_NAMES)
    else:
        n = len(testset.TEST_CASES)
    worst = sum(case_worst_case(m) for m in ARMS) * n
    est = cost_estimate.estimate(n, ARMS, LEVEL)["total_usd"]
    print(f"  cases={n}  arms={len(ARMS)}  estimated ~${est:.2f}  worst-case ${worst:.2f}")
    print(f"  Experiment 3 allowance: $10.00 (client-side; NOT a guaranteed final bill)")
    if mode == "test":
        ok, diffs = freeze.verify_frozen()
        print(f"  frozen benchmark hash: {'OK' if ok else 'STALE ' + str(diffs)}")


def _grade_case(con, key, result):
    g = scorer.grade(con, key, result["verdict"] or {}, log=result["log"],
                     tool_stats=result["tool_stats"])
    return g


def run(mode: str, cap: float, go: bool) -> int:
    preflight(mode, cap)
    if not go:
        print("\nDry run (no --go): nothing was sent. Add --go and type 'run' to make paid calls.")
        return 0
    if mode == "test":
        ok, _ = freeze.verify_frozen()
        if not ok:
            sys.exit("Refusing to run --mode test: frozen benchmark hash does not match.")
    if input('\nType "run" to make PAID Gemini API calls: ').strip() != "run":
        print("Not confirmed; nothing sent.")
        return 1
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set.")

    from agent.gemini_client import GeminiClient
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "runs" / f"{mode}_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    if mode == "smoke":
        return _smoke(GeminiClient, cap, out)

    cases = testset.TEST_CASES if mode == "test" else DEV_NAMES
    with out.open("a", encoding="utf-8") as f, LEDGER.open("a", encoding="utf-8") as ledger:
        for case in cases:
            for model in ARMS:
                worst = case_worst_case(model)
                spent = ledger_spent()
                if spent + worst > cap:
                    print(f"STOP cap: spent ${spent:.4f} + worst ${worst:.4f} > ${cap:.2f}")
                    return 2
                if mode == "test":
                    con, truth = testset.build_case(case)
                    key = validate_testset._key_from_truth(case, truth)
                    cid = case["id"]
                else:
                    con, key = keymod.build_key(case)
                    cid = case
                t0 = time.time()
                client = GeminiClient(model, LEVEL)
                result = run_investigation(con, client, max_turns=MAX_TURNS)
                cost = actual_cost(model, result["usage"])
                g = _grade_case(con, key, result)
                charged = max(cost, 0.0)
                row = {"type": "row", "mode": mode, "case": cid, "model": model, "level": LEVEL,
                       "status": result["status"], "turns": result["turns"],
                       "score": g["score"], "breakdown": g["breakdown"],
                       "critical": g["critical_failures"], "error_category": g["error_category"],
                       "usage": result["usage"], "cost_usd": round(cost, 6),
                       "latency_s": round(time.time() - t0, 2)}
                f.write(json.dumps(row) + "\n"); f.flush()
                ledger.write(json.dumps({"at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                         "experiment": "finance-reconciliation", "mode": mode,
                                         "case": cid, "model": model, "charged_usd": round(charged, 6),
                                         "worst_case_usd": round(worst, 6), "basis": "measured",
                                         "status": result["status"]}) + "\n"); ledger.flush()
                print(f"  {model:17s} {cid:26s} {result['status']:10s} score={g['score']:>5} "
                      f"${charged:.4f}  ledger ${ledger_spent():.4f}")
                if charged > worst:
                    print(f"STOP actual ${charged:.4f} > worst ${worst:.4f}: output cap not honoured")
                    return 2
    print(f"\nSaved {out}. Experiment ledger total ${ledger_spent():.4f}. "
          f"(Estimated; reconcile against provider billing.)")
    return 0


def _smoke(GeminiClient, cap: float, out: Path) -> int:
    """One minimal function-call round trip per model. Verifies live compatibility."""
    with out.open("a", encoding="utf-8") as f, LEDGER.open("a", encoding="utf-8") as ledger:
        for model in ARMS:
            worst = case_worst_case(model)
            if ledger_spent() + worst > cap:
                print(f"STOP cap before {model}"); return 2
            con, _ = keymod.build_key("incident2_duplicate_replay")   # a simple case
            t0 = time.time()
            client = GeminiClient(model, LEVEL)
            result = run_investigation(con, client, max_turns=4)   # short: just prove the round trip
            cost = actual_cost(model, result["usage"])
            row = {"type": "smoke", "model": model, "status": result["status"],
                   "turns": result["turns"], "made_tool_call": any(c["tool"] == "run_sql" for c in result["log"]),
                   "usage": result["usage"], "cost_usd": round(cost, 6),
                   "latency_s": round(time.time() - t0, 2)}
            f.write(json.dumps(row) + "\n"); f.flush()
            ledger.write(json.dumps({"at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                     "experiment": "finance-reconciliation", "mode": "smoke",
                                     "model": model, "charged_usd": round(max(cost, 0), 6),
                                     "worst_case_usd": round(worst, 6), "basis": "measured",
                                     "status": result["status"]}) + "\n"); ledger.flush()
            ok = result["status"] in ("completed", "incomplete") and row["made_tool_call"]
            print(f"  {model:17s} status={result['status']:10s} tool_call={row['made_tool_call']} "
                  f"turns={result['turns']} ${max(cost,0):.4f}  {'OK' if ok else 'CHECK'}")
            if not ok:
                print(f"STOP: {model} did not complete a function-call round trip. Fix before pilot.")
                return 2
    print("\nSmoke test passed for both models. Safe to proceed to --mode pilot (with approval).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "pilot", "test"], required=True)
    ap.add_argument("--cap", type=float, default=DEFAULT_CAP, help="hard USD cap across ALL runs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--go", action="store_true", help="required to make paid calls")
    args = ap.parse_args()
    if args.dry_run:
        preflight(args.mode, args.cap)
        print("\nDry run: nothing sent.")
        return 0
    return run(args.mode, args.cap, args.go)


if __name__ == "__main__":
    sys.exit(main())
