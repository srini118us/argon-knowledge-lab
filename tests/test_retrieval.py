"""Chunking and index validation, with a fake embedding client (offline)."""
import types

import numpy as np
import pytest

from argon_lab import corpus, retrieval


@pytest.fixture(scope="module")
def docs():
    return corpus.load("small")


class FakeModels:
    """collapse=True mimics the observed failure: one vector for a whole batch."""

    def __init__(self, collapse=False, always_collapse=False):
        self.collapse, self.always_collapse, self.calls = collapse, always_collapse, 0

    def embed_content(self, model, contents, config=None):
        self.calls += 1
        is_list = isinstance(contents, list)
        n = 1 if (self.always_collapse or (self.collapse and is_list) or not is_list) else len(contents)
        if self.always_collapse and is_list:
            n = 1
        rng = np.random.default_rng(self.calls)
        return types.SimpleNamespace(embeddings=[types.SimpleNamespace(values=list(rng.normal(size=8)))
                                                 for _ in range(n)])


def client(**kw):
    return types.SimpleNamespace(models=FakeModels(**kw))


def test_every_text_document_is_chunked(docs):
    chunks = retrieval.chunk_docs(docs, include_captions=False)
    text_ids = {d.doc_id for d in docs.values() if d.kind == "text"}
    assert {c.doc_id for c in chunks} == text_ids


def test_chunk_sizes_are_bounded(docs):
    for c in retrieval.chunk_docs(docs, include_captions=False):
        assert 0 < len(c.text) <= retrieval.CHUNK_CHARS * 1.5


def test_captions_only_when_requested(docs):
    without = retrieval.chunk_docs(docs, include_captions=False)
    with_caps = retrieval.chunk_docs(docs, include_captions=True)
    assert not any(c.doc_id.startswith("DIAG-") for c in without)
    assert sum(c.doc_id.startswith("DIAG-") for c in with_caps) == 4
    assert len(with_caps) == len(without) + 4


def test_frozen_chunk_count(docs):
    """Regression: the benchmark used 86 text chunks; a chunker change would alter RAG inputs."""
    assert len(retrieval.chunk_docs(docs, include_captions=False)) == 86


def test_index_has_one_vector_per_chunk(docs, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    ix = retrieval.Index(client(), docs, include_captions=True, size="t")
    assert len(ix.vectors) == len(ix.chunks)
    hits = ix.search("carrier rate limit", 8)
    assert len(hits) == 8 and all(h[0].doc_id in docs for h in hits)


def test_collapsed_batch_falls_back_to_per_text_calls(docs, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    ix = retrieval.Index(client(collapse=True), docs, include_captions=False, size="t")
    assert len(ix.vectors) == len(ix.chunks) == 86


def test_wrong_size_cache_is_rebuilt(docs, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    first = retrieval.Index(client(), docs, include_captions=False, size="t")
    cache = next((tmp_path / "results" / "index").glob("*.npz"))
    np.savez(cache, v=np.ones((2, 8), dtype=np.float32))     # the pilot's broken shape
    again = retrieval.Index(client(), docs, include_captions=False, size="t")
    assert len(again.vectors) == len(first.chunks)


def test_unrecoverable_mismatch_raises(docs, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    c = client()
    c.models.embed_content = lambda model, contents, config=None: types.SimpleNamespace(embeddings=[])
    with pytest.raises((RuntimeError, IndexError)):
        retrieval.Index(c, docs, include_captions=False, size="t")
