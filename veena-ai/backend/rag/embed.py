"""Local embeddings with sentence-transformers, plus an in-memory cache."""

from __future__ import annotations

import hashlib
import os
import sys
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
BUNDLED_DIR = "all-MiniLM-L6-v2"


def bundled_model_path() -> Path | None:
    """The embedding model shipped inside the installer (Apache-2.0, about 90 MB),
    so document search never needs a download. VEENA_EMBEDDER_PATH overrides."""
    candidates = [os.environ.get("VEENA_EMBEDDER_PATH")]
    if getattr(sys, "frozen", False):
        candidates.append(str(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "models" / BUNDLED_DIR))
    for c in candidates:
        if c and (Path(c) / "modules.json").is_file():
            return Path(c)
    return None


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

                bundled = bundled_model_path() if self.model_name == DEFAULT_MODEL else None
                if bundled is not None:
                    self._model = SentenceTransformer(str(bundled), device="cpu", local_files_only=True)
                    return self._model
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
