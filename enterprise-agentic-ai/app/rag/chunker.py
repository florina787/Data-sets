"""Section-aware document chunking.

Markdown headings are used to keep each chunk inside one section (so a citation
can name the section), then long sections are split with LangChain's
``RecursiveCharacterTextSplitter`` using the configured size and overlap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loader import LoadedDocument

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_DISCLAIMER_RE = re.compile(r"^>\s*SYNTHETIC DATA", re.IGNORECASE)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    filename: str
    title: str
    section: str
    chunk_index: int
    text: str
    content_hash: str

    @property
    def metadata(self) -> dict[str, str | int]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "title": self.title,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "content_hash": self.content_hash,
        }


def _split_sections(text: str, default_section: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = default_section
    buffer: list[str] = []
    for line in text.splitlines():
        if _DISCLAIMER_RE.match(line.strip()):
            continue  # the synthetic-data banner is not evidence
        match = _HEADING_RE.match(line.strip())
        if match:
            if any(b.strip() for b in buffer):
                sections.append((current_heading, "\n".join(buffer).strip()))
            current_heading = match.group(2).strip()
            buffer = []
        else:
            buffer.append(line)
    if any(b.strip() for b in buffer):
        sections.append((current_heading, "\n".join(buffer).strip()))
    return sections


def chunk_document(doc: LoadedDocument, chunk_size: int = 800, chunk_overlap: int = 120) -> list[Chunk]:
    """Split a document into overlapping, section-labelled chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n- ", "\n", ". ", " ", ""],
    )
    chunks: list[Chunk] = []
    for section, body in _split_sections(doc.text, default_section=doc.title):
        for piece in splitter.split_text(body):
            piece = piece.strip()
            if len(piece) < 20:
                continue
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.document_id}#c{index:03d}",
                    document_id=doc.document_id,
                    filename=doc.filename,
                    title=doc.title,
                    section=section,
                    chunk_index=index,
                    # Prefix the section heading so it contributes to retrieval.
                    text=f"{section}\n{piece}" if section != doc.title else piece,
                    content_hash=doc.content_hash,
                )
            )
    return chunks
