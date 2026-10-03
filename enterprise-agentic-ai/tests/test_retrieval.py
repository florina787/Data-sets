"""Chunking, ingestion and retrieval with provenance metadata."""

from __future__ import annotations

from pathlib import Path

from app.rag.chunker import chunk_document
from app.rag.embeddings import HashingEmbedding
from app.rag.ingestion import IngestionService
from app.rag.loader import load_bytes, make_document_id
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore

SAMPLE = b"""# Sample Doc

## Section One
Alpha beta gamma. The quarterly revenue target is 42 million.

## Section Two
Delta epsilon. The migration deadline is next Friday.
"""


def test_document_id_is_stable_slug() -> None:
    assert make_document_id("Project Phoenix Status-Report.md") == "project_phoenix_status_report"


def test_chunker_keeps_section_and_ids() -> None:
    doc = load_bytes("sample.md", SAMPLE)
    chunks = chunk_document(doc, chunk_size=200, chunk_overlap=20)
    assert [c.section for c in chunks] == ["Section One", "Section Two"]
    assert chunks[0].chunk_id == "sample#c000"
    assert all(c.metadata["filename"] == "sample.md" and c.metadata["document_id"] == "sample" for c in chunks)


def test_synthetic_disclaimer_not_indexed() -> None:
    doc = load_bytes("d.md", b"# T\n\n> SYNTHETIC DATA - fictional.\n\n## S\nReal content sentence here.")
    assert all("SYNTHETIC" not in c.text for c in chunk_document(doc))


def test_retrieved_chunks_have_provenance(demo_container) -> None:
    chunks = demo_container.retriever.retrieve("Which issues are blocking the release?", top_k=4)
    assert chunks
    for chunk in chunks:
        assert chunk.filename.endswith(".md")
        assert chunk.document_id
        assert chunk.chunk_id.startswith(chunk.document_id + "#c")
        assert 0.0 <= chunk.score <= 1.0


def test_relevant_document_ranked_high(demo_container) -> None:
    chunks = demo_container.retriever.retrieve("What are the major delivery risks?", top_k=8)
    assert "delivery_risk_report" in {c.document_id for c in chunks[:3]}


def test_off_topic_query_returns_nothing(demo_container) -> None:
    assert demo_container.retriever.retrieve("price of bananas in Tokyo") == []


def test_find_target_document(demo_container) -> None:
    assert demo_container.retriever.find_target_document("Summarize the architecture document") == "ai_platform_architecture_notes"


def test_ingestion_skips_unchanged_and_replaces_changed(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "chroma", "t", HashingEmbedding(dimensions=64))
    service = IngestionService(store, chunk_size=200, chunk_overlap=20)
    first = service.ingest_document(load_bytes("sample.md", SAMPLE))
    again = service.ingest_document(load_bytes("sample.md", SAMPLE))
    changed = service.ingest_bytes("sample.md", SAMPLE + b"\n## Section Three\nNew content about zeta.\n")
    assert first.chunks_indexed == 2 and not first.replaced_existing
    assert again.skipped_unchanged
    assert changed.replaced_existing and changed.chunks_indexed == 3
    assert store.count() == 3

    retriever = Retriever(store, default_top_k=2, min_score=0.0)
    top = retriever.retrieve("revenue target")[0]
    assert top.section == "Section One"
