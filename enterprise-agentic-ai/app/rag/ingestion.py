"""Document ingestion: load -> chunk -> embed -> store."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.rag.chunker import chunk_document
from app.rag.loader import SUPPORTED_EXTENSIONS, LoadedDocument, load_bytes, load_file
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    filename: str
    chunks_indexed: int
    replaced_existing: bool
    skipped_unchanged: bool = False


class IngestionService:
    """Indexes documents into the vector store, skipping unchanged content."""

    def __init__(self, store: VectorStore, chunk_size: int, chunk_overlap: int) -> None:
        self._store = store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def ingest_document(self, doc: LoadedDocument, *, force: bool = False) -> IngestionResult:
        existing_hash = self._store.document_hash(doc.document_id)
        if existing_hash == doc.content_hash and not force:
            return IngestionResult(doc.document_id, doc.filename, 0, False, skipped_unchanged=True)
        chunks = chunk_document(doc, self._chunk_size, self._chunk_overlap)
        count = self._store.upsert_chunks(doc.document_id, chunks)
        logger.info("Indexed %s (%d chunks)", doc.filename, count)
        return IngestionResult(doc.document_id, doc.filename, count, replaced_existing=existing_hash is not None)

    def ingest_bytes(self, filename: str, data: bytes) -> IngestionResult:
        return self.ingest_document(load_bytes(filename, data), force=True)

    def ingest_directory(self, directory: Path) -> list[IngestionResult]:
        """Index every supported file in ``directory`` (non-recursive)."""
        if not directory.exists():
            logger.warning("Document directory %s does not exist; nothing to ingest.", directory)
            return []
        results: list[IngestionResult] = []
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    results.append(self.ingest_document(load_file(path)))
                except Exception:
                    logger.exception("Failed to ingest %s", path.name)
        return results
