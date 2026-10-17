# Experiment 3 technical report: autonomous finance reconciliation with Gemini 3.8 Flash and Gemini 4 Argon

**Run dates:** 2026-10-16 to 2026-10-17. Offline apparatus built and frozen; live model pilots run
from a Windows PC against the Gemini Interactions API. All costs are usage-based estimates, not
billed amounts. Raw data, scoring code and offline tests are in this folder.

**Summary.** A strong deterministic SQL baseline solves all 15 synthetic reconciliation incidents
(5 development + 10 frozen test) with a perfect score. Given the identical five bounded tools and
an independent grader, Gemini 3.8 Flash and Gemini 4 Argon investigated the discrepancies (querying
the right data layers) but did not complete correct structured diagnoses: across three development
pilots neither model scored above 16 of 100 on any case. When forced to submit a verdict, both
models frequently **fabricated plausible-looking business keys that do not exist in the data** and
misclassified the root cause. Flash was roughly three to four times cheaper and faster per case than
Argon, with no accuracy advantage to Argon. This is a single-trial case study on synthetic data, not
a statistically powered benchmark; it should be read as a methods demonstration and a candid negative
result, not as a verdict that one model is better than the other.

---

## 1. Business problem and scenario

Accounts Receivable in SAP S/4HANA does not match a downstream Databricks finance mart, and every
pipeline monitor shows SUCCESS. The data path is S/4HANA -> CDC -> SAP Datasphere data product ->
Delta share -> Databricks mart. An investigator must find the root cause, the exact affected
accounting records, and a safe remediation, then verify that the repair reconciles the data without
new damage. The task is multistep and rewards grounding each conclusion in evidence from the actual
records, which is the property this experiment probes: not retrieval (Experiment 1) or governed
reasoning with all evidence supplied (Experiment 2), but **verified action** — gathering evidence and
turning it into a correct, checkable diagnosis.

Everything is synthetic. No real financial data, no real SAP, BDC or Databricks connection.

## 2. Design and method

The apparatus is fully offline and deterministic; only the model arms make paid calls.

| Element | Choice |
|---|---|
| World | A seeded DuckDB simulation of all layers (S/4HANA ACDOCA-style ledger, CDC, Datasphere view, Delta share, Databricks mart) with a three-clock CDC model (source commit, CDC capture, downstream ingestion) and a fixed reconciliation scope (client, company code, ledger, period, posting-date cutoff, group currency) |
| Measure | Period AR movement: the signed sum of group-currency amounts over the in-scope lines; the source is authoritative |
| Incidents | Five classes: missing CDC batch, duplicate downstream replay, wrong currency basis, lossy downstream join, and a compound of two offsetting defects; each produces an exact expected discrepancy |
| Tools | Five bounded tools given identically to both models: `run_sql` (read-only, tier-isolated, row-capped), `get_pipeline_metadata`, `inspect_transformation_logic`, `simulate_remediation` (isolated overlay), `submit_investigation_verdict` |
| Grader | Independent 100-point scorer that re-derives the post-remediation state on its own overlay; it never trusts the agent's success claim. Dimensions: root cause 30, affected keys 20 (F1), evidence 15, safe remediation 15, independent verification 20. Unsafe actions, overclaims and premature termination are tracked separately |
| Baseline | A strong deterministic SQL battery driven through the same bounded tools, run to completion |
| Benchmark | 5 development incidents and 10 frozen, unseen test incidents (distinct seeds, magnitudes, key ranges), frozen with a reproducible `benchmark_sha256` |
| Model arms | gemini-3.8-flash and gemini-4-argon, medium thinking, identical tools/prompt/limits; multi-turn function calling via the Interactions API |
| Spending controls | Shared ledger, per-case worst-case reservation, hard `--cap`, per-call token and turn limits, per-call timeout, no retries; estimated spend kept separate from billing |

The offline apparatus is verified by 191 automated tests; the frozen benchmark hash is
`7b797b2c7f6c1f4ba856cceacf329c49ca4661bb77e6e55dc9428e570c18aed6`.

## 3. Deterministic baseline result

The strong SQL baseline scores **100/100 on all five development incidents and all ten frozen test
incidents.** It reconciles totals across layers, finds missing records by composite-key anti-join,
detects duplicates with signed impact, identifies per-record currency drift, distinguishes a skipped
CDC batch from a benign pending delta, localises the layer where divergence first appears, and
detects both defects in the compound case. Its proposed remediations independently reconcile the data
on the grader's own overlay.

**Reading:** on this task, as constructed, correct investigation is fully achievable without an LLM.
Per the design's calibration rule, this is reported as-is; no case was weakened and the baseline was
not crippled to manufacture a model advantage. A legitimate consequence is that the model comparison
may show little room above a strong baseline — but, as Section 4 shows, the models did not reach the
baseline; they fell well below it.

## 4. Live model results (development pilots)

Three development pilots were run (2026-10-16 to 2026-10-17) while the agent loop and the live
Interactions-API integration were brought up (see Section 6). All figures are from the live runs on
the five development incidents, both models, medium thinking, one trial per model per case.
Estimated spend across all live activity: about **$1.55**.

**Scores never exceeded 16/100 for either model on any case, in any pilot.** Representative final
pilot (`results/runs/pilot_20261017_010947.jsonl`):

| Case | Flash status / score | Argon status / score |
|---|---|---|
| missing CDC batch | incomplete / 8 | timeout / 0 |
| duplicate replay | completed / 0 | incomplete / 0 |
| currency basis | completed / 4 | completed / 15 |
| lossy join | completed / 0 | incomplete / 0 |
| compound | completed / 0 | incomplete / 0 |

Two failure modes dominate, and they are the substantive finding:

1. **Incomplete investigations.** Even with the final turns restricted to only the verdict tool,
   both models often did not submit a usable verdict; Argon especially (three incomplete and one
   timeout in the final pilot). Completion was unreliable across all three pilots.

2. **Fabricated, ungrounded verdicts when they did complete.** Inspecting the saved verdicts
   (`agent/inspect_run.py`) shows the models reported business keys that **do not exist in the
   data**: invented identifiers like `INV-2024-001`, `1010-0100000042-2024-001` or
   `1000-1400000012-2024`, where the real composite keys are of the form
   `100/1000/2026/4820000100/000001/0L`. Overlap with the true affected keys was **zero on every
   completed case.** The models also frequently misclassified the root-cause class (for example
   calling a duplicate replay a lossy join, or a currency-basis defect a missing CDC delta) and
   proposed null remediations. The independent grader therefore scored these near zero, correctly:
   a fabricated key is not a correct answer, and the grader was not loosened to accept one.

**On the evidence dimension** both models earned partial credit on several cases (they did run the
right kinds of queries), which confirms they investigated; the failure is in turning that
investigation into a grounded, correct, structured verdict.

## 5. Cost, latency and behaviour

Consistent across pilots: Argon cost roughly **three to four times** Flash per case and ran
substantially slower (for example about 215 s versus about 55 s on one case), with much higher token
use, and no accuracy benefit. On this task, the cheaper model was not worse at the thing that
mattered, because neither model succeeded.

| | Flash, medium | Argon, medium |
|---|---|---|
| Cost per case (observed) | ~$0.02-0.04 | ~$0.09-0.17 |
| Latency per case (observed) | tens of seconds | up to several minutes |
| Completion | unreliable | less reliable (more incompletes/timeouts) |
| Best score on any case | 16 | 15 |

## 6. Harness notes and honest caveats

Bringing up the live integration required several fixes, each committed and, where possible,
validated offline first:

* The Interactions API multi-turn shape: a function_call is a response step, not an input item;
  follow-up turns send only the new `function_result` with `previous_interaction_id`, re-sending
  tools and system instruction. An earlier full-transcript attempt was rejected by the server with a
  `CreateAgentInteraction.agent` validation error.
* Completion: a prose nudge did not reliably make models submit; restricting the final turns to only
  the verdict tool did make them submit, validated offline against a mock that reproduces the
  observed behaviour. This is why Section 4's completions exist at all.
* Verdict capture: the first pilots did not save the submitted verdict, so low scores could not be
  diagnosed; the runner now saves verdicts and a run inspector re-scores offline with no new calls.

These notes matter for interpretation. A skeptic can reasonably argue that better scaffolding or more
turns would raise the scores, and that is partly true — getting a model to emit a grounded structured
verdict at the end of a long tool-use loop is itself hard, which is part of the finding rather than a
defect to apologise for. The limitations are stated plainly:

* **Single trial, five development cases, three pilots, about $1.55 of spend.** No statistical
  significance; no claim that one model is better than the other. The frozen 10-case test set was
  **not** run against the models (sealed), so all live numbers are development-set only.
* **Synthetic data and a young harness.** This is a controlled probe of verified agentic action, not
  production evidence.
* **Completion was partly harness-limited.** The forcing mechanism is a blunt instrument; a different
  agent design might complete more often. The fabrication finding, however, is about the content of
  the verdicts the models did submit, and is independent of the completion mechanism.

## 7. Did the more expensive model justify its cost?

On this task: **no.** Argon cost three to four times more than Flash and was slower, while neither
model produced correct diagnoses and Argon completed less often. There is no measured dimension on
which Argon's additional cost bought additional value here. This is a single-trial observation on
synthetic data, not a general claim about the models.

## 8. Combined reading across Experiments 1 to 3

* Experiment 1 (retrieval): the cheaper model was sufficient; errors coincided with missing retrieved
  evidence.
* Experiment 2 (governed reasoning, all evidence supplied): both models were perfect at medium
  thinking; a ceiling prevented ranking.
* Experiment 3 (verified action): a strong SQL baseline solves the task, but both models fail to turn
  investigation into grounded, correct, structured verdicts — frequently not completing, and
  fabricating record identifiers when they do. The independent grader's refusal to accept fabricated
  keys is what makes this measurable.

The arc is consistent: as the task moves from retrieving evidence, to reasoning over supplied
evidence, to acting on self-gathered evidence and verifying the action, the gap between "looks like
work" and "correct, grounded, verifiable result" widens — and that last gap is where current models,
in this harness, fell short of a deterministic baseline.

## 9. Reproducing

Offline (free): `pip install duckdb pytest`; `python -m pytest experiments/finance-reconciliation/tests -q`
(191 tests); `python experiments/finance-reconciliation/agent/run_baseline_dev.py`;
`python experiments/finance-reconciliation/spec/run_phase6.py` (test set + frozen hash).

Live (paid, Windows): see `agent/windows/README.md`. Set a key with `set-key.ps1`, dry-run the
smoke test, then the pilot, under a conservative client cap and a Cloud Billing alert budget.

Raw run files and the spending ledger are under `results/` (gitignored by default).
