"""Multistep tool loop for the model arms (Phase 7, mechanics only).

Drives a function-calling model through an investigation: the model emits a function call, the
loop dispatches it to the bounded Tools, feeds the result back, and repeats until the model calls
submit_investigation_verdict or a limit is hit. Model-agnostic: it takes a `client` object with a
single `.create(...)` method returning a response in a normalised shape, so Flash, Argon, and a
mock all drive the same loop.

This module makes NO API calls itself. Phase 8 passes a real Gemini-backed client; Phase 7 passes
the MockClient in agent/mock_client.py to validate the loop offline.

Normalised response shape the client must return (so the loop is model-agnostic):
  {
    "function_call": {"name": str, "args": dict} | None,   # the tool the model wants to call
    "verdict": dict | None,                                  # set when name == submit_...verdict
    "usage": {"input_tokens": int, "output_tokens": int, "thinking_tokens": int},
    "status": "ok" | "timeout" | "incomplete" | "error",
    "error": str | None,
  }
"""
from __future__ import annotations

from tools.tools import Tools

from . import schemas

MAX_TURNS = 15               # per-case cap on model turns (DESIGN.md 9.3)


def _dispatch(tools: Tools, name: str, args: dict):
    """Route a function call to the bounded tools. Unknown names return an error dict
    (the model can recover), never an exception."""
    if name == "run_sql":
        return tools.run_sql(args.get("tier"), args.get("query"), offset=args.get("offset", 0))
    if name == "get_pipeline_metadata":
        return tools.get_pipeline_metadata(args.get("pipeline_id"))
    if name == "inspect_transformation_logic":
        return tools.inspect_transformation_logic(args.get("view_name"))
    if name == "simulate_remediation":
        return tools.simulate_remediation(args.get("action_type"), args.get("parameters"))
    if name == "submit_investigation_verdict":
        return tools.submit_investigation_verdict(args)
    return {"error": "unknown_tool", "detail": f"no tool named {name}"}


def run_investigation(con, client, *, max_turns: int = MAX_TURNS, tool_schema=None) -> dict:
    """Run one investigation to a verdict or a limit. Returns a result dict with the verdict,
    the tool log, usage totals, completion status, and turn count.

    `client.create(messages, tools, system)` must return the normalised shape above.
    `tool_schema` is what gets passed to the client as `tools` (the real Gemini adapter wants
    schemas.GEMINI_TOOLS; the mock ignores it). Defaults to GEMINI_TOOLS.
    """
    tools = Tools(con)
    tool_schema = tool_schema if tool_schema is not None else schemas.GEMINI_TOOLS
    if hasattr(client, "reset"):
        client.reset()
    messages = [{"role": "user", "content": schemas.initial_user_message(_reported(con))}]
    usage = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
    verdict = None
    status = "incomplete"      # until a verdict is submitted or a terminal failure occurs
    turns = 0

    nudged = False   # whether we've already told the model to submit its verdict

    def _nudge():
        """Ask the model, once, to finalise by calling submit_investigation_verdict now."""
        messages.append({"role": "user", "content":
            "You have gathered enough evidence. Do not reply in prose. Call the "
            "submit_investigation_verdict tool now with your final structured diagnosis: "
            "root_causes (incident_class + layer), affected_business_keys, evidence, "
            "proposed_remediations, and verification."})

    for turns in range(1, max_turns + 1):
        resp = client.create(messages=messages, tools=tool_schema,
                             system=schemas.SYSTEM_PROMPT)
        u = resp.get("usage") or {}
        for k in usage:
            usage[k] += int(u.get(k, 0) or 0)

        st = resp.get("status", "ok")
        if st in ("timeout", "error"):
            status = st
            break

        fc = resp.get("function_call")

        # Model took no tool action this turn (gave prose, or spent its budget thinking).
        # Nudge it ONCE to submit the verdict; only stop if it still won't.
        if st == "incomplete" or not fc:
            if not nudged:
                nudged = True
                _nudge()
                continue
            status = "incomplete"
            break

        name, args = fc.get("name"), fc.get("args") or {}
        call_id = fc.get("call_id") or fc.get("id")
        result = _dispatch(tools, name, args)
        messages.append({"role": "model",
                         "function_call": {"name": name, "args": args, "call_id": call_id}})
        messages.append({"role": "tool", "name": name, "call_id": call_id, "content": result})

        if name == "submit_investigation_verdict" and not result.get("error"):
            verdict = args
            status = "completed"
            break

        # If the model has spent most of its turns still investigating, nudge it once to wrap up.
        if not nudged and turns >= max_turns - 3:
            nudged = True
            _nudge()

    return {
        "verdict": verdict,
        "log": tools.log,
        "tool_stats": tools.stats(),
        "usage": usage,
        "status": status,
        "turns": turns,
    }


def _reported(con) -> float:
    """The symptom shown to the agent: the reported discrepancy (no ground truth)."""
    from sim import reconcile
    return float(reconcile.discrepancy(con))
