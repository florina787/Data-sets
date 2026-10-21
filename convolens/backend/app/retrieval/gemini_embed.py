"""Gemini embeddings (gemini-embedding-001) behind the same interface as the local sentence-transformer Encoder.

Every vector is cached in SQLite by (model, sha256(text)), so a message is embedded once and reused across datasets,
restarts and re-imports. Remote requests (one per text on the free tier) are capped per process; when a build would exceed the cap the encoder
raises and retrieval reports semantic search as unavailable (keyword search still works) instead of draining quota.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time

import numpy as np
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models.orm import EmbeddingCache

log = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalise(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return (v / np.where(n == 0, 1, n)).astype("float32")


class GeminiEncoder:
    # The free tier counts every input text as one request (100/minute), so only customer messages - the default
    # search target - are embedded. Support replies stay keyword-searchable.
    roles = ("customer",)

    def __init__(self, max_requests: int | None = None):
        s = get_settings()
        self.model = s.gemini_embedding_model
        self.dims = s.gemini_embedding_dims
        self.batch = s.gemini_embedding_batch
        self.max_requests = s.gemini_embedding_max_requests if max_requests is None else max_requests
        self.model_name = f"gemini:{self.model}@{self.dims}"
        self.requests_made = 0
        self.error: str | None = None
        self._client = None
        self._lock = threading.Lock()

    @property
    def _model(self):  # mirrors Encoder._model for semantic_status()
        return self._client

    def available(self) -> bool:
        if self._client is not None:
            return True
        try:
            from openai import OpenAI
            s = get_settings()
            key = s.google_api_key.get_secret_value() if s.google_api_key else "injected-by-egress-proxy"
            if not s.google_api_key and not s.gemini_key_via_proxy:
                raise RuntimeError("No GOOGLE_API_KEY and GEMINI_KEY_VIA_PROXY is false")
            self._client = OpenAI(api_key=key, base_url=s.gemini_base_url, max_retries=0, timeout=60)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {str(exc)[:200]}"
            return False
        return True

    def cached(self, texts: list[str]) -> dict[str, np.ndarray]:
        hashes = list({_hash(t) for t in texts})
        out: dict[str, np.ndarray] = {}
        with session_scope() as db:
            for i in range(0, len(hashes), 500):
                rows = db.execute(select(EmbeddingCache.text_hash, EmbeddingCache.vector).where(
                    EmbeddingCache.model == self.model_name, EmbeddingCache.text_hash.in_(hashes[i:i + 500]))).all()
                out.update({h: np.frombuffer(v, dtype="float32") for h, v in rows})
        return out

    def requests_needed(self, texts: list[str]) -> int:
        return len({_hash(t) for t in texts} - set(self.cached(texts)))

    def fill(self, texts: list[str], max_requests: int | None = None, pace_s: float = 0) -> dict:
        """Embed uncached texts, at most `max_requests` texts (the free tier bills each text as a request).
        `pace_s` sleeps between batches to stay under the per-minute limit. Returns counts; safe to re-run."""
        if not self.available():
            raise RuntimeError(f"Gemini embeddings unavailable: {self.error}")
        have = self.cached(texts)
        todo = list(dict.fromkeys(t for t in texts if _hash(t) not in have))
        budget = self.max_requests - self.requests_made if max_requests is None else max_requests
        done = 0
        for i in range(0, len(todo), self.batch):
            if budget <= 0:
                break
            chunk = todo[i:i + min(self.batch, budget)]
            if pace_s and i:
                time.sleep(pace_s)
            with self._lock:
                resp = self._client.embeddings.create(model=self.model, input=chunk, dimensions=self.dims)
                self.requests_made += len(chunk)
            budget -= len(chunk)
            vecs = _normalise(np.asarray([d.embedding for d in resp.data], dtype="float32"))
            with session_scope() as db:
                for t, v in zip(chunk, vecs):
                    db.merge(EmbeddingCache(model=self.model_name, text_hash=_hash(t), dims=self.dims, vector=v.tobytes()))
            done += len(chunk)
        return {"embedded": done, "cached_before": len(texts) - len(todo), "remaining": len(todo) - done,
                "requests": self.requests_made}

    def encode(self, texts: list[str]) -> np.ndarray:
        need = self.requests_needed(texts)
        if need > self.max_requests - self.requests_made:
            raise RuntimeError(
                f"{need} Gemini embedding requests needed but only {self.max_requests - self.requests_made} allowed "
                f"this run (GEMINI_EMBEDDING_MAX_REQUESTS). Fill the cache with: python -m app.ingestion.cli embed <dataset_id>")
        if need:
            self.fill(texts, max_requests=need)
        have = self.cached(texts)
        return np.stack([have[_hash(t)] for t in texts]).astype("float32")
