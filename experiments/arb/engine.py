"""Deterministic Architecture Review Board decision engine: computes the answer key.

The engine applies the rules in spec/policy.json to a structured proposal. Models never see
these structures; they see the policy pack (pack/*.md) and a prose rendering of each proposal.

Decision procedure (stated in prose in pack/ARB-CHARTER.md):
  * violations  = failing rules not covered by an active, in scope waiver
  * conditions  = rules covered by a waiver, plus CF-1 when go live falls in a freeze window
  * decision    = reject if any violation, else approve_with_conditions if any condition, else approve
  * on reject, conditions are not listed

MUTATIONS model plausible reasoning mistakes. check_cases.py uses them to prove each case needs
several distinct reasoning steps: a case is only accepted if enough mutations change its outcome.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

SPEC = Path(__file__).resolve().parent / "spec"
RANK = {"C1": 1, "C2": 2, "C3": 3}

# Mutations that skip a step (a model that forgets a check).
SKIP = ["classify_low", "dpa", "c3_ban", "transport", "retention", "annex", "encryption",
        "residency", "zone", "gateway", "freeze", "waivers", "waiver_dates", "waiver_scope", "superseded"]
# Mutations that over apply a rule (a model that is stricter than the policy).
OVER = ["classify_high", "annex_all", "residency_all", "freeze_inclusive_day_after", "waiver_ignore_valid"]
MUTATIONS = SKIP + OVER


def load_policy() -> dict:
    return json.loads((SPEC / "policy.json").read_text(encoding="utf-8"))


def _d(s: str) -> date:
    return date.fromisoformat(s)


def evaluate(case: dict, policy: dict | None = None, mutation: str | None = None) -> dict:
    p = policy or load_policy()
    m = mutation
    vendor = p["vendors"][case["vendor"]]
    subjects = set(case["data_subjects"])
    go_live = _d(case["go_live"])

    # Step 1: classify
    if m == "classify_low":
        cls = "C1"
    else:
        cls = max((p["classes"][f] for f in case["fields"]), key=RANK.get)
        if m == "classify_high" and RANK[cls] < 2:
            cls = "C2"
    c2 = RANK[cls] >= 2

    failing: list[str] = []
    rules = p["rules"]
    old = p["superseded"]["SEC-POL@v2"] if m == "superseded" else {}

    if m != "dpa" and cls not in vendor["dpa_classes"]:
        failing.append("SP-2.1")
    if m != "c3_ban" and cls == "C3":
        failing.append("SP-2.2")
    if m != "transport":
        need = RANK[cls] >= RANK[old["SP-3.1"]["min_class"]] if old else c2
        if need and case["transport"] not in rules["SP-3.1"]["secure_transports"]:
            failing.append("SP-3.1")
    # Retention: the EU annex replaces SP-4.1 for EU data subjects (stricter rule wins)
    if c2 and m != "retention":
        if m == "annex_all":
            annex_applies, global_applies = True, False
        elif m == "annex":
            annex_applies, global_applies = False, True
        else:
            annex_applies, global_applies = "EU" in subjects, bool(subjects - {"EU"})
        cap = old["SP-4.1"]["max_days"] if old else rules["SP-4.1"]["max_days"]
        if global_applies and case["retention_days"] > cap:
            failing.append("SP-4.1")
        if annex_applies and case["retention_days"] > rules["AX-EU-1"]["max_days"]:
            failing.append("AX-EU-1")
    if c2 and m != "encryption" and not case["encrypted_at_rest"]:
        failing.append("SP-4.2")
    if c2 and m != "residency":
        if ("EU" in subjects or m == "residency_all") and vendor["region"] != "EU":
            failing.append("DR-1")
    if m != "zone" and case["source_zone"] == "Z3" and not case["egress_proxy"]:
        failing.append("NZ-2")
    if m != "gateway" and not case["via_gateway"]:
        failing.append("D1")

    # Waivers
    violations, conditions, waivers_used = [], [], []
    for r in failing:
        w = None if m == "waivers" else _waiver_for(r, case, subjects, go_live, p, m)
        if w:
            conditions.append(r)
            waivers_used.append(w)
        else:
            violations.append(r)

    # Freeze calendar
    if m != "freeze":
        for fw in p["freeze_windows"]:
            end = _d(fw["end"])
            if m == "freeze_inclusive_day_after":
                end = date.fromordinal(end.toordinal() + 1)
            if _d(fw["start"]) <= go_live <= end:
                conditions.append(fw["clause"])

    if violations:
        decision, conditions, waivers_used = "reject", [], []
    elif conditions:
        decision = "approve_with_conditions"
    else:
        decision = "approve"

    req = set()
    for r in violations + conditions:
        req.add(f"{rules[r]['doc']}#{r}")
    for w in waivers_used:
        req.add(f"{p['waivers'][w]['doc']}#{w}")
    if "SP-2.1" in violations or "DR-1" in violations:
        req.add(vendor["contract"])
    return {"decision": decision, "class": cls, "violations": sorted(violations),
            "conditions": sorted(conditions), "waivers": sorted(waivers_used),
            "required_citations": sorted(req)}


def _waiver_for(rule, case, subjects, go_live, p, m):
    for wid, w in p["waivers"].items():
        if w["rule"] != rule or w["vendor"] != case["vendor"]:
            continue
        if m not in ("waiver_dates",) and not (_d(w["valid_from"]) <= go_live <= _d(w["valid_to"])):
            continue
        if m == "waiver_ignore_valid":
            return None
        if m != "waiver_scope":
            if "subjects_only" in w and not subjects <= set(w["subjects_only"]):
                continue
            if "max_days" in w and case["retention_days"] > w["max_days"]:
                continue
        return wid
    return None


def outcome(r: dict) -> tuple:
    return r["decision"], tuple(r["violations"]), tuple(r["conditions"])
