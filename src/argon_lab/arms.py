"""The four arms. Same system prompt and answer schema everywhere.

R1  classic RAG, text only (diagrams not indexed; labelled as such)
R2  classic RAG with frozen diagram captions indexed as text
L   long context: every document plus diagram images, corpus first, question last
A   agentic retrieval: search_docs / read_doc / list_docs tools over the R2 index
"""
from __future__ import annotations

import json
import re
import time

from .corpus import Doc, png_b64

SYSTEM = (
    "You answer questions about Northwind Logistics internal architecture documentation. "
    "Use only the documents provided to you or returned by your tools; never use outside knowledge. "
    "If the documents do not contain the answer, set status to not_found and do not guess. "
    "Documents can conflict: prefer the current version by checking Status, Supersedes or Superseded by, and dates. "
    "Cite every document you rely on by its exact identifier in the form DOC_ID@VERSION, for example ADR-024@v1 or DIAG-01@v1. "
    "Keep the answer short and specific."
)
FINAL_JSON = ('Reply with only a JSON object: {"status": "answered" or "not_found", '
              '"answer": string, "citations": [list of DOC_ID@VERSION strings]}')
SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answered", "not_found"]},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "answer", "citations"],
}
RAG_K = 8
AGENT_MAX_ROUNDS = 8
USAGE_KEYS = ["total_input_tokens", "total_output_tokens", "total_thought_tokens",
              "total_cached_tokens", "total_tool_use_tokens", "total_tokens"]


class Run:
    """Accumulates usage, latency and trace across the calls of one question."""

    def __init__(self):
        self.usage = {k: 0 for k in USAGE_KEYS}
        self.calls = 0
        self.tool_calls: list[dict] = []
        self.retrieved: set[str] = set()
        self.latency = 0.0
        self.notes: list[str] = []

    def call(self, client, **kw):
        t0 = time.time()
        ix = client.interactions.create(**kw)
        self.latency += time.time() - t0
        self.calls += 1
        u = getattr(ix, "usage", None)
        for k in USAGE_KEYS:
            self.usage[k] += (getattr(u, k, 0) or 0) if u else 0
        return ix


def parse_answer(text: str) -> dict | None:
    if not text:
        return None
    t = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    d.setdefault("citations", [])
    d.setdefault("answer", "")
    if d.get("status") not in ("answered", "not_found"):
        return None
    return d


def _structured(client, run: Run, model: str, level: str, inputs, **extra) -> dict | None:
    """Ask for the schema. If the API rejects response_format, fall back to a JSON instruction."""
    try:
        ix = run.call(client, model=model, input=inputs, system_instruction=SYSTEM,
                      generation_config={"thinking_level": level},
                      response_format={"type": "text", "mime_type": "application/json", "schema": SCHEMA}, **extra)
    except Exception as e:  # noqa: BLE001
        if "response_format" not in str(e) and "schema" not in str(e).lower():
            raise
        run.notes.append(f"response_format rejected, used JSON instruction: {e!s:.120}")
        if isinstance(inputs, str):
            inputs = inputs + "\n\n" + FINAL_JSON
        else:
            inputs = list(inputs) + [{"type": "text", "text": FINAL_JSON}]
        ix = run.call(client, model=model, input=inputs, system_instruction=SYSTEM,
                      generation_config={"thinking_level": level}, **extra)
    return parse_answer(ix.output_text)


# ------------------------------------------------------------------ RAG
def rag(client, model, level, question, index) -> tuple[dict | None, Run]:
    run = Run()
    hits = index.search(question, RAG_K)
    blocks = []
    for c, score in hits:
        run.retrieved.add(c.doc_id)
        blocks.append(f"=== {c.doc_id} | section: {c.section} ===\n{c.text}")
    prompt = "Retrieved document excerpts:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    return _structured(client, run, model, level, prompt), run


# ------------------------------------------------------------------ long context
def long_context_input(docs: dict[str, Doc], question: str) -> list[dict]:
    """Corpus first in a fixed order (stable prefix), question last."""
    text = "\n\n".join(f"=== DOCUMENT {d.doc_id} ===\n{d.text}" for d in docs.values() if d.kind == "text")
    items = [{"type": "text", "text": "Northwind Logistics documentation corpus.\n\n" + text}]
    for d in docs.values():
        if d.kind == "diagram":
            items.append({"type": "text", "text": f"=== DIAGRAM {d.doc_id} ==="})
            items.append({"type": "image", "data": png_b64(d), "mime_type": "image/png"})
    items.append({"type": "text", "text": f"Question: {question}"})
    return items


def long_context(client, model, level, question, docs) -> tuple[dict | None, Run]:
    run = Run()
    run.retrieved = set(docs)
    return _structured(client, run, model, level, long_context_input(docs, question)), run


# ------------------------------------------------------------------ agentic retrieval
TOOLS = [
    {"type": "function", "name": "list_docs",
     "description": "List every document with its type, title, date and status. Diagrams appear as DIAG-xx.",
     "parameters": {"type": "object", "properties": {}}},
    {"type": "function", "name": "search_docs",
     "description": "Semantic search over document sections. Returns the best matching sections with a short snippet.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"}, "k": {"type": "integer", "description": "1 to 8, default 5"}},
         "required": ["query"]}},
    {"type": "function", "name": "read_doc",
     "description": "Return the full text of one document by its exact DOC_ID@VERSION. For diagrams this returns a text caption.",
     "parameters": {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]}},
]


def _tool(name: str, args: dict, docs: dict[str, Doc], index, run: Run) -> dict:
    if name == "list_docs":
        return {"documents": [{"doc_id": d.doc_id, "type": d.kind, "title": d.title, "date": d.date,
                               "status": d.status} for d in docs.values()]}
    if name == "search_docs":
        k = max(1, min(8, int(args.get("k") or 5)))
        out = []
        for c, s in index.search(str(args.get("query", "")), k):
            run.retrieved.add(c.doc_id)
            out.append({"doc_id": c.doc_id, "section": c.section, "score": round(s, 3), "snippet": c.text[:600]})
        return {"results": out}
    if name == "read_doc":
        d = docs.get(str(args.get("doc_id", "")).strip())
        if not d:
            return {"error": "unknown doc_id; call list_docs for valid identifiers"}
        run.retrieved.add(d.doc_id)
        if d.kind == "diagram":
            return {"doc_id": d.doc_id, "note": "caption generated once by gemini-3.8-flash from the diagram image",
                    "text": d.text}
        return {"doc_id": d.doc_id, "text": d.text}
    return {"error": f"unknown tool {name}"}


def agentic(client, model, level, question, docs, index) -> tuple[dict | None, Run]:
    run = Run()
    prompt = f"Question: {question}\n\nUse the tools to find the evidence. When you are done, {FINAL_JSON[0].lower()}{FINAL_JSON[1:]}"
    ix = run.call(client, model=model, input=prompt, system_instruction=SYSTEM, tools=TOOLS,
                  generation_config={"thinking_level": level})
    for _ in range(AGENT_MAX_ROUNDS):
        calls = [s for s in (ix.steps or []) if getattr(s, "type", "") == "function_call"]
        if not calls:
            break
        results = []
        for c in calls:
            args = dict(c.arguments or {})
            run.tool_calls.append({"name": c.name, "args": args})
            res = _tool(c.name, args, docs, index, run)
            results.append({"type": "function_result", "name": c.name, "call_id": c.id,
                            "result": [{"type": "text", "text": json.dumps(res)}]})
        ix = run.call(client, model=model, previous_interaction_id=ix.id, input=results,
                      system_instruction=SYSTEM, tools=TOOLS, generation_config={"thinking_level": level})
    else:
        run.notes.append(f"hit the {AGENT_MAX_ROUNDS} round limit")

    answer = parse_answer(ix.output_text)
    if answer is None:
        run.notes.append("final answer not JSON; asked once more for the JSON object")
        answer = _structured(client, run, model, level, FINAL_JSON, previous_interaction_id=ix.id)
    return answer, run
