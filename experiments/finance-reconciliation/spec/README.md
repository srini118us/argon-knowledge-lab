# Phase 6: test-case generation, difficulty calibration, benchmark freeze

An unseen TEST set, validated and frozen with reproducible hashes. Offline, deterministic, no
Gemini, no API calls. Built only from the existing Phase 2 injectors (no new defect logic); the
injectors gained optional `base`/count parameters (defaults unchanged, so Phases 2-5 are intact).

## The test set (10 cases, distinct from the 5 dev fixtures)

Two varied instances per incident class, on new base ledgers (new seeds), with different defect
magnitudes, counts and key ranges. No case reuses a dev `(incident, seed, base)` signature.

| id | class | variation |
|---|---|---|
| T01, T02 | missing CDC delta | +270K/3 keys; +88K/2 keys |
| T03, T04 | duplicate replay | -210K/3 dups; -60K/2 dups |
| T05, T06 | currency basis | different fx mixes (new ledgers) |
| T07, T08 | lossy join | +174K/3; +52K/2 |
| T09, T10 | compound | missing 600K/dup 220K → net 380K; missing 360K/dup 90K → net 270K |

Compound cases use different splits than the dev +450/-140, and the skipped-CDC cases carry a
benign post-watermark lag row (a genuine pending change that must NOT be flagged).

## Validation (spec/validate_testset.py)

Every case passes four checks, computed from the built world (not asserted):

1. **Financial math** — source-minus-target equals the expected net (compound nets missing-dup).
2. **Affected keys** — each injected key actually exhibits its defect (missing / duplicated /
   amount-drift) at the right layer.
3. **Remediation outcome** — the case's safe remediations, applied on the grader's own overlay,
   close the discrepancy with no residual invariant breach.
4. **Multistep necessity** — a naive "totals-only" strategy (compare the two totals, read off the
   sign, name no keys, propose no fix) scores 0-30, while a real investigation scores 100. Proof
   the case cannot be solved by a single total comparison.

A real bug surfaced here and was fixed honestly: `fix_transform` was listed as a safe remediation
for the lossy-join incident but does not recover inner-join-dropped rows (verified on the
overlay). The lossy-join safe set is now `refresh_customer_snapshot` only.

## Honest baseline result on the frozen test set

The strong deterministic SQL baseline scores **100/100 on all ten test cases** — the same ceiling
seen on dev. Per DESIGN.md 7.2 this is reported as-is: on these incident classes a strong fixed
SQL battery is sufficient, so the eventual model comparison may show little accuracy separation.
No case was tuned to make a model fail or succeed; difficulty was assessed by the independent
necessity criterion (a shortcut cannot solve the case), not by the baseline's score.

Run it: `python experiments/finance-reconciliation/spec/run_phase6.py`

## Freeze (spec/freeze.py → spec/frozen_testset.json)

The frozen file records the case definitions, the ground-truth manifest (per case: discrepancy,
affected keys, layers, safe remediations, counts), the scoring-rule fingerprint, sha256 of every
load-bearing source file, and a single `benchmark_sha256` over all of it. Re-running the freeze
reproduces the identical hash; `python spec/freeze.py` (no args) verifies current == frozen and
fails if anything drifted.

The frozen ground truth lives under `spec/`, which — like `grade/` — is kept off the agent's
import path by `tools/isolation.py`. The agent-visible world carries no answer-label columns.

## Tests

`tests/test_testset.py` (38): separation from dev, per-class variation, financials+keys,
multistep necessity, remediation reconciliation, compound two-defect, benign distractor, honest
baseline scoring, freeze reproducibility, and frozen-file integrity. Full suite: 160 passed.

## Not in Phase 6

No Gemini agent, no model arm, no API calls, no paid evaluation (Phases 7-8, gated on approval).
The frozen test set is ready for the capability probe (Phase 7) and the model run (Phase 8).
