"""Local embeddings with sentence-transformers, plus an in-memory cache."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    """Weights download once from Hugging Face (free) and are cached locally."""

    def __init__(self, model_name: str = DEFAULT_MODEL, cache_size: int = 4096):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._cache_size = cache_size
        self.cache_hits = 0

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                try:
                    # Cached weights load without touching the network (offline use).
                    self._model = SentenceTransformer(self.model_name, device="cpu", local_files_only=True)
                except Exception:  # noqa: BLE001 - first run: download once
                    self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    @property
    def dim(self) -> int:
        m = self._load()
        get_dim = getattr(m, "get_embedding_dimension", None) or m.get_sentence_embedding_dimension
        return int(get_dim())

    def embed(self, texts: list[str]) -> np.ndarray:
        keys = [hashlib.sha1(t.encode(), usedforsecurity=False).hexdigest() for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self._cache]
        if missing:
            vecs = (
                self._load()
                .encode([texts[i] for i in missing], batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
                .astype(np.float32)
            )
            for i, v in zip(missing, vecs):
                self._cache[keys[i]] = v
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
        self.cache_hits += len(texts) - len(missing)
        out = np.stack([self._cache[k] for k in keys]) if keys else np.zeros((0, 0), np.float32)
        for k in keys:
            self._cache.move_to_end(k)
        return out
