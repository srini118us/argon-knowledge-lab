# Running Experiment 3 live on Windows (PowerShell)

Step-by-step to run the Flash-vs-Argon comparison from your own PC. All paid steps are gated
and ask for a typed confirmation. **Nothing here runs from Claude's environment** — you run it.

## Key safety (read first)

- **Never paste your API key into Claude, ChatGPT, GitHub, or any chat.** Only into the local
  `set-key.ps1` secure prompt, on your machine.
- The key is set as a session environment variable only. No script prints it, writes it to a
  file, or stores it in results/ledger. `set-key.ps1` confirms by showing its *length*, not value.
- `results/` is gitignored; raw runs and the ledger stay local.

## 0. Apply the patch (if not already applied)

See the cumulative patch instructions. Then from the repo root (`argon-knowledge-lab\`):

## 1. One-time setup (offline, free)

```powershell
.\experiments\finance-reconciliation\agent\windows\setup.ps1
```

Creates `.venv`, installs `duckdb`, `pytest`, `google-genai>=2.30.1`, and runs the offline test
suite. Must end green before continuing.

## 2. Set your key for this session (offline, free)

```powershell
.\experiments\finance-reconciliation\agent\windows\set-key.ps1
```

Paste your key at the hidden prompt. It applies only to this PowerShell window.

## 3. Live smoke test (PAID ~$0.14, capped $1)

Preflight first (free), then the real thing:

```powershell
.\experiments\finance-reconciliation\agent\windows\smoke.ps1 -DryRun
.\experiments\finance-reconciliation\agent\windows\smoke.ps1
```

One short function-call round trip per model. Confirms the live API accepts the shared schema,
parses tool calls, and reports usage. **Stop if either model fails.**

## 4. Development pilot (PAID ~$0.72, capped $2) — after the smoke test passes

```powershell
.\experiments\finance-reconciliation\agent\windows\pilot.ps1 -DryRun
.\experiments\finance-reconciliation\agent\windows\pilot.ps1
```

5 dev cases x 2 models x 1 trial, scored by the independent grader. The frozen test set stays
sealed. Review the results, then share them for approval before the frozen test run.

## 5. Review results and cost

```powershell
# the newest run file and the shared ledger (estimated costs)
Get-ChildItem experiments\finance-reconciliation\results\runs\ | Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content experiments\finance-reconciliation\results\ledger.jsonl
```

Costs in the rows/ledger are **estimated** from usage x published prices. Reconcile against your
Google Cloud billing for the actual charge.

## 6. Frozen benchmark (Phase 8C) — ONLY after you approve the pilot

```powershell
.\.venv\Scripts\python.exe experiments\finance-reconciliation\spec\freeze.py   # verify hash first
.\.venv\Scripts\python.exe -m agent.run_live --mode test --dry-run
.\.venv\Scripts\python.exe -m agent.run_live --mode test --cap 3 --go
```

Verifies the frozen benchmark hash before running. **Note:** the 10-case test worst-case
(~$19.80) exceeds the $10 allowance; with `--cap 3` the runner stops when the reservation would
cross the cap, so a single `--cap 3` run may not finish all cases. Run in approved batches or
raise the cap toward (but not past) $10 with your eyes on the ledger. Do not run a variance
experiment unless separately approved.

## Spending controls (what actually protects you)

1. **Client `--cap`** + per-case worst-case reservation: the runner stops before the ledger +
   next case's worst case would exceed the cap. Primary control.
2. **Per-call** `max_output_tokens` (8k, includes thinking), **per-case** `max_turns` (15),
   **per-call** SDK timeout (120s), **no retries**.
3. **Post-call check**: if a case's actual cost exceeds its reservation, the run stops.
4. **A Google Cloud Billing budget with alert thresholds** — set this in the console first. It is
   early warning, **NOT a hard stop**; Google keeps serving past a budget.
5. **Billing reconciliation** after: estimated spend is never claimed equal to the actual bill.

**No single control guarantees an exact final bill.** The $10 is a client-side allowance and a
conservative target, not a Google-enforced ceiling.
