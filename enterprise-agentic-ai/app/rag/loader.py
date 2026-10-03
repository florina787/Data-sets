"""Load documents from disk into a normalised in-memory representation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".md", ".txt", ".pdf"})


class DocumentLoadError(ValueError):
    """Raised when a document cannot be read or is unsupported."""


@dataclass(frozen=True)
class LoadedDocument:
    document_id: str
    filename: str
    title: str
    text: str
    content_hash: str


def make_document_id(filename: str) -> str:
    """Stable, human-readable document ID derived from the filename."""
    stem = Path(filename).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return slug or "document"


def _read_pdf(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def load_bytes(filename: str, data: bytes) -> LoadedDocument:
    """Parse raw bytes of an uploaded or on-disk document."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentLoadError(
            f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    try:
        text = _read_pdf(data) if suffix == ".pdf" else data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentLoadError("Text documents must be UTF-8 encoded.") from exc
    except Exception as exc:  # pypdf raises a variety of errors on malformed files
        raise DocumentLoadError(f"Could not parse PDF: {type(exc).__name__}") from exc

    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise DocumentLoadError("Document is empty or contains no extractable text.")

    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(filename).stem.replace("_", " ").title()
    return LoadedDocument(
        document_id=make_document_id(filename),
        filename=Path(filename).name,
        title=title,
        text=text,
        content_hash=hashlib.sha256(data).hexdigest()[:16],
    )


def load_file(path: Path) -> LoadedDocument:
    """Load a document from the filesystem."""
    return load_bytes(path.name, path.read_bytes())
