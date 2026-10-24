"""Document intelligence: upload -> validate -> extract -> clean -> chunk -> embed -> index -> retrieve -> rerank."""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass

from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlmodel import col, select

from ..memory.db import session as db_session
from ..memory.tables import Chunk, Collection, Document
from ..security.paths import check_extension, sanitize_filename
from .chunk import chunk_pages
from .embed import Embedder
from .extract import clean, extract
from .index import VectorIndex

COLLECTION_KINDS = ("resume", "project", "docs", "job", "meeting", "general")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.]*")
_STOP = set("the a an and or of to in on for with is are was were be by as at it this that from how what why which who".split())


@dataclass
class Evidence:
    n: int
    chunk_id: int
    document_id: str
    collection_id: str
    filename: str
    page: int | None
    score: float
    vector_score: float
    lexical_score: float
    text: str

    def citation(self) -> dict:
        d = asdict(self)
        d["snippet"] = d.pop("text")[:400]
        return d


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def lexical_score(query: str, text: str) -> float:
    q = set(_tokens(query))
    if not q:
        return 0.0
    tf = Counter(_tokens(text))
    hit = sum(1 + math.log(tf[t]) for t in q if tf[t])
    return min(1.0, hit / (len(q) * 1.5))


class KnowledgeBase:
    # Relevance floor on the cosine score, calibrated for all-MiniLM-L6-v2:
    # measured unrelated queries peak near 0.11, paraphrased matches start
    # near 0.25. A strong keyword match also qualifies a passage.
    min_score = 0.2
    min_lexical = 0.5

    def __init__(self, engine: Engine, embedder: Embedder, index: VectorIndex, max_bytes: int):
        self.engine = engine
        self.embedder = embedder
        self.index = index
        self.max_bytes = max_bytes

    # ---------- collections ----------
    def create_collection(self, name: str, kind: str = "general") -> Collection:
        if kind not in COLLECTION_KINDS:
            raise ValueError(f"kind must be one of {COLLECTION_KINDS}")
        with db_session(self.engine) as s:
            c = Collection(name=name.strip()[:120] or "Untitled", kind=kind)
            s.add(c)
            s.commit()
            s.refresh(c)
            return c

    def list_collections(self) -> list[dict]:
        with db_session(self.engine) as s:
            cols = list(s.exec(select(Collection).order_by(Collection.created_at)))
            docs = list(s.exec(select(Document)))
        out = []
        for c in cols:
            ds = [d for d in docs if d.collection_id == c.id]
            out.append(
                {
                    **c.model_dump(mode="json"),
                    "documents": [d.model_dump(mode="json") for d in ds],
                    "chunk_count": sum(d.chunk_count for d in ds),
                }
            )
        return out

    def get_collection(self, collection_id: str) -> Collection | None:
        with db_session(self.engine) as s:
            return s.get(Collection, collection_id)

    def delete_collection(self, collection_id: str) -> bool:
        with db_session(self.engine) as s:
            c = s.get(Collection, collection_id)
            if not c:
                return False
            s.exec(delete(Chunk).where(Chunk.collection_id == collection_id))
            s.exec(delete(Document).where(Document.collection_id == collection_id))
            s.delete(c)
            s.commit()
        self.index.drop(collection_id)
        return True

    def delete_document(self, document_id: str) -> bool:
        with db_session(self.engine) as s:
            d = s.get(Document, document_id)
            if not d:
                return False
            ids = list(s.exec(select(Chunk.id).where(Chunk.document_id == document_id)))
            s.exec(delete(Chunk).where(Chunk.document_id == document_id))
            s.delete(d)
            s.commit()
        if ids:
            self.index.remove(d.collection_id, ids)
        return True

    # ---------- ingestion ----------
    def ingest(self, collection_id: str, filename: str, data: bytes) -> dict:
        t0 = time.perf_counter()
        if not self.get_collection(collection_id):
            raise LookupError("collection not found")
        name = sanitize_filename(filename)
        ext = check_extension(name)
        if not data:
            raise ValueError("file is empty")
        if len(data) > self.max_bytes:
            raise ValueError(f"file exceeds {self.max_bytes // 2**20} MB limit")
        sha = hashlib.sha256(data).hexdigest()
        with db_session(self.engine) as s:
            existing = s.exec(select(Document).where(Document.collection_id == collection_id, Document.sha256 == sha)).first()
            if existing:
                return {"document": existing.model_dump(mode="json"), "duplicate": True}
        pages = extract(data, ext)
        pages = [type(p)(p.number, clean(p.text)) for p in pages]
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("no extractable text (scanned PDFs need OCR before upload)")
        vectors = self.embedder.embed([c.text for c in chunks])
        with db_session(self.engine) as s:
            doc = Document(
                collection_id=collection_id,
                filename=name,
                ext=ext,
                sha256=sha,
                pages=sum(1 for p in pages if p.number) or 1,
                chunk_count=len(chunks),
                char_count=sum(len(p.text) for p in pages),
            )
            s.add(doc)
            s.flush()
            rows = [Chunk(document_id=doc.id, collection_id=collection_id, page=c.page, ordinal=c.ordinal, text=c.text) for c in chunks]
            s.add_all(rows)
            s.flush()
            ids = [r.id for r in rows]
            try:
                self.index.add(collection_id, ids, vectors)
            except Exception:
                s.rollback()
                raise
            s.commit()
            s.refresh(doc)
        return {
            "document": doc.model_dump(mode="json"),
            "duplicate": False,
            "chunks": len(chunks),
            "ingest_ms": (time.perf_counter() - t0) * 1000,
        }

    # ---------- retrieval ----------
    def search(self, query: str, collection_ids: list[str] | None = None, k: int = 5, min_score: float | None = None) -> list[Evidence]:
        min_score = self.min_score if min_score is None else min_score
        with db_session(self.engine) as s:
            all_ids = list(s.exec(select(Collection.id)))
        targets = [c for c in (collection_ids or all_ids) if c in all_ids]
        if not targets or not query.strip():
            return []
        qv = self.embedder.embed([query])[0]
        hits: list[tuple[int, float]] = []
        for cid in targets:
            hits += self.index.search(cid, qv, k * 3)
        if not hits:
            return []
        score_by_id = dict(hits)
        with db_session(self.engine) as s:
            rows = list(s.exec(select(Chunk).where(col(Chunk.id).in_(list(score_by_id)))))
            docs = {d.id: d for d in s.exec(select(Document).where(col(Document.id).in_({r.document_id for r in rows})))}
        ranked = []
        for r in rows:
            v = score_by_id[r.id]
            lex = lexical_score(query, r.text)
            ranked.append((0.75 * v + 0.25 * lex, v, lex, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        out: list[Evidence] = []
        for final, v, lex, r in ranked:
            if v < min_score and lex < self.min_lexical:
                continue
            d = docs.get(r.document_id)
            out.append(
                Evidence(
                    n=len(out) + 1,
                    chunk_id=r.id,
                    document_id=r.document_id,
                    collection_id=r.collection_id,
                    filename=d.filename if d else "unknown",
                    page=r.page,
                    score=round(final, 4),
                    vector_score=round(v, 4),
                    lexical_score=round(lex, 4),
                    text=r.text,
                )
            )
            if len(out) >= k:
                break
        return out

    def collection_text(self, collection_id: str, max_chars: int = 6000) -> str:
        """Concatenated text of a small collection (e.g. one resume) for prompts."""
        with db_session(self.engine) as s:
            rows = list(s.exec(select(Chunk).where(Chunk.collection_id == collection_id).order_by(Chunk.document_id, Chunk.ordinal)))
        text, total = [], 0
        for r in rows:
            if total + len(r.text) > max_chars:
                break
            text.append(r.text)
            total += len(r.text)
        return "\n\n".join(text)
