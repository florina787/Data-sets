"""Knowledge loading, section chunking, and scope-filtered lexical retrieval.

Retrieval order: tenant and role filtering happen in the SQL query, before
any scoring. DEMO mode uses BM25 lexical scoring only; it does not pretend
embeddings exist. Semantic retrieval (pgvector) is available only when an
embedding provider is configured, which this prototype does not ship.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.orm import KnowledgeChunk, KnowledgeDocument

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an the and or of to in on for is are be with this that it as at by not no do if".split())

AUTHORITY_RANK = {"policy": 3, "runbook": 2, "guide": 1}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def parse_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text()
    if not raw.startswith("---"):
        raise ValueError(f"{path.name}: missing front matter")
    _, fm, body = raw.split("---", 2)
    return yaml.safe_load(fm), body.strip()


def chunk_sections(body: str) -> list[tuple[str, str, int, int]]:
    """Split on '## ' headings, preserving character offsets in the body."""
    chunks: list[tuple[str, str, int, int]] = []
    matches = list(re.finditer(r"^## (.+)$", body, flags=re.M))
    for i, m in enumerate(matches):
        start = m.end() + 1
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        text_start = body.index(text, start) if text else start
        chunks.append((m.group(1).strip(), text, text_start, text_start + len(text)))
    return chunks


def load_knowledge(db: Session, knowledge_dir: Path) -> int:
    count = 0
    for path in sorted(knowledge_dir.glob("*.md")):
        meta, body = parse_markdown(path)
        doc = KnowledgeDocument(
            id=meta["id"], version=str(meta["version"]), title=meta["title"],
            doc_type=meta["doc_type"], authority=meta["authority"], product=meta["product"],
            tenant_scope=meta["tenant_scope"], allowed_roles=list(meta["allowed_roles"]),
            effective_date=str(meta["effective_date"]), body=body,
        )
        db.add(doc)
        db.flush()
        for idx, (heading, text, start, end) in enumerate(chunk_sections(body)):
            db.add(KnowledgeChunk(id=f"{doc.id}@{doc.version}#s{idx + 1}", document_id=doc.id,
                                  version=doc.version, heading=heading, text=text,
                                  char_start=start, char_end=end))
        count += 1
    return count


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    version: str
    title: str
    heading: str
    text: str
    authority: str
    doc_type: str
    effective_date: str
    score: float


def scoped_chunks(db: Session, tenant_id: str, role: str, product: str | None = None):
    q = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(or_(KnowledgeDocument.tenant_scope == "*", KnowledgeDocument.tenant_scope == tenant_id))
    )
    if product:
        q = q.where(KnowledgeDocument.product == product)
    rows = db.execute(q).all()
    # allowed_roles is JSON; filter in Python after the tenant filter in SQL.
    return [(c, d) for c, d in rows if role in (d.allowed_roles or [])]


def search(db: Session, query: str, *, tenant_id: str, role: str, product: str | None = None,
           k: int = 5) -> list[RetrievedChunk]:
    rows = scoped_chunks(db, tenant_id, role, product)
    if not rows:
        return []
    docs_tokens = [tokenize(c.heading + " " + c.text) for c, _ in rows]
    n = len(rows)
    avgdl = sum(len(t) for t in docs_tokens) / n
    df: dict[str, int] = {}
    for toks in docs_tokens:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    q_tokens = tokenize(query)
    scored: list[RetrievedChunk] = []
    k1, b = 1.4, 0.75
    for (chunk, doc), toks in zip(rows, docs_tokens):
        score = 0.0
        for qt in q_tokens:
            f = toks.count(qt)
            if not f:
                continue
            idf = math.log(1 + (n - df[qt] + 0.5) / (df[qt] + 0.5))
            score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(toks) / avgdl))
        if score > 0:
            scored.append(RetrievedChunk(chunk.id, doc.id, chunk.version, doc.title, chunk.heading,
                                         chunk.text, doc.authority, doc.doc_type,
                                         doc.effective_date, round(score, 4)))
    # Ties broken by authority (policy > runbook > guide) then id for determinism.
    scored.sort(key=lambda r: (-r.score, -AUTHORITY_RANK.get(r.authority, 0), r.chunk_id))
    return scored[:k]


def get_chunk(db: Session, chunk_id: str, *, tenant_id: str, role: str) -> RetrievedChunk | None:
    for chunk, doc in scoped_chunks(db, tenant_id, role):
        if chunk.id == chunk_id:
            return RetrievedChunk(chunk.id, doc.id, chunk.version, doc.title, chunk.heading,
                                  chunk.text, doc.authority, doc.doc_type, doc.effective_date, 0.0)
    return None
