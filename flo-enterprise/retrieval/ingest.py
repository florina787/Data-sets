"""Document ingestion pipeline:
validation (malware/file checks) -> parsing -> classification -> metadata extraction -> chunking -> injection screening
-> embedding -> keyword indexing (BM25 built at query time from chunks) -> ACL metadata persisted with every document."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import ROOT
from backend.db import models as m
from privacy.detect import contains_pii
from retrieval import embed as emb
from retrieval.injection import scan_text
from retrieval.language import detect_language
from retrieval.parse import chunk, parse_bytes
from retrieval.validate import scan

CORPUS = ROOT / "data" / "documents"
REQUIRED_META = ("id", "title", "owner", "version", "classification", "tenant", "access_groups", "effective_date", "jurisdiction")


class IngestError(Exception):
    pass


def _d(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def ingest_bytes(s: Session, filename: str, data: bytes, meta: dict | None = None, source: str = "upload") -> m.Document:
    res = scan(filename, data)
    if not res.ok:
        raise IngestError(f"rejected: {res.reason}")
    fm, sections = parse_bytes(filename, data)
    meta = {**fm, **(meta or {})}
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise IngestError(f"missing required metadata: {missing}")
    full = "\n".join(t for _, t in sections)
    classification = meta["classification"]
    if classification == "public" and contains_pii(full):
        classification = "confidential"  # auto-upgrade: public documents may not contain personal information
    inj = scan_text(full)
    status = "quarantined" if inj["severity"] == "high" else "active"
    doc = m.Document(id=meta["id"], tenant_id=meta["tenant"], title=meta["title"], source=source, owner=meta["owner"],
                     version=str(meta["version"]), classification=classification, access_groups=list(meta["access_groups"]),
                     effective_date=_d(meta["effective_date"]), expiry_date=_d(meta.get("expiry_date")),
                     jurisdiction=meta["jurisdiction"], language=meta.get("language") or detect_language(full),
                     doc_type=meta.get("doc_type", "document"), sha256=hashlib.sha256(data).hexdigest(), status=status,
                     injection_flags=inj["hits"], ingested_at=datetime.now(timezone.utc).replace(tzinfo=None))
    doc = s.merge(doc)
    s.query(m.DocChunk).filter(m.DocChunk.document_id == doc.id).delete()
    vecs = []
    for i, (sec, text) in enumerate(chunk(sections)):
        v = emb.embed(f"{doc.title} {sec} {text}")
        s.add(m.DocChunk(id=f"{doc.id}#{i}", document_id=doc.id, ordinal=i, section=sec[:200], text=text, embedding=v))
        vecs.append((f"{doc.id}#{i}", v))
    s.flush()
    from retrieval.vectorstore import write_vectors
    write_vectors(s, vecs)
    from retrieval.search import invalidate_index
    invalidate_index()
    return doc


def ingest_corpus(s: Session, directory: Path = CORPUS) -> list[str]:
    out = []
    for p in sorted(directory.glob("*.md")):
        d = ingest_bytes(s, p.name, p.read_bytes(), source=f"repo:data/documents/{p.name}")
        out.append(f"{d.id}:{d.status}")
    return out
