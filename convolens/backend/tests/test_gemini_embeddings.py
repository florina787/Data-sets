"""Gemini embedding encoder: cache reuse, request caps and the customer-only semantic index (no network)."""
from types import SimpleNamespace

import numpy as np
import pytest

from app.retrieval import index as retrieval
from app.retrieval.gemini_embed import GeminiEncoder


class FakeEmbeddings:
    def __init__(self):
        self.calls: list[list[str]] = []

    def create(self, model, input, dimensions):
        self.calls.append(list(input))
        # Deterministic bag-of-letters vectors so similar words land close together.
        data = []
        for t in input:
            v = np.zeros(dimensions, dtype="float32")
            for ch in t.lower():
                v[ord(ch) % dimensions] += 1
            data.append(SimpleNamespace(embedding=v.tolist()))
        return SimpleNamespace(data=data)


def _encoder(max_requests=1000):
    enc = GeminiEncoder(max_requests=max_requests)
    enc.batch = 3
    fake = FakeEmbeddings()
    enc._client = SimpleNamespace(embeddings=fake)
    return enc, fake


def test_cache_means_each_text_is_embedded_once(demo_ids):
    enc, fake = _encoder()
    texts = [f"parcel number {i} never arrived" for i in range(7)]
    v1 = enc.encode(texts)
    assert v1.shape == (7, enc.dims)
    assert np.allclose(np.linalg.norm(v1, axis=1), 1, atol=1e-5)
    assert sum(len(c) for c in fake.calls) == 7 and max(len(c) for c in fake.calls) <= 3
    enc2, fake2 = _encoder()
    assert np.allclose(enc2.encode(texts), v1) and fake2.calls == []


def test_cap_refuses_instead_of_draining_quota(demo_ids):
    enc, fake = _encoder(max_requests=2)
    with pytest.raises(RuntimeError, match="GEMINI_EMBEDDING_MAX_REQUESTS"):
        enc.encode(["refund one", "refund two", "refund three"])
    assert fake.calls == []
    r = enc.fill(["refund one", "refund two", "refund three"], max_requests=2)
    assert r["embedded"] == 2 and r["remaining"] == 1


def test_semantic_index_covers_customer_messages_only(demo_ids, monkeypatch):
    from app.db import session_scope
    enc, _ = _encoder(max_requests=100000)
    monkeypatch.setattr(retrieval, "get_encoder", lambda: enc)
    retrieval.invalidate()
    try:
        with session_scope() as db:
            idx = retrieval.get_index(db, demo_ids["demo"])
            assert idx.faiss_index is not None and idx.sem_pos is not None
            assert 0 < len(idx.sem_pos) < len(idx.texts)
            res = retrieval.search(db, demo_ids["demo"], "refund still not received", k=5)
        assert "semantic_faiss" in res["methods_used"]
        assert all(h["role"] == "customer" for h in res["hits"])
    finally:
        retrieval.invalidate()
