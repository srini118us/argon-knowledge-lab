# Experiment 3: Enterprise Finance Reconciliation Agent

**Question.** Given an identical set of bounded tools and an independent grader, can Gemini 3.8 Flash
and Gemini 4 Argon autonomously investigate a finance reconciliation discrepancy across a synthetic
SAP S/4HANA -> Databricks data path — and does a frontier model add measurable value over a cheaper
one, or over no model at all?

**Short answer.** A strong deterministic SQL baseline solves all 15 synthetic incidents perfectly
(100/100). Both models investigate but do not complete correct structured diagnoses: across three
development pilots neither scored above 16/100, frequently failing to submit a verdict and, when
forced to, **fabricating record identifiers that do not exist in the data**. Flash was 3-4x cheaper
and faster than Argon with no accuracy disadvantage. This is a single-trial case study on synthetic
data, framed as a methods demonstration and a candid negative result — not a benchmark verdict that
one model beats the other. Full write-up: [`REPORT.md`](REPORT.md).

Status: offline apparatus complete and frozen; live pilots run on the development set only (the
10-case test set remains sealed). Estimated live spend: ~$1.55.

## Why this experiment

It is the third of three. Experiment 1 tested **retrieval**; Experiment 2 tested **governed
reasoning** with all evidence supplied; Experiment 3 tests **verified action** — gathering evidence
with tools and turning it into a correct, independently checkable diagnosis. The headline finding
sits exactly on that last step: the models can gather evidence but not reliably ground a structured,
verifiable verdict in it.

## The scenario

AR in SAP S/4HANA does not match a downstream Databricks finance mart, and every pipeline monitor
shows SUCCESS. The data path is S/4HANA -> CDC -> Datasphere data product -> Delta share -> Databricks
mart. The investigator must find the root cause, the exact affected accounting records, and a safe
remediation, then verify the repair reconciles the data. Everything is synthetic.

Five incident classes: missing CDC batch, duplicate downstream replay, wrong currency basis, lossy
downstream join, and a compound of two offsetting defects (netting, e.g., +450K missing and -140K
duplicated to +310K).

## What is in this folder

| Path | What it is | Paid? |
|---|---|---|
| `DESIGN.md` | The full Phase 1 design and methodology | no |
| `sim/` | Deterministic DuckDB world: schema, seeded ledger, five incident injectors, reconciliation measure | no |
| `tools/` | The five bounded agent tools and their safety rails; `SECURITY.md` documents the SQL guard's honest limits | no |
| `grade/` | Independent 100-point grader that re-derives post-repair state itself; it never trusts the agent's claim | no |
| `agent/baseline.py` | The strong deterministic SQL baseline arm | no |
| `spec/` | The frozen, unseen test set, its validation, and the reproducible `benchmark_sha256` | no |
| `agent/gemini_client.py`, `loop.py`, `schemas.py` | The real Gemini adapter and multi-turn tool loop | calls API |
| `agent/run_live.py` | The paid runner: ledger, spending guard, smoke/pilot/test modes | calls API |
| `agent/inspect_run.py` | Offline tool to re-score and inspect saved runs with no new calls | no |
| `agent/windows/` | PowerShell scripts to run it on Windows (setup, key, smoke, pilot) | mixed |
| `REPORT.md` | The full technical report with results, caveats and limitations | no |

## Key results

**Deterministic SQL baseline: 100/100 on all 15 cases** (5 dev + 10 frozen test). Correct
investigation is achievable without an LLM.

**Both models (development set, 3 pilots): never above 16/100.** Two failure modes:
1. Incomplete investigations — often no verdict submitted, even with the final turns restricted to
   only the verdict tool (Argon especially: more incompletes and a timeout).
2. Fabricated, ungrounded verdicts when completed — invented keys like `INV-2024-001` where the real
   keys are `100/1000/2026/4820000100/000001/0L`; zero overlap with the true keys on every completed
   case; frequent root-cause misclassification; null remediations. The grader correctly scored these
   near zero and was not loosened to accept fabrication.

**Cost/latency:** Argon ~3-4x Flash per case and slower, with no accuracy benefit.

## Honest limitations

* Single trial, five development cases, three pilots, ~$1.55 spend. No statistical significance and
  no claim that one model is better than the other.
* The frozen 10-case test set was not run against the models (sealed).
* Synthetic data; a young agent harness (completion was partly harness-limited — see `REPORT.md`
  Section 6). The fabrication finding is about verdict content and is independent of the completion
  mechanism.

## Reproduce

Offline (free):
```bash
pip install duckdb pytest
python -m pytest experiments/finance-reconciliation/tests -q          # 191 tests
python experiments/finance-reconciliation/agent/run_baseline_dev.py    # baseline 100/100
python experiments/finance-reconciliation/spec/run_phase6.py           # test set + frozen hash
```

Live (paid, Windows): see [`agent/windows/README.md`](agent/windows/README.md). Conservative client
cap, a Cloud Billing alert budget set first, and a typed confirmation before any call. A $10
client-side allowance and billing alerts are not a guaranteed final bill.

## On publishing

This is worth publishing **as a methods-and-honesty piece**, not as "Flash vs Argon: which wins".
The valuable, reusable contribution is: an offline, deterministic, independently graded benchmark for
verified agentic action, plus a candid negative result (a strong SQL baseline beats two frontier
models that fabricate record identifiers). Frame it as a case study, state the single-trial and
synthetic-data limits up front, and do not claim a model ranking the data cannot support. See
`REPORT.md` Sections 6-8.
