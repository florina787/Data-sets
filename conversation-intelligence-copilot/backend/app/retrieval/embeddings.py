"""Embedding adapters.

* SentenceTransformerEmbedder: `sentence-transformers/all-MiniLM-L6-v2` (preferred).
  Requires the optional `transformers` extra and network access to Hugging Face
  the first time the weights are fetched.
* LSAEmbedder: TF-IDF (word 1-2 grams) + truncated SVD, fitted locally on the
  corpus. Fully offline. Used automatically when the transformer model cannot be
  loaded; the active backend is reported by /api/retrieval/status and stored in
  the index manifest.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str
    dim: int

    def fit(self, texts: list[str]) -> None: ...
    def encode(self, texts: list[str]) -> np.ndarray: ...
    def save(self, path: Path) -> None: ...


def _normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (x / norms).astype("float32")


class LSAEmbedder:
    def __init__(self, dim: int = 192):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, lowercase=True)
        self.svd = TruncatedSVD(n_components=dim, random_state=7)
        self.dim = dim
        self.name = f"lsa-tfidf-svd{dim}"

    def fit(self, texts: list[str]) -> None:
        x = self.vectorizer.fit_transform(texts)
        n_comp = min(self.dim, x.shape[1] - 1, x.shape[0] - 1)
        if n_comp < self.dim:
            from sklearn.decomposition import TruncatedSVD

            self.svd = TruncatedSVD(n_components=max(2, n_comp), random_state=7)
            self.dim = self.svd.n_components
            self.name = f"lsa-tfidf-svd{self.dim}"
        self.svd.fit(x)

    def encode(self, texts: list[str]) -> np.ndarray:
        return _normalize(self.svd.transform(self.vectorizer.transform(texts)))

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "svd": self.svd, "dim": self.dim, "name": self.name}, f)

    @classmethod
    def load(cls, path: Path) -> "LSAEmbedder":
        with open(path, "rb") as f:
            d = pickle.load(f)  # noqa: S301 - file is produced locally by build_embeddings
        e = cls.__new__(cls)
        e.vectorizer, e.svd, e.dim, e.name = d["vectorizer"], d["svd"], d["dim"], d["name"]
        return e


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.model = SentenceTransformer(model_name)
        self.dim = int(self.model.get_sentence_embedding_dimension())
        self.name = model_name

    def fit(self, texts: list[str]) -> None:  # pretrained: nothing to fit
        return None

    def encode(self, texts: list[str]) -> np.ndarray:
        return _normalize(np.asarray(self.model.encode(texts, batch_size=64, show_progress_bar=False)))

    def save(self, path: Path) -> None:
        path.write_text(self.name)


def create_embedder(backend: str, model_name: str) -> tuple[Embedder, str | None]:
    """Return (embedder, fallback_reason)."""
    if backend in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerEmbedder(model_name), None
        except Exception as e:  # noqa: BLE001 - import or download failure
            reason = f"{model_name} unavailable ({type(e).__name__}: {str(e)[:160]}); using local LSA embeddings"
            if backend == "sentence-transformers":
                raise RuntimeError(reason) from e
            log.warning(reason)
            return LSAEmbedder(), reason
    return LSAEmbedder(), None


def load_embedder(path: Path, kind: str) -> Embedder:
    if kind == "lsa":
        return LSAEmbedder.load(path)
    return SentenceTransformerEmbedder(path.read_text().strip())
