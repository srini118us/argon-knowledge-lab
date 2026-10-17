"""Inspect and re-score a saved pilot/test run OFFLINE (no API calls).

After a live run, this reads the saved verdicts and shows, per case, what the model actually
submitted versus what the grader expected -- so low scores can be diagnosed (genuine model
error vs a format mismatch in grading) without spending anything.

    python -m agent.inspect_run results/runs/pilot_YYYYMMDD_HHMMSS.jsonl
    python -m agent.inspect_run <file> --verdicts    # dump each submitted verdict in full

Requires rows saved with the "verdict" field (runner updated 2026-10-17).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from grade import key as keymod  # noqa: E402
from grade.key import all_affected_keys  # noqa: E402


def load_rows(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()
            if l.strip() and json.loads(l).get("type") == "row"]


def expected_keys_for(case_id: str) -> set[str]:
    # dev cases are named incidentN_...; build their key from the injector truth
    try:
        _, key = keymod.build_key(case_id)
        return all_affected_keys(key)
    except Exception:
        return set()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--verdicts", action="store_true", help="dump each full verdict")
    args = ap.parse_args()
    rows = load_rows(args.path)

    for r in rows:
        v = r.get("verdict")
        print("=" * 78)
        print(f"{r['model']}  {r['case']}  status={r['status']}  score={r['score']}")
        if v is None:
            print("  NO VERDICT SAVED (older run, or model never submitted)")
            continue
        reported = set(str(k) for k in (v.get("affected_business_keys") or []))
        expected = expected_keys_for(r["case"])
        print(f"  root_causes: {[(rc.get('incident_class'), rc.get('layer')) for rc in (v.get('root_causes') or [])]}")
        print(f"  reported keys ({len(reported)}): {sorted(reported)[:4]}{'...' if len(reported) > 4 else ''}")
        print(f"  expected keys ({len(expected)}): {sorted(expected)[:4]}{'...' if len(expected) > 4 else ''}")
        overlap = reported & expected
        print(f"  overlap: {len(overlap)}  |  reported-not-expected: {len(reported - expected)}")
        print(f"  proposed_remediations: {[p.get('action_type') for p in (v.get('proposed_remediations') or [])]}")
        if args.verdicts:
            print("  FULL VERDICT:")
            print("   " + json.dumps(v, indent=2, default=str)[:1200].replace("\n", "\n   "))


if __name__ == "__main__":
    main()
