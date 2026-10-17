# Phase 3: agent tools and safety rails

The five tools an investigating agent is allowed to call, plus the isolation guard. Offline,
deterministic, no Gemini, no API calls. Both model arms (Phase 8) receive this identical surface.

## Tools (DESIGN.md section 5)

| Tool | What it does | Key guards |
|---|---|---|
| `run_sql(tier, query)` | read-only SQL against one layer | single SELECT/WITH only; no DDL/DML/PRAGMA/ATTACH/COPY; no filesystem functions; tier isolation; row + cell caps; bounded pagination |
| `get_pipeline_metadata(pipeline_id)` | config + run history for a pipeline | enum pipelines only; exposes the real config (idempotent flag, join type, watermark), no fault label |
| `inspect_transformation_logic(view_name)` | a view/load definition + mapping | enum views only; shows the real SQL (the evidence) with no `-- BUG`/`wrong`/`FIXME` annotation |
| `simulate_remediation(action_type, parameters)` | apply a fix to an **isolated clone**, return before/after | enum actions only; raw SQL or base-targeting is refused and flagged unsafe; base state is re-measured and asserted unchanged after every call |
| `submit_investigation_verdict(verdict)` | the final structured diagnosis | schema-validated; the `verification` block is recorded but **not trusted** (the Phase 4 grader re-derives it) |

`tools/isolation.py` enforces DESIGN.md 6.1.1: the agent process cannot import `grade/` or
`spec.key`, and the agent-visible world carries no defect-label columns or tables.

The `Tools` facade binds the tools to one world connection and one call log, and exposes
`stats()` (tool-call count, repeated SQL, unsafe attempts, errors) for the Phase 6 scorer.

## What the rails prevent

- No writes, ever: every mutating or DDL statement is refused; `simulate_remediation` works on
  a scratch copy and the base is asserted identical before and after.
- No cross-layer peeking by mistake: a query naming another tier's table is a `tier_violation`.
- No filesystem or attach escape: `read_csv`, `glob`, `ATTACH`, `COPY` and friends are blocked.
- No answer leakage: the tiers map only to the simulated world, never to the key or grader;
  tool outputs carry evidence (the wrong-FX SQL, the `idempotent=false` flag) but no label saying
  "this is the planted defect".

## Reproduce (offline, free)

```bash
python -m pytest experiments/finance-reconciliation/tests/test_tools.py -q   # 34 tool tests
python -m pytest experiments/finance-reconciliation/tests -q                 # 47 total (Phase 2 + 3)
```

## Not in Phase 3

No Gemini agent, no agent loop, no grader, no answer-key file, no API calls. Those are Phases 4
to 8 in `DESIGN.md`, gated on approval. The tools are the interface; nothing drives them yet
except the tests.
