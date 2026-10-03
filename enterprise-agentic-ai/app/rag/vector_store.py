"""ChromaDB-backed vector store with explicit, provider-controlled embeddings."""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.models.domain import RetrievedChunk
from app.rag.chunker import Chunk
from app.rag.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class VectorStore:
    """Persistent Chroma collection storing chunk embeddings and provenance metadata.

    The collection name includes the embedding model name so switching
    embedding backends never mixes vectors of different dimensions.
    """

    def __init__(self, persist_dir: Path, collection_name: str, embedding: EmbeddingModel) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._embedding = embedding
        self._lock = threading.Lock()
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )
        safe_model = re.sub(r"[^a-zA-Z0-9_-]+", "-", embedding.name)
        self.collection_name = f"{collection_name}_{safe_model}"[:60]
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=None,  # embeddings are always supplied explicitly
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store ready (collection=%s, chunks=%d)", self.collection_name, self.count())

    @property
    def embedding_name(self) -> str:
        return self._embedding.name

    def count(self) -> int:
        return self._collection.count()

    def document_hash(self, document_id: str) -> str | None:
        """Content hash of an indexed document, or ``None`` if not indexed."""
        result = self._collection.get(where={"document_id": document_id}, limit=1, include=["metadatas"])
        metadatas = result.get("metadatas") or []
        return str(metadatas[0].get("content_hash")) if metadatas else None

    def upsert_chunks(self, document_id: str, chunks: list[Chunk]) -> int:
        """Replace all chunks of ``document_id`` with ``chunks``."""
        with self._lock:
            self._collection.delete(where={"document_id": document_id})
            if not chunks:
                return 0
            embeddings = self._embedding.embed_documents([c.text for c in chunks])
            self._collection.add(
                ids=[c.chunk_id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[c.metadata for c in chunks],
                embeddings=embeddings,
            )
        return len(chunks)

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            self._collection.delete(where={"document_id": document_id})

    def query(self, text: str, top_k: int, where: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        """Semantic search returning chunks ordered by similarity (highest first)."""
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[self._embedding.embed_query(text)],
            n_results=min(top_k, self.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        chunks: list[RetrievedChunk] = []
        for doc, meta, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            chunks.append(_to_chunk(doc, meta, score=max(0.0, 1.0 - float(distance))))
        return chunks

    def get_document_chunks(self, document_id: str) -> list[RetrievedChunk]:
        """All chunks of a document in reading order (used for summarisation)."""
        result = self._collection.get(where={"document_id": document_id}, include=["documents", "metadatas"])
        chunks = [_to_chunk(d, m, score=1.0) for d, m in zip(result["documents"], result["metadatas"], strict=True)]
        return sorted(chunks, key=lambda c: c.chunk_index)

    def list_documents(self) -> list[dict[str, Any]]:
        """Indexed documents with chunk counts."""
        result = self._collection.get(include=["metadatas"])
        docs: dict[str, dict[str, Any]] = {}
        for meta in result.get("metadatas") or []:
            doc_id = str(meta["document_id"])
            entry = docs.setdefault(
                doc_id,
                {"document_id": doc_id, "filename": meta["filename"], "title": meta.get("title", ""), "chunks": 0},
            )
            entry["chunks"] += 1
        return sorted(docs.values(), key=lambda d: d["filename"])


def _to_chunk(text: str, meta: dict[str, Any], score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(meta["chunk_id"]),
        document_id=str(meta["document_id"]),
        filename=str(meta["filename"]),
        title=str(meta.get("title", "")),
        section=str(meta.get("section", "")),
        chunk_index=int(meta.get("chunk_index", 0)),
        text=text,
        score=round(score, 4),
    )
