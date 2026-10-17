# Phase 7: Gemini capability probe

Validates the mechanics the paid Flash-vs-Argon run depends on, and estimates its cost — with
**zero API calls** in this environment, because no Gemini key is present here (and I will not add
one; that is your billing). The one check that genuinely needs the live API is called out below as
a gated step for you to run.

## Environment reality (stated honestly)

- `GEMINI_API_KEY` is **not set** in this environment and the `google-genai` SDK is **not
  installed** (the same missing dependency that makes Experiment 1's live tests skip here).
- Therefore no live Gemini call was made. This satisfies "minimum API requests" in the strongest
  way: the minimum is zero, and everything below was validated against a deterministic **mock
  client** that returns Gemini's response shape (function calls, usage with thinking tokens, and
  each failure mode).

## 1. Shared schema + multistep loop (validated, offline)

- `agent/schemas.py` holds ONE set of function declarations and ONE system prompt, given
  identically to both arms. The only per-arm variables are the model id and thinking level — the
  fairness invariant.
- `agent/loop.py` runs the multistep loop: the model emits a function call → the loop dispatches
  it to the bounded `Tools` → the result is fed back → repeat until `submit_investigation_verdict`
  or `max_turns` (15). Model-agnostic: Flash, Argon, and the mock all drive the same loop.
- The competent mock completes all 10 frozen test cases in 5-7 turns and the grader scores each
  **100/100** — confirming the schema, loop, dispatch, and verdict handling all work together.

## 2. Verdict handling, usage + thinking-token accounting (validated)

- Structured verdicts parse and score through the real grader.
- Per-turn `input` / `output` / `thinking` tokens accumulate into correct totals; thinking tokens
  are tracked separately (they bill at the output rate).

## 3. Model ids, API compatibility, current pricing (confirmed from the repo + public sources)

- Model ids and API shape come from the repo's own working Experiment 2 runner: `gemini-4-argon`
  and `gemini-3.8-flash`, called via `client.interactions.create(model, input, system_instruction,
  generation_config={thinking_level, max_output_tokens}, response_format=...)`.
- Pricing reconfirmed against public sources in Phase 7 and matches the repo table
  (`src/argon_lab/pricing.py`, checked 2026-10-13):

  | Model | Input $/1M | Output (incl. thinking) $/1M | Window |
  |---|---|---|---|
  | gemini-4-argon | 2.00 (promo) → 4.00 | 10.00 (promo) → 20.00 | promo "for at least one month" from 2026-09-30 |
  | gemini-3.8-flash | 0.75 → 1.50 | 3.75 → 7.50 | — |

  Honest caveat: one public source noted Argon returned 404 (not purchasable) on 2026-10-01; the
  repo's Experiment 2 shows it was callable by 2026-10-16. I cannot verify its live status from
  here without a key — your repo is the authoritative evidence it works.

## 4. Timeout / retry / incomplete handling (validated, offline)

- **timeout** → status `timeout`, no verdict, usage still recorded.
- **incomplete** (thinking-budget exhausted: 7000 thinking / 2 output tokens) → status
  `incomplete`, no verdict — the same signature Experiment 2 saw with Argon-high.
- **no-call stall** → status `incomplete`.
- **never-submits spinner** → stops at `max_turns`, does not loop forever.
- Retry/deadline policy is inherited from the Experiment 2 runner pattern (no client retries, a
  hard per-call deadline, worst-case charging for abandoned calls).

## 5. Conservative cost estimate (`agent/cost_estimate.py`)

Verified promo pricing, medium thinking, a **1.5× safety margin** on placeholder token figures:

| Scope | Estimate |
|---|---|
| **Pilot** — 5 dev cases × 2 arms × 1 trial | **~$0.72** |
| Full benchmark — 10 frozen test cases × 2 arms × 1 trial | ~$1.44 |
| Variance probe — 1 case × 2 arms × 3 trials | ~$0.42 |

Token-per-case figures are **placeholders** until a real pilot measures them. The runner's
per-call worst-case reservation + hard `--cap` bound actual spend; a Cloud Billing alert budget is
early warning, **not** a hard stop (DESIGN.md 9.3).

## 6. Runner isolation (validated)

- The schema exposes exactly the five controlled tools; the loop dispatches only to them.
- The loop source references no `grade/`, `spec.key`, `frozen_testset`, injector, or answer data.
- The system prompt is symptom-only (no class names, keys, or labels).
- The frozen Phase 6 benchmark is **unchanged** (hash verified identical).

## 7. Frozen cases / scoring / hash preserved

`freeze.verify_frozen()` returns match; `benchmark_sha256` unchanged. Phase 7 added only the
agent-loop mechanics and the cost tooling; it modified nothing under `spec/` or `grade/`.

## The one gated step that needs the live API (for you to run)

A single real call per arm to confirm the live API accepts the shared schema and returns the
expected shape. This is the only thing the mock cannot prove. It should run under your key with a
tiny cap, as part of the pilot below — not separately.

## Recommended smallest fair pilot

**5 dev cases × {Flash-medium, Argon-medium} × 1 trial = 10 calls, ~$0.72 estimated.**

Rationale: one instance of each incident class, identical tools/prompt/limits per arm, medium
thinking only (high is out of the initial benchmark), one trial (descriptive). This is the minimum
that (a) confirms the live API end-to-end for both arms and (b) gives a first real token/cost
measurement to replace the placeholders — before committing to the full frozen test set.

Guardrails for the pilot: client `--cap $2` (well above the $0.72 estimate, below any surprise),
a Cloud Billing alert budget set first, dev-only (the frozen test set stays sealed), and a typed
confirmation before any call.

**Explicit approval required before any paid call. Nothing runs until you say so.**
