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
    weak: bool = False  # below the relevance floor; shown/used only as lower-confidence context

    def citation(self) -> dict:
        d = asdict(self)
        d["snippet"] = d.pop("text")[:400]
        return d


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


# Query expansion for the KEYWORD signal only: questions use different words than documents
# ("most recent role" vs "Lead Engineer ... to Present"). Never changes the semantic query.
_EXPAND: dict[str, tuple[str, ...]] = {
    "experience": ("experience", "years", "worked", "present", "since"),
    "years": ("years", "experience", "present", "since"),
    "role": ("engineer", "developer", "manager", "lead", "analyst", "scientist", "consultant", "position", "title", "present"),
    "recent": ("present", "current", "now"),
    "current": ("present", "current", "now"),
    "companies": ("ltd", "inc", "llc", "gmbh", "plc", "corp", "company", "employer"),
    "company": ("ltd", "inc", "llc", "gmbh", "plc", "corp", "employer"),
    "employers": ("ltd", "inc", "llc", "gmbh", "plc", "corp", "company"),
    "worked": ("experience", "present", "ltd", "inc"),
    "languages": (
        "python",
        "java",
        "javascript",
        "typescript",
        "c++",
        "c#",
        "go",
        "rust",
        "sql",
        "kotlin",
        "swift",
        "ruby",
        "php",
        "scala",
        "r",
    ),
    "programming": ("python", "java", "javascript", "typescript", "c++", "go", "rust", "sql"),
    "skills": ("skills", "proficient", "tools", "technologies"),
    "ai": ("ai", "ml", "llm", "llms", "rag", "nlp", "pytorch", "tensorflow", "embeddings", "machine", "learning"),
    "education": ("education", "degree", "university", "msc", "bsc", "phd", "college"),
    "degree": ("degree", "university", "msc", "bsc", "phd", "ba", "ma"),
}


def expand_query(query: str) -> str:
    extra = [w for t in _tokens(query) for w in _EXPAND.get(t, ())]
    return query + (" " + " ".join(extra) if extra else "")


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
    # Below these, a candidate is unrelated (measured unrelated queries peak near 0.11).
    weak_vector = 0.12
    weak_lexical = 0.15
    # In collections this small every passage is compared (not just the nearest k*3), so a resume
    # question is never missed because of candidate truncation.
    small_collection_chunks = 24

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
    def search(
        self, query: str, collection_ids: list[str] | None = None, k: int = 5, min_score: float | None = None, include_weak: bool = False
    ) -> list[Evidence]:
        return self.search_with_diagnostics(query, collection_ids, k, min_score, include_weak)[0]

    def search_with_diagnostics(
        self, query: str, collection_ids: list[str] | None = None, k: int = 5, min_score: float | None = None, include_weak: bool = False
    ) -> tuple[list[Evidence], dict]:
        """Hybrid retrieval. Strong matches pass the relevance floor (semantic) or a strong keyword match.
        With include_weak, weaker candidates that still share meaning or keywords fill the remaining
        slots, flagged weak=True; in a small collection every passage is compared. Diagnostics explain what was kept and rejected."""
        min_score = self.min_score if min_score is None else min_score
        diag: dict = {
            "floor": min_score,
            "candidates": 0,
            "strong": 0,
            "weak": 0,
            "rejected": 0,
            "best_vector": None,
            "best_lexical": None,
            "small_collection_mode": False,
            "indexed_passages": 0,
            "reason": None,
        }
        with db_session(self.engine) as s:
            all_ids = list(s.exec(select(Collection.id)))
        targets = [c for c in (collection_ids or all_ids) if c in all_ids]
        if not targets or not query.strip():
            diag["reason"] = "no collection selected" if not targets else "empty query"
            return [], diag
        total = sum(self.index.count(c) for c in targets)
        diag["indexed_passages"] = total
        if total == 0:
            diag["reason"] = "the selected collections have no indexed passages; re-index or add documents"
            return [], diag
        small = total <= self.small_collection_chunks
        diag["small_collection_mode"] = small
        qv = self.embedder.embed([query])[0]
        hits: list[tuple[int, float]] = []
        for cid in targets:
            hits += self.index.search(cid, qv, max(k * 3, self.small_collection_chunks if small else 0))
        if not hits:
            diag["reason"] = "the vector index returned no candidates; re-index this collection"
            return [], diag
        score_by_id = dict(hits)
        with db_session(self.engine) as s:
            rows = list(s.exec(select(Chunk).where(col(Chunk.id).in_(list(score_by_id)))))
            docs = {d.id: d for d in s.exec(select(Document).where(col(Document.id).in_({r.document_id for r in rows})))}
        lexq = expand_query(query)
        ranked = []
        for r in rows:
            v = score_by_id[r.id]
            lex = max(lexical_score(query, r.text), 0.8 * lexical_score(lexq, r.text))
            ranked.append((0.75 * v + 0.25 * lex, v, lex, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        diag["candidates"] = len(ranked)
        diag["best_vector"] = round(max(x[1] for x in ranked), 4)
        diag["best_lexical"] = round(max(x[2] for x in ranked), 4)
        strong, weak = [], []
        for item in ranked:
            _, v, lex, _ = item
            if v >= min_score or lex >= self.min_lexical:
                strong.append(item)
            elif v >= self.weak_vector or lex >= self.weak_lexical:
                weak.append(item)
            else:
                diag["rejected"] += 1
        chosen = [(x, False) for x in strong[:k]]
        if include_weak:
            chosen += [(x, True) for x in weak[: max(0, k - len(chosen))]]
        else:
            diag["rejected"] += len(weak)
        out: list[Evidence] = []
        for (final, v, lex, r), is_weak in chosen:
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
                    weak=is_weak,
                )
            )
        diag["strong"] = sum(1 for e in out if not e.weak)
        diag["weak"] = sum(1 for e in out if e.weak)
        if not out:
            diag["reason"] = (
                f"{diag['candidates']} passage(s) were compared; none reached the relevance floor {min_score} "
                f"(best semantic {diag['best_vector']}, best keyword {diag['best_lexical']})"
            )
        return out, diag

    def reindex(self, collection_id: str) -> dict:
        """Re-embeds every stored passage of a collection and rebuilds its vector index (for an index that
        is missing, corrupted or built with an older embedding model). Document text is not re-extracted."""
        with db_session(self.engine) as s:
            rows = list(s.exec(select(Chunk).where(Chunk.collection_id == collection_id).order_by(Chunk.id)))
        self.index.drop(collection_id)
        empty = [r.id for r in rows if not (r.text or "").strip()]
        rows = [r for r in rows if (r.text or "").strip()]
        if rows:
            self.index.add(collection_id, [r.id for r in rows], self.embedder.embed([r.text for r in rows]))
        return {
            "collection_id": collection_id,
            "passages": len(rows),
            "empty_passages": len(empty),
            "indexed": self.index.count(collection_id),
        }

    def passages(self, collection_id: str, limit: int = 2000) -> list[str]:
        """Chunk texts of a collection, in document order (for the knowledge graph)."""
        with db_session(self.engine) as s:
            stmt = select(Chunk.text).where(Chunk.collection_id == collection_id).order_by(Chunk.document_id, Chunk.ordinal).limit(limit)
            return list(s.exec(stmt))

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
