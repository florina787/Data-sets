"""Vector similarity backend: pgvector on PostgreSQL when the extension/column exists, otherwise in-process cosine.
Both paths only score chunk ids that already passed the authorization pre-filter."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.orm import Session

from retrieval import embed as emb


@lru_cache
def _has_pgvector(url: str) -> bool:
    from backend.db.session import get_engine
    eng = get_engine()
    if eng.dialect.name != "postgresql":
        return False
    with eng.connect() as c:
        return bool(c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='doc_chunks' AND column_name='embedding_vec'")).scalar())


def mode(s: Session) -> str:
    return "pgvector" if _has_pgvector(str(s.get_bind().url)) else "in-process cosine"


def write_vectors(s: Session, rows: list[tuple[str, list[float]]]) -> None:
    if not _has_pgvector(str(s.get_bind().url)):
        return
    for cid, v in rows:
        s.execute(text("UPDATE doc_chunks SET embedding_vec = CAST(:v AS vector) WHERE id = :id"), {"v": str(v), "id": cid})


def scores(s: Session, qv: list[float], chunks: list[dict]) -> dict[str, float]:
    if not chunks:
        return {}
    if _has_pgvector(str(s.get_bind().url)):
        rows = s.execute(text("SELECT id, 1 - (embedding_vec <=> CAST(:q AS vector)) FROM doc_chunks WHERE id = ANY(:ids) AND embedding_vec IS NOT NULL"),
                         {"q": str(qv), "ids": [c["id"] for c in chunks]}).all()
        if rows:
            return {r[0]: float(r[1]) for r in rows}
    return {c["id"]: emb.cosine(qv, c["emb"]) for c in chunks}
