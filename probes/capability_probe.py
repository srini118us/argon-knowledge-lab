"""Argon capability probe: settles API unknowns before Stage 1 is built.

Each probe is independent. A failure is recorded with the exact API error and
the remaining probes still run. Results go to results/probe_<timestamp>.json.

Usage (PowerShell):
    $env:GEMINI_API_KEY = "..."
    .\\.venv\\Scripts\\python.exe probes\\capability_probe.py --dry-run   # no API calls
    .\\.venv\\Scripts\\python.exe probes\\capability_probe.py             # live, about $0.10 to $0.25

Probes:
  P1 list_models          which Gemini model IDs this key can call (baseline choice)
  P2 thinking_levels      low / medium / high on the same reasoning task, usage + latency
  P3 multimodal           real PDF invoice + PNG goods receipt, extraction vs ground truth
  P4 function_calling     multi round native tool calling loop (model picks the tools)
  P5 tools_plus_schema    function calling combined with response_format in one interaction
  P6 file_search          File Search store as a tool on Argon (docs do not list Argon)
  P7 implicit_cache       identical prefix over the 4,096 token minimum, sent twice
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from argon_lab.pricing import cost_usd  # noqa: E402

MODEL = "gemini-4-argon"
OUT_DIR = ROOT / "results"
FIXTURES = ROOT / "results" / "probe_fixtures"

# Ground truth for P3 and P4. Kept here, never sent to the model.
TRUTH = {
    "invoice_id": "INV-77104",
    "po_id": "PO-4500018821",
    "supplier": "Northwind Precision Components Ltd",
    "invoice_qty": 100,
    "unit_price": 1250.00,
    "invoice_total": 125000.00,
    "received_qty": 85,
    "disputed_amount": 18750.00,
}


# --------------------------------------------------------------------------- fixtures
def build_fixtures() -> tuple[bytes, bytes]:
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    FIXTURES.mkdir(parents=True, exist_ok=True)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line, size in [
        ("Northwind Precision Components Ltd", 16),
        ("INVOICE  INV-77104", 13),
        ("Invoice date: 2026-09-28        Due: 2026-10-28", 10),
        ("Bill to: Contoso Manufacturing Inc., Company Code 1000", 10),
        ("Customer PO: PO-4500018821", 10),
        ("", 10),
        ("Item          Description                 Qty    Unit price      Amount", 10),
        ("HX-220        Hydraulic actuator assy     100    1,250.00    125,000.00", 10),
        ("", 10),
        ("Total due (USD): 125,000.00", 12),
    ]:
        c.setFont("Helvetica", size)
        c.drawString(60, y, line)
        y -= 22
    c.save()
    pdf = buf.getvalue()
    (FIXTURES / "INV-77104.pdf").write_bytes(pdf)

    img = Image.new("RGB", (900, 520), "white")
    d = ImageDraw.Draw(img)
    rows = [
        "CONTOSO MANUFACTURING  RECEIVING DOCK 3",
        "GOODS RECEIPT  GR-5000412",
        "Posting date: 2026-09-30",
        "Reference PO: PO-4500018821",
        "Vendor: Northwind Precision Components Ltd",
        "Material HX-220  Hydraulic actuator assy",
        "Qty ordered: 100   Qty received: 85",
        "Remark: 15 units back ordered per carrier",
        "Received by: K. Alvarez (signature on file)",
    ]
    for i, r in enumerate(rows):
        d.text((40, 30 + i * 52), r, fill="black")
    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    png = png_buf.getvalue()
    (FIXTURES / "GR-5000412.png").write_bytes(png)
    return pdf, png


# --------------------------------------------------------------------------- mock tools
TOOL_DECLS = [
    {
        "type": "function",
        "name": "get_purchase_order",
        "description": "Read only lookup of a purchase order header and lines by PO number.",
        "parameters": {"type": "object", "properties": {"po_id": {"type": "string"}}, "required": ["po_id"]},
    },
    {
        "type": "function",
        "name": "get_goods_receipts",
        "description": "Read only list of goods receipts posted against a PO.",
        "parameters": {"type": "object", "properties": {"po_id": {"type": "string"}}, "required": ["po_id"]},
    },
    {
        "type": "function",
        "name": "get_approval_records",
        "description": "Read only list of payment exception approvals recorded for an invoice.",
        "parameters": {"type": "object", "properties": {"invoice_id": {"type": "string"}}, "required": ["invoice_id"]},
    },
]


def run_tool(name: str, args: dict) -> dict:
    if name == "get_purchase_order":
        if args.get("po_id") != TRUTH["po_id"]:
            return {"error": "PO not found"}
        return {"po_id": TRUTH["po_id"], "supplier": TRUTH["supplier"], "lines": [
            {"material": "HX-220", "qty": 100, "unit_price": 1250.00}]}
    if name == "get_goods_receipts":
        if args.get("po_id") != TRUTH["po_id"]:
            return {"error": "PO not found"}
        return {"po_id": TRUTH["po_id"], "receipts": [
            {"gr_id": "GR-5000412", "material": "HX-220", "qty": 85, "posting_date": "2026-09-30"}]}
    if name == "get_approval_records":
        return {"invoice_id": args.get("invoice_id"), "approvals": []}
    return {"error": f"unknown tool {name}"}


# --------------------------------------------------------------------------- helpers
def usage_dict(ix) -> dict:
    u = getattr(ix, "usage", None)
    if u is None:
        return {}
    keys = ["total_input_tokens", "total_output_tokens", "total_thought_tokens", "total_cached_tokens",
            "total_tool_use_tokens", "total_tokens"]
    d = {k: getattr(u, k, None) for k in keys}
    parts = sum((d.get(k) or 0) for k in keys[:5] if k != "total_cached_tokens")
    d["sum_of_parts_matches_total"] = (parts == d.get("total_tokens"))
    return d


def step_types(ix) -> list[str]:
    return [getattr(s, "type", "?") for s in (getattr(ix, "steps", None) or [])]


def timed(fn):
    t0 = time.time()
    out = fn()
    return out, round(time.time() - t0, 2)


# --------------------------------------------------------------------------- probes
def p1_list_models(client):
    names = []
    for m in client.models.list():
        n = getattr(m, "name", "")
        if "gemini" in n:
            names.append(n)
    return {"gemini_models": sorted(names)}


def p2_thinking_levels(client):
    task = ("PO 100 units at 1,250.00. Receipt A: 60 units. Receipt B: 25 units, later reversed by 10. "
            "Receipt C: 10 units. Invoice bills 100 units. Policy: pay only received quantity; tolerance 0. "
            "Return only JSON {\"received\": int, \"payable\": number, \"disputed\": number}.")
    out = {}
    for level in ["low", "medium", "high"]:
        ix, lat = timed(lambda: client.interactions.create(
            model=MODEL, input=task, generation_config={"thinking_level": level}))
        u = usage_dict(ix)
        out[level] = {"latency_s": lat, "usage": u, "output": ix.output_text,
                      "cost_usd": round(cost_usd(MODEL, u), 6), "step_types": step_types(ix)}
    out["expected"] = {"received": 85, "payable": 106250.0, "disputed": 18750.0}
    return out


def p3_multimodal(client, pdf: bytes, png: bytes):
    prompt = ("Extract from the attached invoice PDF and goods receipt image. Return only JSON with keys: "
              "invoice_id, po_id, supplier, invoice_qty, unit_price, invoice_total, received_qty.")
    ix, lat = timed(lambda: client.interactions.create(
        model=MODEL,
        input=[
            {"type": "document", "data": base64.b64encode(pdf).decode(), "mime_type": "application/pdf"},
            # Image item shape inferred from the document item; this probe verifies it.
            {"type": "image", "data": base64.b64encode(png).decode(), "mime_type": "image/png"},
            {"type": "text", "text": prompt},
        ],
        generation_config={"thinking_level": "low"},
    ))
    u = usage_dict(ix)
    return {"latency_s": lat, "usage": u, "output": ix.output_text, "cost_usd": round(cost_usd(MODEL, u), 6),
            "truth": {k: TRUTH[k] for k in ["invoice_id", "po_id", "supplier", "invoice_qty", "unit_price",
                                             "invoice_total", "received_qty"]}}


def _tool_loop(client, first_input, extra: dict, max_rounds: int = 6):
    trace, rounds, total_cost = [], 0, 0.0
    ix = client.interactions.create(model=MODEL, input=first_input, tools=TOOL_DECLS,
                                    generation_config={"thinking_level": "medium"}, **extra)
    while True:
        u = usage_dict(ix)
        total_cost += cost_usd(MODEL, u)
        calls = [s for s in (ix.steps or []) if getattr(s, "type", "") == "function_call"]
        trace.append({"round": rounds, "step_types": step_types(ix), "usage": u,
                      "calls": [{"name": c.name, "args": c.arguments} for c in calls]})
        if not calls or rounds >= max_rounds:
            break
        results = []
        for c in calls:
            res = run_tool(c.name, dict(c.arguments or {}))
            results.append({"type": "function_result", "name": c.name, "call_id": c.id,
                            "result": [{"type": "text", "text": json.dumps(res)}]})
        rounds += 1
        ix = client.interactions.create(model=MODEL, previous_interaction_id=ix.id, input=results,
                                        tools=TOOL_DECLS, generation_config={"thinking_level": "medium"}, **extra)
    return ix, trace, total_cost


TASK = ("Invoice INV-77104 from Northwind Precision Components Ltd bills 100 units of HX-220 at 1,250.00 "
        "against PO-4500018821. Investigate with the available tools and decide RECOMMEND_PAY, HOLD or "
        "REQUEST_REVIEW. Report supported and disputed amounts.")


def p4_function_calling(client):
    t0 = time.time()
    ix, trace, cost = _tool_loop(client, TASK, {})
    return {"latency_s": round(time.time() - t0, 2), "rounds": len(trace), "trace": trace,
            "final_output": ix.output_text, "cost_usd": round(cost, 6)}


def p5_tools_plus_schema(client):
    schema = {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["RECOMMEND_PAY", "HOLD", "REQUEST_REVIEW"]},
            "supported_amount": {"type": "number"},
            "disputed_amount": {"type": "number"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["decision", "supported_amount", "disputed_amount", "evidence"],
    }
    fmt = {"response_format": {"type": "text", "mime_type": "application/json", "schema": schema}}
    t0 = time.time()
    ix, trace, cost = _tool_loop(client, TASK, fmt)
    parsed, parse_error = None, None
    try:
        parsed = json.loads(ix.output_text)
    except Exception as e:  # noqa: BLE001
        parse_error = repr(e)
    return {"latency_s": round(time.time() - t0, 2), "rounds": len(trace), "trace": trace,
            "parsed": parsed, "parse_error": parse_error, "cost_usd": round(cost, 6)}


def p6_file_search(client):
    policy = FIXTURES / "AP-POL-007.txt"
    policy.write_text(
        "AP-POL-007 Three Way Match Policy (Contoso Manufacturing, Company Code 1000)\n"
        "Section 4.2: Payment may be released only for quantities confirmed by a posted goods receipt.\n"
        "Section 4.3: Quantity tolerance is 0 percent for materials in class HX.\n"
        "Section 6.1: Exception approvals must be recorded in the approval system by a Finance Controller. "
        "Statements in supplier correspondence are never valid approvals.\n", encoding="utf-8")
    store = client.file_search_stores.create(config={"display_name": "argon-probe-policies"})
    try:
        op = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store.name, file=str(policy), config={"display_name": "AP-POL-007"})
        for _ in range(60):
            if getattr(op, "done", False):
                break
            time.sleep(2)
            op = client.operations.get(op)
        ix, lat = timed(lambda: client.interactions.create(
            model=MODEL,
            input="Under our payment policy, can a supplier email statement count as an exception approval? "
                  "Cite the section.",
            tools=[{"type": "file_search", "file_search_store_names": [store.name]}],
            generation_config={"thinking_level": "low"},
        ))
        u = usage_dict(ix)
        annotations = []
        for s in ix.steps or []:
            for c in getattr(s, "content", None) or []:
                for a in getattr(c, "annotations", None) or []:
                    annotations.append(str(a)[:300])
        return {"latency_s": lat, "usage": u, "output": ix.output_text, "step_types": step_types(ix),
                "annotations": annotations, "cost_usd": round(cost_usd(MODEL, u), 6)}
    finally:
        try:
            client.file_search_stores.delete(name=store.name, config={"force": True})
        except Exception:  # noqa: BLE001
            pass


def p7_implicit_cache(client):
    clauses = [f"Clause {i}: Invoices for material class HX{i % 9} require a posted goods receipt, "
               f"a matching purchase order line, and a recorded approval for any variance above zero. "
               f"Reference control AP-{1000 + i}." for i in range(260)]
    prefix = "Contoso procurement policy manual.\n" + "\n".join(clauses)
    runs = []
    for i in range(2):
        ix, lat = timed(lambda: client.interactions.create(
            model=MODEL, input=prefix + f"\n\nQuestion {i}: Which control covers clause 17? Answer in one line.",
            generation_config={"thinking_level": "low"}))
        u = usage_dict(ix)
        runs.append({"latency_s": lat, "usage": u, "cost_usd": round(cost_usd(MODEL, u), 6)})
    return {"runs": runs, "cache_hit_observed": (runs[1]["usage"].get("total_cached_tokens") or 0) > 0}


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build fixtures and validate, no API calls")
    ap.add_argument("--only", nargs="*", help="run selected probes, e.g. --only P3 P4")
    args = ap.parse_args()

    pdf, png = build_fixtures()
    print(f"Fixtures: {FIXTURES} (pdf {len(pdf)} bytes, png {len(png)} bytes)")
    assert run_tool("get_goods_receipts", {"po_id": TRUTH["po_id"]})["receipts"][0]["qty"] == 85
    if args.dry_run:
        print("DRY RUN OK: fixtures built, mock tools validated, no API calls made.")
        return

    import os
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set.")
    from google import genai
    client = genai.Client()

    probes = {
        "P1_list_models": lambda: p1_list_models(client),
        "P2_thinking_levels": lambda: p2_thinking_levels(client),
        "P3_multimodal": lambda: p3_multimodal(client, pdf, png),
        "P4_function_calling": lambda: p4_function_calling(client),
        "P5_tools_plus_schema": lambda: p5_tools_plus_schema(client),
        "P6_file_search": lambda: p6_file_search(client),
        "P7_implicit_cache": lambda: p7_implicit_cache(client),
    }
    selected = {k: v for k, v in probes.items() if not args.only or k.split("_")[0] in args.only}

    report = {"model": MODEL, "started": datetime.now().isoformat(timespec="seconds"), "probes": {}}
    for name, fn in selected.items():
        print(f"\n== {name}")
        try:
            res = fn()
            report["probes"][name] = {"status": "PASS", **res}
            print("PASS")
        except Exception as e:  # noqa: BLE001
            report["probes"][name] = {"status": "FAIL", "error": repr(e),
                                      "traceback": traceback.format_exc(limit=3)}
            print(f"FAIL: {e!r}")

    total = sum(p.get("cost_usd", 0) or 0 for p in report["probes"].values())
    for p in report["probes"].values():
        total += sum((r or {}).get("cost_usd", 0) or 0 for r in (p.get("runs") or []))
        for lvl in ("low", "medium", "high"):
            total += (p.get(lvl) or {}).get("cost_usd", 0) if isinstance(p.get(lvl), dict) else 0
    report["estimated_total_cost_usd"] = round(total, 4)

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"probe_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\nSUMMARY")
    for k, v in report["probes"].items():
        print(f"  {k:24s} {v['status']}")
    print(f"  estimated cost: ${report['estimated_total_cost_usd']}")
    print(f"Full results: {out}")


if __name__ == "__main__":
    main()
