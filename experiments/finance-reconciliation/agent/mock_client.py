"""Mock Gemini client for offline validation of the tool loop (Phase 7). NO API calls.

Returns responses in the loop's normalised shape. It can play:
  * a competent investigator that queries the layers and submits a correct verdict
  * each failure mode: timeout, incomplete (thinking-budget exhausted), malformed/no-call

It reads the world (as a real agent would, through tool results fed back) to decide its next
call, but it NEVER reads the answer key -- it reasons from the symptom and the layer reads, the
same evidence a model would have. This validates the loop mechanics, not model quality.
"""
from __future__ import annotations

from sim import reconcile


class MockClient:
    def __init__(self, con, *, mode: str = "competent", usage_per_turn=None):
        self.con = con
        self.mode = mode
        self.usage = usage_per_turn or {"input_tokens": 1500, "output_tokens": 120,
                                        "thinking_tokens": 300}
        self._plan = None
        self._i = 0

    def create(self, messages, tools, system):
        # failure modes short-circuit immediately
        if self.mode == "timeout":
            return {"function_call": None, "verdict": None, "usage": self.usage,
                    "status": "timeout", "error": "no response within deadline"}
        if self.mode == "incomplete":
            # thinking-budget exhausted: tokens spent, no usable action
            return {"function_call": None, "verdict": None,
                    "usage": {"input_tokens": 1500, "output_tokens": 2, "thinking_tokens": 7000},
                    "status": "incomplete", "error": None}
        if self.mode == "no_call":
            return {"function_call": None, "verdict": None, "usage": self.usage,
                    "status": "ok", "error": None}   # stalls (prose, no tool call)

        if self._plan is None:
            self._plan = self._build_plan()
        if self._i >= len(self._plan):
            # safety: if the loop runs past the plan, stall
            return {"function_call": None, "verdict": None, "usage": self.usage,
                    "status": "ok", "error": None}
        call = self._plan[self._i]
        self._i += 1
        return {"function_call": call, "verdict": (call["args"] if call["name"].startswith("submit") else None),
                "usage": self.usage, "status": "ok", "error": None}

    def _build_plan(self):
        """A competent, deterministic investigation: read layers, then submit a correct verdict.
        Uses the reconcile helpers (as evidence an agent would gather via tool calls), not the key."""
        con = self.con
        missing = [list(map(str, k)) for k in reconcile.missing_at_mart(con)]
        dup = [list(map(str, k)) for k in reconcile.duplicated_at_mart(con)]
        amt = [list(map(str, k[:6])) for k in reconcile.amount_mismatches(con)]

        plan = [
            {"name": "run_sql", "args": {"tier": "metadata", "query": "SELECT * FROM recon_cutoff"}},
            {"name": "run_sql", "args": {"tier": "source",
                "query": "SELECT belnr FROM s4_acdoca WHERE racct='0001400000'"}},
            {"name": "run_sql", "args": {"tier": "mart", "query": "SELECT belnr FROM dbx_ar_mart"}},
            {"name": "run_sql", "args": {"tier": "mart",
                "query": "SELECT belnr, count(*) FROM dbx_ar_mart GROUP BY belnr HAVING count(*)>1"}},
        ]
        affected, root_causes, remediations = [], [], []
        if missing and dup:
            root_causes = [{"incident_class": "compound", "layer": "L4"},
                           {"incident_class": "compound", "layer": "L4"}]
            remediations = [{"action_type": "backfill_missing",
                             "parameters": {"business_keys": ["/".join(k) for k in missing]}},
                            {"action_type": "dedupe_target"}]
            affected = ["/".join(k) for k in missing] + ["/".join(k) for k in dup]
        elif missing:
            plan.append({"name": "run_sql", "args": {"tier": "cdc", "query": "SELECT belnr FROM cdc_acdoca"}})
            plan.append({"name": "run_sql", "args": {"tier": "share", "query": "SELECT belnr FROM share_ar_items"}})
            cdc = {r[0] for r in con.execute("SELECT belnr FROM cdc_acdoca").fetchall()}
            miss_belnr = {k[3] for k in missing}
            if miss_belnr - cdc:   # absent at cdc -> skip
                root_causes = [{"incident_class": "missing_cdc_delta", "layer": "L1"}]
                remediations = [{"action_type": "reextract_batch",
                                 "parameters": {"business_keys": ["/".join(k) for k in missing]}}]
            else:                  # present at share, dropped at mart -> lossy join
                root_causes = [{"incident_class": "lossy_join", "layer": "L4"}]
                remediations = [{"action_type": "refresh_customer_snapshot"}]
            affected = ["/".join(k) for k in missing]
        elif dup:
            root_causes = [{"incident_class": "duplicate_replay", "layer": "L4"}]
            remediations = [{"action_type": "dedupe_target"}]
            affected = ["/".join(k) for k in dup]
        elif amt:
            plan.append({"name": "inspect_transformation_logic", "args": {"view_name": "dsp_ar_items"}})
            plan.append({"name": "run_sql", "args": {"tier": "source",
                "query": "SELECT belnr, ksl FROM s4_acdoca WHERE waers <> 'USD'"}})
            root_causes = [{"incident_class": "currency_basis", "layer": "L2"}]
            remediations = [{"action_type": "fix_transform"}]
            affected = ["/".join(k) for k in amt]

        verdict = {
            "root_causes": root_causes,
            "affected_business_keys": sorted(affected),
            "evidence": [{"tool": "run_sql", "summary": "layer comparison", "ref": "call #2"},
                         {"tool": "run_sql", "summary": "duplicate check", "ref": "call #4"}],
            "proposed_remediations": remediations,
            "verification": {"discrepancy_after": 0.0, "invariants_ok": True},
        }
        plan.append({"name": "submit_investigation_verdict", "args": verdict})
        return plan
