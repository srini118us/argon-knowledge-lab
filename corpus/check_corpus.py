"""Consistency checker for the frozen corpus and question key.

Fails loudly if:
  1. a key fact of an answered question is missing from its required documents
     (diagram facts are checked against the diagram source, which is never
     given to any model);
  2. a forbidden fact (diagram only, or answer to an unanswerable question)
     appears in any text document;
  3. a required citation points to a document that does not exist.

Writes corpus/<size>/MANIFEST.json with SHA256 of every file plus a rough
token estimate (characters / 4; the real count comes from the API).

    python corpus/check_corpus.py small
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "spec"

# Things that must appear nowhere in the text documents.
FORBIDDEN = {
    "region names": r"us-east|us-west",
    "warehouse name": r"Polaris",
    "egress proxy": r"egress",
    "carrier topic": r"shipment-requests",
    "event name": r"OrderPlaced",
    "SOC 2": r"SOC\s*2",
    "broker count": r"\b\d+\s+(Kafka\s+)?brokers\b|\bbrokers?:\s*\d+",
    "customer-service recovery": r"customer-service[^.\n]{0,80}(Tier\s*\d|RPO|RTO)|(Tier\s*\d|RPO|RTO)[^.\n]{0,80}customer-service",
    "PayNimbus termination": r"(terminat|notice period)[^.\n]{0,120}\b\d+\s*(days|months|weeks)",
    "LedgerOne SLA": r"LedgerOne[^.\n]{0,100}(SLA|availab|\d+(\.\d+)?\s*%)",
    "Relatia limit": r"Relatia[^.\n]{0,100}(rate limit|requests per)",
    "migration budget": r"budget[^.\n]{0,60}(\$|USD|\d)",
    "Shipping API v1": r"Shipping API v1|SPEC-SHIP-API\s*(@|v)\s*v?1\b",
    "retry queue depth": r"payment-retry[^.\n]{0,80}(depth|max(imum)? (size|length|messages))",
    "sync/async PayNimbus": r"payment-service[^.\n]{0,80}(synchronous|asynchronous|sync REST)[^.\n]{0,40}PayNimbus",
}
# Per document bans from the spec that a regex can check.
DOC_BANS = {
    "ADR-011@v1": r"mTLS|mutual TLS",
    "PM-2025-014@v1": r"ADR-024",
}


def load_docs(size: str) -> dict[str, str]:
    docs = {p.stem: p.read_text(encoding="utf-8") for p in sorted((HERE / size / "docs").glob("*.md"))}
    for p in sorted(SPEC.glob("diagram_src/*.dot")):
        docs[f"{p.stem}@v1"] = p.read_text(encoding="utf-8")  # ground truth only, never sent to models
    return docs


def main(size: str) -> int:
    spec = json.loads((SPEC / "corpus_spec.json").read_text())
    questions = json.loads((SPEC / "questions.json").read_text())["questions"]
    docs = load_docs(size)
    text_docs = {k: v for k, v in docs.items() if not k.startswith("DIAG-")}
    problems: list[str] = []

    expected = {f"{d['id']}@{d['version']}" for d in spec["documents"]} | {f"{d['id']}@{d['version']}" for d in spec["diagrams"]}
    for missing in sorted(expected - set(docs)):
        problems.append(f"MISSING document {missing}")

    for q in questions:
        for c in q["required_citations"] + q["superseded_citations"]:
            if c not in docs:
                problems.append(f"{q['id']}: cites unknown document {c}")
        if q["status"] != "answered":
            continue
        corpus = "\n".join(docs.get(c, "") for c in q["required_citations"])
        for fact in q["key_facts"]:
            if not re.search(fact, corpus, re.I):
                problems.append(f"{q['id']}: key fact /{fact}/ not found in {q['required_citations']}")

    hits = []
    for name, pattern in FORBIDDEN.items():
        for doc_id, text in text_docs.items():
            for m in re.finditer(pattern, text, re.I):
                line = text[max(0, m.start() - 60): m.end() + 60].replace("\n", " ")
                hits.append(f"FORBIDDEN [{name}] in {doc_id}: ...{line}...")
    for doc_id, pattern in DOC_BANS.items():
        if doc_id in text_docs and re.search(pattern, text_docs[doc_id], re.I):
            hits.append(f"DOC BAN /{pattern}/ in {doc_id}")

    files = sorted((HERE / size).rglob("*.*"))
    files = [f for f in files if f.name != "MANIFEST.json"]
    chars = sum(len(t) for t in text_docs.values())
    manifest = {
        "size": size,
        "text_documents": len(text_docs),
        "diagrams": len(list((HERE / size / "diagrams").glob("*.png"))),
        "approx_text_tokens": chars // 4,
        "files": {str(f.relative_to(HERE)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        "spec_files": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(SPEC.rglob("*.*"))},
    }
    (HERE / size / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))

    for p in problems + hits:
        print(p)
    print(f"\n{len(text_docs)} text documents, {manifest['diagrams']} diagrams, ~{manifest['approx_text_tokens']:,} text tokens")
    print(f"{len(problems)} key fact problems, {len(hits)} forbidden hits")
    return 1 if problems or hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "small"))
