"""Answer key for the grader (DESIGN.md 6.1). Lives in grade/ ONLY.

The agent process must never import this module (enforced by tools/isolation.py). The key
for an incident is derived directly from the injector's returned truth, so it cannot drift
from what the simulator actually did.

A key entry holds, per incident:
  incident_class     : the canonical class name
  root_cause_layers  : list of layers (e.g. ["L4", "L4"] for compound)
  affected_keys      : {"missing": [...], "duplicated": [...], "amount_mismatch": [...]}
  safe_remediations  : the set of acceptable action_types
  required_evidence  : evidence signatures a sound investigation must have produced
  expected_discrepancy
"""
from __future__ import annotations

# Evidence signatures expected per incident class. Each signature is a predicate the grader
# checks against the agent's tool-call log (grade/scorer.py).
REQUIRED_EVIDENCE = {
    "missing_cdc_delta": ["anti_join_missing", "cdc_vs_source"],
    "duplicate_replay":  ["duplicate_check"],
    "currency_basis":    ["inspect_transform", "amount_compare"],
    "lossy_join":        ["anti_join_missing", "share_vs_mart"],
    "compound":          ["anti_join_missing", "duplicate_check"],
}


def build_key(incident_name: str) -> dict:
    """Build the frozen key for one incident by running its injector and reading the truth.

    This imports the simulator (allowed inside grade/) but never exposes the result to the
    agent. In the real harness this is serialized to spec/key.json by a check_cases step and
    the agent process cannot read it.
    """
    from sim import injectors
    con, truth = injectors.build_incident(incident_name)
    cls = truth["incident"]
    key = {
        "incident_name": incident_name,
        "incident_class": cls,
        "root_cause_layers": truth["root_cause_layer"],
        "affected_keys": {k: [list(map(str, bk)) for bk in v]
                          for k, v in truth["affected_keys"].items()},
        "safe_remediations": set(truth["safe_remediations"]),
        "required_evidence": REQUIRED_EVIDENCE.get(cls, []),
        "expected_discrepancy": truth.get("expected_discrepancy"),
    }
    return con, key


def all_affected_keys(key: dict) -> set[str]:
    """Flatten every affected business key (as 'a/b/c/d/e/f' strings) for P/R scoring."""
    out = set()
    for keys in key["affected_keys"].values():
        for bk in keys:
            out.add("/".join(bk))
    return out
