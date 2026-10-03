"""Embedding backends.

* ``SentenceTransformerEmbedding`` — real semantic embeddings (default).
* ``HashingEmbedding`` — a dependency-free lexical fallback (hashed bag of
  stemmed words and bigrams). It is used for tests and offline environments.
  It is *not* semantic, so the active backend is always reported through
  ``/health`` and the UI instead of being swapped in silently.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Protocol

from app.config.settings import EmbeddingProvider, Settings
from app.rag.text_utils import tokenize

logger = logging.getLogger(__name__)


class EmbeddingModel(Protocol):
    """Interface used by the vector store."""

    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashingEmbedding:
    """Deterministic feature-hashing embedding (lexical, offline, fast)."""

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions
        self.name = f"hashing-{dimensions}"

    def _bucket(self, feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "little")
        return value % self.dimensions, 1.0 if (value >> 63) & 1 else -1.0

    def _embed(self, text: str) -> list[float]:
        tokens = tokenize(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        vector = [0.0] * self.dimensions
        counts: dict[str, int] = {}
        for feat in features:
            counts[feat] = counts.get(feat, 0) + 1
        for feat, count in counts.items():
            idx, sign = self._bucket(feat)
            weight = 1.0 + math.log(count)
            vector[idx] += sign * weight * (0.6 if "_" in feat else 1.0)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbedding:
    """Semantic embeddings from a local sentence-transformers model."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, lazy

        self._model = SentenceTransformer(model_name)
        self.name = model_name.split("/")[-1]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@dataclass(frozen=True)
class EmbeddingSelection:
    model: EmbeddingModel
    fallback_reason: str | None = None


def build_embedding_model(settings: Settings) -> EmbeddingSelection:
    """Create the configured embedding model, falling back *visibly* if unavailable."""
    if settings.embedding_provider is EmbeddingProvider.HASHING:
        return EmbeddingSelection(HashingEmbedding())
    try:
        return EmbeddingSelection(SentenceTransformerEmbedding(settings.embedding_model))
    except Exception as exc:  # ImportError, network errors while downloading the model, ...
        reason = (
            f"sentence-transformers model '{settings.embedding_model}' unavailable "
            f"({type(exc).__name__}); using lexical hashing embeddings instead."
        )
        logger.warning(reason)
        return EmbeddingSelection(HashingEmbedding(), fallback_reason=reason)
