# Phase 5: deterministic SQL reconciliation baseline

The strong, realistic SQL baseline arm (DESIGN.md 6.6). Offline, deterministic, no Gemini, no
API calls. It drives the **same bounded `Tools`** that Flash and Argon will later receive, never
reads the answer key or injector manifest, and emits a verdict in the **same schema** as the model
arms, scored by the Phase 4 grader.

## What it does (the fixed battery)

A competent enterprise data engineer's reconciliation battery, run to completion (it does not stop
at the first finding):

1. Read the scope from `recon_cutoff` (period, both snapshot boundaries).
2. Totals: source period-movement vs target, from each tier.
3. Layer walk: presence sets at source, cdc, share, mart — to localise where records first diverge.
4. Missing: `source_keys - mart_keys`; then split into missing-at-cdc (CDC family) vs
   present-at-share-dropped-at-mart (downstream join family).
5. Skip vs lag: for missing-at-cdc keys, confirm `cpudt <= watermark` (a true skip) vs a benign
   pending delta (`cpudt > watermark`).
6. Duplicates: `GROUP BY business key HAVING count(*) > 1` at the mart, with **signed** impact.
7. Currency: when counts match, compare source `ksl` vs mart `amount_usd` per key; inspect the L2
   transform definition to confirm the basis.
8. Compound: because the whole battery runs, it detects both a missing set and a duplicate set.
9. Emit a verdict (root causes, affected keys, evidence, remediations) in the agent schema.

## Result on the five development scenarios

```
incident1_skipped_cdc        100/100   missing_cdc_delta/L1   (skip confirmed, +450K)
incident2_duplicate_replay   100/100   duplicate_replay/L4    (2 dups, -140K signed impact)
incident3_currency_basis     100/100   currency_basis/L2      (10 fx rows drift, counts match)
incident4_lossy_join         100/100   lossy_join/L4          (present at share, dropped at mart, +120K)
incident5_compound           100/100   compound/L4 x2         (3 missing + 2 dup, net +310K)
MEAN: 100.0/100
```

Every diagnosis has the correct class and layer, the exact affected keys, safe remediations, and
**repairs that independently reconcile** (the grader's own overlay closes each discrepancy with no
residual invariant breach). No unsafe attempts, no tier errors.

Reproduce: `python experiments/finance-reconciliation/agent/run_baseline_dev.py`

## The honest finding (read this)

**The strong deterministic baseline solves all five development incidents.** Per DESIGN.md 7.2
this is a real, reportable result: on these cases, straightforward SQL is sufficient and an LLM may
add little. It is **not** a reason to weaken any case or cripple the baseline to manufacture a
model advantage — doing so is explicitly forbidden by the design. The honest reading, if the frozen
test set behaves the same way, is "both models and a strong SQL baseline are sufficient for this
task", which the experiment must be willing to report.

What this does **not** establish: that a model is unnecessary in the field. The baseline is a
*fixed* hypothesis set written with full knowledge of the five incident classes; a model must form
hypotheses adaptively against incidents it is not told the class of. The two answer different
questions and Phase 9 keeps them separate. The calibration gate (Phase 6) is where difficulty and
separability are assessed honestly — against an independent mutation-depth criterion, not against
the baseline's score.

## Isolation and safety (preserved)

- The baseline uses only the five bounded tools; it cannot import `grade/` or `spec/` (the agent
  path excludes them; `tools/isolation.py`).
- The `run_sql` guard's documented limits stand unchanged (`tools/SECURITY.md`): it is
  defence-in-depth over synthetic, local, read-only data, not a universally secure SQL firewall.
- The eventual model launcher must expose only these controlled tools and keep the grading files
  (`grade/`, `spec/`) off the agent's path — the same contract the baseline already honours.

## Not in Phase 5

No Gemini agent, no model arm, no API calls, no calibration gate (Phase 6), no frozen test set.
The baseline runs on the five dev scenarios only.
