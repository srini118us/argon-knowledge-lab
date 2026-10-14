"""Section aware chunking and a dense index on gemini-embedding-2.

The same index serves the RAG arms and the agent's search tool, so retrieval
quality is identical wherever it is used. Embeddings are cached on disk by a
hash of the chunk texts, so the corpus is embedded once per configuration.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

import numpy as np

from .corpus import ROOT, Doc

EMBED_MODEL = "gemini-embedding-2"
CHUNK_CHARS = 3200      # about 800 tokens
OVERLAP_CHARS = 400     # about 100 tokens


@dataclass
class Chunk:
    doc_id: str
    section: str
    text: str


def chunk_docs(docs: dict[str, Doc], include_captions: bool) -> list[Chunk]:
    chunks: list[Chunk] = []
    for d in docs.values():
        if d.kind == "diagram":
            if include_captions and d.text:
                chunks.append(Chunk(d.doc_id, "diagram caption", d.text))
            continue
        sections = re.split(r"\n(?=#{1,4} )", d.text)
        buf, head = "", "start"
        for sec in sections:
            title = sec.splitlines()[0].lstrip("#").strip() if sec.startswith("#") else head
            if buf and len(buf) + len(sec) > CHUNK_CHARS:
                chunks.append(Chunk(d.doc_id, head, buf))
                buf = buf[-OVERLAP_CHARS:]
                head = title
            if not buf:
                head = title
            buf += ("\n" if buf else "") + sec
            while len(buf) > CHUNK_CHARS * 1.5:   # one very long section
                chunks.append(Chunk(d.doc_id, head, buf[:CHUNK_CHARS]))
                buf = buf[CHUNK_CHARS - OVERLAP_CHARS:]
        if buf.strip():
            chunks.append(Chunk(d.doc_id, head, buf))
    return chunks


def _embed_text(c: Chunk, title: str) -> str:
    return f"Document {c.doc_id} | {title} | {c.section}\n{c.text}"


class Index:
    def __init__(self, client, docs: dict[str, Doc], include_captions: bool, size: str = "small"):
        self.client = client
        self.chunks = chunk_docs(docs, include_captions)
        self.embed_tokens = 0
        texts = [_embed_text(c, docs[c.doc_id].title) for c in self.chunks]
        key = hashlib.sha256(json.dumps([EMBED_MODEL, texts]).encode()).hexdigest()[:16]
        cache = ROOT / "results" / "index" / f"{size}_{'cap' if include_captions else 'text'}_{key}.npz"
        if cache.exists():
            self.vectors = np.load(cache)["v"]
        else:
            self.vectors = self._embed(texts, "RETRIEVAL_DOCUMENT")
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache, v=self.vectors)
            (cache.with_suffix(".json")).write_text(json.dumps([asdict(c) | {"chars": len(c.text)} for c in self.chunks], indent=1))

    def _embed(self, texts: list[str], task: str) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 50):
            batch = texts[i:i + 50]
            self.embed_tokens += sum(len(t) for t in batch) // 4
            try:
                r = self.client.models.embed_content(model=EMBED_MODEL, contents=batch, config={"task_type": task})
            except Exception:  # noqa: BLE001  model may not accept task_type
                r = self.client.models.embed_content(model=EMBED_MODEL, contents=batch)
            out.extend(e.values for e in r.embeddings)
        v = np.array(out, dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        q = self._embed([query], "RETRIEVAL_QUERY")[0]
        scores = self.vectors @ q
        top = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in top]
