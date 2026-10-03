"""RAG agent: retrieves evidence chunks (with filename, document ID and chunk ID)."""

from __future__ import annotations

from typing import Any

from app.graph.state import CopilotState
from app.models.domain import Intent
from app.rag.retriever import Retriever

_MAX_SUMMARY_CHUNKS = 14
_BROAD_INTENTS = {Intent.RISK_ANALYSIS, Intent.COMPARISON, Intent.ACTION_PLANNING}


class RAGAgent:
    """Retrieves evidence from the vector store.

    Summarisation requests that name a document ("the architecture document")
    load that whole document in reading order; other requests use semantic
    top-k retrieval (with a wider k for analytical intents).
    """

    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def __call__(self, state: CopilotState) -> dict[str, Any]:
        query = state["user_query"]
        intent = state.get("intent", Intent.GENERAL_QA)
        top_k = state.get("top_k") or self._retriever.default_top_k

        if intent is Intent.SUMMARIZATION:
            target = self._retriever.find_target_document(query)
            if target:
                chunks = self._retriever.get_document(target)[:_MAX_SUMMARY_CHUNKS]
                return {
                    "retrieved_documents": chunks,
                    "_detail": f"loaded {len(chunks)} chunks of '{target}' for summarisation",
                }

        k = top_k + 3 if intent in _BROAD_INTENTS else top_k
        chunks = self._retriever.retrieve(query, top_k=k)
        documents = sorted({c.filename for c in chunks})
        return {
            "retrieved_documents": chunks,
            "_detail": f"retrieved {len(chunks)} chunks from {len(documents)} documents",
        }
