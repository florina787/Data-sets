"""Retriever: vector search + light lexical re-ranking + document targeting."""

from __future__ import annotations

import logging

from app.models.domain import RetrievedChunk
from app.rag.text_utils import content_tokens, overlap_score
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

_GENERIC_TITLE_WORDS = {"document", "doc", "report", "note", "notes", "the", "file"}


class Retriever:
    """Semantic retrieval with provenance-preserving results."""

    def __init__(self, store: VectorStore, default_top_k: int = 5, min_score: float = 0.12) -> None:
        self._store = store
        self.default_top_k = default_top_k
        self.min_score = min_score

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Return the most relevant chunks for ``query``.

        Over-fetches candidates from the vector store and re-ranks them with a
        hybrid score (vector similarity + keyword overlap on section/title/text),
        which makes results robust for short enterprise queries. ``min_score``
        applies to the hybrid score, so off-topic questions return no evidence.
        """
        k = top_k or self.default_top_k
        candidates = self._store.query(query, top_k=k * 3)
        if not candidates:
            return []

        def hybrid(chunk: RetrievedChunk) -> float:
            lexical = overlap_score(query, f"{chunk.title} {chunk.section} {chunk.text}")
            title_boost = overlap_score(query, chunk.title)
            return 0.7 * chunk.score + 0.3 * lexical + 0.1 * title_boost

        scored = sorted(((hybrid(c), c) for c in candidates), key=lambda x: x[0], reverse=True)
        results = [c for score, c in scored if score >= self.min_score][:k]
        logger.debug("Retrieved %d/%d chunks for query=%r", len(results), len(candidates), query[:80])
        return results

    def find_target_document(self, query: str) -> str | None:
        """Return the document a query explicitly refers to (e.g. 'the architecture document')."""
        query_tokens = content_tokens(query) - _GENERIC_TITLE_WORDS
        best_id, best_hits = None, 0
        for doc in self._store.list_documents():
            title_tokens = content_tokens(f"{doc['title']} {doc['filename'].replace('_', ' ')}")
            hits = len(query_tokens & (title_tokens - _GENERIC_TITLE_WORDS))
            if hits > best_hits:
                best_id, best_hits = doc["document_id"], hits
        return best_id

    def get_document(self, document_id: str) -> list[RetrievedChunk]:
        return self._store.get_document_chunks(document_id)
