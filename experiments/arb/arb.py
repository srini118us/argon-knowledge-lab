"""Shared helpers for Experiment 2 (Architecture Review Board): pack loading, case rendering,
prompt, answer schema, key loading. No API calls here."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "spec"
PACK = HERE / "pack"

FIELD_NAMES = {
    "shipment_id": "shipment IDs", "route_plan": "route plans", "telemetry": "vehicle telemetry",
    "customer_email": "customer email addresses", "customer_phone": "customer phone numbers",
    "delivery_address": "delivery addresses", "driver_location": "driver locations",
    "card_pan": "card numbers (PAN)",
}
REGION_NAMES = {"US": "the US", "EU": "the EU", "APAC": "Asia Pacific"}
TRANSPORT = {"mtls": "mutual TLS", "private_link": "a private link connection",
             "tls": "standard HTTPS (server side TLS)"}

SYSTEM = (
    "You are a voting member of the Northwind Logistics Architecture Review Board. "
    "Decide integration proposals using only the review pack provided; never use outside knowledge or assumptions. "
    "Follow the ARB charter's decision procedure exactly, evaluating every applicable rule. "
    "Cite every violation, condition, waiver and contract you rely on as DOC_ID@VERSION#CLAUSE "
    "(contracts as DOC_ID@VERSION)."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "approve_with_conditions", "reject"]},
        "violations": {"type": "array", "items": {"type": "string"},
                       "description": "Clause IDs of rules violated, e.g. SP-3.1"},
        "conditions": {"type": "array", "items": {"type": "string"},
                       "description": "Clause IDs of rules that are conditions, e.g. SP-4.2 or CF-1"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["decision", "violations", "conditions", "citations", "rationale"],
}
FINAL_JSON = ('Reply with only a JSON object with keys decision (approve, approve_with_conditions or reject), '
              'violations (list of clause IDs), conditions (list of clause IDs), citations (list), rationale (string).')


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def load_cases(split: str | None = None) -> list[dict]:
    cases = json.loads((SPEC / "cases.json").read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if split is None or c["split"] == split]


def load_key() -> dict:
    return json.loads((SPEC / "key.json").read_text(encoding="utf-8"))["key"]


def pack_text() -> str:
    """All pack documents in a fixed order: a stable prefix for every request."""
    return "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(PACK.glob("*.md")))


def render(case: dict) -> str:
    """Prose proposal as a delivery team would submit it. Models never see the structured fields."""
    subj = _join([REGION_NAMES[s] for s in case["data_subjects"]])
    zone = case["source_zone"]
    egress = ("Outbound traffic from the service passes through the egress proxy."
              if case["egress_proxy"] else "Outbound traffic does not use the egress proxy.")
    route = ("The service calls the vendor through int-gw."
             if case["via_gateway"] else "The service calls the vendor's API directly from its own code.")
    enc = ("The vendor stores the data encrypted at rest."
           if case["encrypted_at_rest"] else "The vendor stores the data without encryption at rest.")
    return (
        f"Proposal {case['id']}: {case['title']}\n\n"
        f"The team proposes to send {_join([FIELD_NAMES[f] for f in case['fields']])} to {case['vendor']}. "
        f"Any people the data is about are in {subj}. "
        f"The sending service runs in network zone {zone}. {egress} {route} "
        f"Data is transferred over {TRANSPORT[case['transport']]}. "
        f"{case['vendor']} will retain the data for {case['retention_days']} days. {enc} "
        f"Planned production go live: {case['go_live']}.\n\n"
        "Decide this proposal under the ARB charter."
    )


def prompt(case: dict) -> list[dict]:
    """Pack first (fixed order, cache friendly), proposal last."""
    return [{"type": "text", "text": "Northwind Logistics ARB review pack.\n\n" + pack_text()},
            {"type": "text", "text": render(case)}]
