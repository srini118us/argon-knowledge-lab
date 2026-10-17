"""Shared function-calling schemas for the model arms (Phase 7).

Both Gemini 3.8 Flash and Gemini 4 Argon receive these IDENTICAL tool declarations and the
identical system prompt. This is the fairness invariant: the only variables across arms are the
model id and the thinking level. The schemas describe the five bounded tools from Phase 3.

No answer key, injector manifest, or ground-truth detail appears in any schema or prompt.
"""
from __future__ import annotations

TIERS = ["source", "cdc", "datasphere", "share", "mart", "metadata"]
PIPELINES = ["cdc_extract", "dsp_build", "share_publish", "mart_load"]
VIEWS = ["dsp_ar_items", "share_ar_items", "dbx_ar_mart_load"]
ACTIONS = ["reextract_batch", "backfill_missing", "dedupe_target", "reload_idempotent",
           "fix_transform", "refresh_customer_snapshot"]
INCIDENT_CLASSES = ["missing_cdc_delta", "duplicate_replay", "currency_basis",
                    "lossy_join", "compound"]
LAYERS = ["L1", "L2", "L3", "L4"]

# Gemini function declarations (the shape client.interactions.create takes as `tools`).
FUNCTION_DECLARATIONS = [
    {
        "name": "run_sql",
        "description": "Run a read-only SQL SELECT against one data tier. Single statement only; "
                       "no writes/DDL; may reference only tables in the named tier. Results are "
                       "row-capped and paginated via offset.",
        "parameters": {
            "type": "object",
            "properties": {
                "tier": {"type": "string", "enum": TIERS},
                "query": {"type": "string", "description": "a single SELECT or WITH ... SELECT"},
                "offset": {"type": "integer", "description": "pagination offset (optional)"},
            },
            "required": ["tier", "query"],
        },
    },
    {
        "name": "get_pipeline_metadata",
        "description": "Return a pipeline's configuration (watermark, idempotent flag, join type) "
                       "and its run history (all stages, statuses, row counts).",
        "parameters": {
            "type": "object",
            "properties": {"pipeline_id": {"type": "string", "enum": PIPELINES}},
            "required": ["pipeline_id"],
        },
    },
    {
        "name": "inspect_transformation_logic",
        "description": "Return the definition and column mapping of a transformation view or the "
                       "mart load step.",
        "parameters": {
            "type": "object",
            "properties": {"view_name": {"type": "string", "enum": VIEWS}},
            "required": ["view_name"],
        },
    },
    {
        "name": "simulate_remediation",
        "description": "Apply a remediation to an ISOLATED copy and return before/after "
                       "reconciliation. Never changes the real data. Enumerated actions only.",
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "enum": ACTIONS},
                "parameters": {"type": "object", "description": "action params, e.g. business_keys"},
            },
            "required": ["action_type"],
        },
    },
    {
        "name": "submit_investigation_verdict",
        "description": "Submit the final structured diagnosis. Ends the investigation.",
        "parameters": {
            "type": "object",
            "properties": {
                "root_causes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "incident_class": {"type": "string", "enum": INCIDENT_CLASSES},
                            "layer": {"type": "string", "enum": LAYERS},
                            "description": {"type": "string"},
                        },
                        "required": ["incident_class", "layer"],
                    },
                },
                "affected_business_keys": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "proposed_remediations": {"type": "array", "items": {"type": "object"}},
                "verification": {"type": "object"},
            },
            "required": ["root_causes", "affected_business_keys", "proposed_remediations"],
        },
    },
]

TOOL_NAMES = [f["name"] for f in FUNCTION_DECLARATIONS]

SYSTEM_PROMPT = (
    "You are a senior data engineer investigating a finance reconciliation discrepancy. "
    "Accounts Receivable in SAP S/4HANA does not match a downstream Databricks finance mart, "
    "and every pipeline monitor shows SUCCESS. The data path is "
    "S/4HANA -> CDC -> Datasphere data product -> Delta share -> Databricks mart. "
    "Investigate using only the provided tools. The SAP source is authoritative. "
    "Query the layers, localise where records or amounts first diverge, and determine the "
    "root cause(s), the exact affected business keys, and a safe remediation. "
    "Test any fix with simulate_remediation (it runs on an isolated copy). "
    "When confident, call submit_investigation_verdict with your structured diagnosis. "
    "Do not claim success without evidence; the grader re-checks every repair independently."
)

# The initial user message is just the reported symptom; the agent must investigate from there.
def initial_user_message(discrepancy: float) -> str:
    return (f"Finance reports an AR discrepancy of about {discrepancy:,.0f} (source minus target) "
            f"for the current period. Monitoring is green. Investigate and submit a verdict.")
