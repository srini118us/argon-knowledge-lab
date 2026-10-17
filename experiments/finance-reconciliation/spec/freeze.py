"""Freeze the test benchmark with reproducible hashes (Phase 6).

Writes spec/frozen_testset.json: the test-case definitions (ids, classes, seeds, params),
the ground-truth manifest (per case: expected discrepancy, affected keys, root-cause layers,
safe remediations), the scoring-rule fingerprint, and sha256 hashes of every load-bearing
source file. Re-running this must reproduce identical hashes, or the freeze is stale.

The frozen file contains the ground truth, so it lives under spec/ and is part of the grader
side; the agent process never imports it (tools/isolation.py keeps spec/ off the agent path).

    python experiments/finance-reconciliation/spec/freeze.py            # verify current == frozen
    python experiments/finance-reconciliation/spec/freeze.py --write    # (re)write the frozen file
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from sim import reconcile  # noqa: E402
from spec import testset  # noqa: E402

FROZEN = HERE / "frozen_testset.json"

# Source files whose content defines the benchmark and the scoring. A change to any of these
# changes the hashes, which is the signal that the frozen benchmark must be reviewed/re-frozen.
HASHED_FILES = [
    "sim/schema.py", "sim/world.py", "sim/injectors.py", "sim/reconcile.py",
    "spec/testset.py", "grade/scorer.py", "grade/key.py", "tools/run_sql.py", "tools/tools.py",
]


def sha256_file(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def ground_truth_manifest() -> list[dict]:
    """Per-case ground truth, computed from the built world (not asserted)."""
    manifest = []
    for case in testset.TEST_CASES:
        con, truth = testset.build_case(case)
        s = reconcile.summary(con)
        manifest.append({
            "id": case["id"],
            "incident_class": truth["incident"],
            "seed": case["seed"],
            "params": case["params"],
            "discrepancy": s["discrepancy"],
            "expected_net": testset.expected_net(case),
            "root_cause_layers": truth["root_cause_layer"],
            "affected_keys": {k: ["/".join(map(str, bk)) for bk in v]
                              for k, v in truth["affected_keys"].items()},
            "safe_remediations": sorted(truth["safe_remediations"]),
            "counts": {"missing": s["missing_at_mart"], "duplicated": s["duplicated_at_mart"],
                       "amount_mismatch": s["amount_mismatches"]},
        })
    return manifest


def scoring_rules_fingerprint() -> dict:
    """The scoring rules, recorded so a change is visible in the freeze."""
    return {
        "dimensions": {"root_cause": 30, "affected_keys": 20, "evidence": 15,
                       "remediation": 15, "verification": 20},
        "verification": "grader applies proposed remediations to its own overlay; closes "
                        "discrepancy within 0.01 AND no residual invariant breach",
        "critical_failures": ["unsafe_attempts", "overclaim", "premature_termination"],
        "tolerance": 0.01,
    }


def build_frozen() -> dict:
    return {
        "benchmark": "finance-reconciliation",
        "split": "test",
        "n_cases": len(testset.TEST_CASES),
        "file_hashes": {f: sha256_file(f) for f in HASHED_FILES},
        "scoring_rules": scoring_rules_fingerprint(),
        "ground_truth": ground_truth_manifest(),
    }


def _canonical(d: dict) -> str:
    return json.dumps(d, sort_keys=True, indent=1)


def write_frozen() -> str:
    frozen = build_frozen()
    content = _canonical(frozen)
    # a self-hash over the ground truth + file hashes, so the whole benchmark has one fingerprint
    frozen["benchmark_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    FROZEN.write_text(_canonical(frozen) + "\n", encoding="utf-8")
    return frozen["benchmark_sha256"]


def verify_frozen() -> tuple[bool, list[str]]:
    """Return (ok, diffs). ok=True means the current benchmark matches the frozen file."""
    if not FROZEN.exists():
        return False, ["frozen_testset.json does not exist; run with --write"]
    saved = json.loads(FROZEN.read_text(encoding="utf-8"))
    current = build_frozen()
    diffs = []
    for f, h in current["file_hashes"].items():
        if saved.get("file_hashes", {}).get(f) != h:
            diffs.append(f"hash changed: {f}")
    if saved.get("scoring_rules") != current["scoring_rules"]:
        diffs.append("scoring rules changed")
    if saved.get("ground_truth") != current["ground_truth"]:
        diffs.append("ground truth changed")
    return (not diffs), diffs


def main() -> int:
    if "--write" in sys.argv:
        fp = write_frozen()
        print(f"Wrote {FROZEN.name}; benchmark_sha256={fp}")
        return 0
    ok, diffs = verify_frozen()
    if ok:
        saved = json.loads(FROZEN.read_text(encoding="utf-8"))
        print(f"Frozen benchmark matches current. benchmark_sha256={saved.get('benchmark_sha256')}")
        return 0
    print("Frozen benchmark is STALE:\n  " + "\n  ".join(diffs))
    return 1


if __name__ == "__main__":
    sys.exit(main())
