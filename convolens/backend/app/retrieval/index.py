"""Hybrid retrieval over redacted messages: BM25 keyword + FAISS semantic (local sentence-transformer or Gemini),
fused with reciprocal rank fusion, restricted by metadata filters resolved in SQL.

Retrieval locates *examples*; it never produces counts (counts come from SQL in analytics.metrics).
"""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.metrics import conditions, evidence_id
from app.config import get_settings
from app.models.orm import Conversation, Message
from app.models.schemas import Filters

log = logging.getLogger(__name__)
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "it", "my", "i", "you", "we", "your", "our",
         "me", "this", "that", "be", "with", "at", "us", "please", "dm", "user", "customer", "agent", "id", "url"}


def tokenize(text: str) -> list[str]:
    toks = [t.lower() for t in _TOKEN.findall(text)]
    return [t[:-1] if len(t) > 4 and t.endswith("s") else t for t in toks if t not in _STOP and len(t) > 1]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=float)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.postings: dict[str, list[int]] = defaultdict(list)
        for i, d in enumerate(self.tf):
            for t in d:
                self.postings[t].append(i)

    def scores(self, query: list[str]) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for t in set(query):
            idf = self.idf.get(t)
            if not idf:
                continue
            for i in self.postings[t]:
                f = self.tf[i][t]
                out[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1)))
        return out


class Encoder:
    """Lazy sentence-transformer wrapper. Unavailability is reported, never silently replaced."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self.error: str | None = None
        self._lock = threading.Lock()

    def available(self) -> bool:
        if self._model is not None:
            return True
        if self.error:
            return False
        with self._lock:
            try:
                from sentence_transformers import SentenceTransformer  # optional dependency
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:  # ImportError, download failures, etc.
                self.error = f"{type(exc).__name__}: {str(exc)[:200]}"
                log.warning("Semantic retrieval unavailable: %s", self.error)
                return False
        return True

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self.available():
            raise RuntimeError(f"Embedding model unavailable: {self.error}")
        v = self._model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
        return np.asarray(v, dtype="float32")


@dataclass
class DatasetIndex:
    dataset_id: str
    msg_ids: list[int]
    conv_ids: list[int]
    texts: list[str]
    bm25: BM25
    faiss_index: object | None = None
    sem_pos: list[int] | None = None  # positions covered by faiss_index, in its order (None = all)
    semantic_error: str | None = None
    built_at: float = field(default_factory=time.time)


_encoder: Encoder | None = None
_indexes: dict[str, DatasetIndex] = {}
_lock = threading.Lock()


def get_encoder() -> Encoder | None:
    global _encoder
    s = get_settings()
    if not s.embeddings_enabled:
        return None
    if _encoder is None:
        if s.embedding_provider == "gemini":
            from app.retrieval.gemini_embed import GeminiEncoder
            _encoder = GeminiEncoder()
        else:
            _encoder = Encoder(s.embedding_model)
    return _encoder


def set_encoder(enc) -> None:
    """Test hook / alternate encoder injection (e.g. a multilingual model for evaluation)."""
    global _encoder
    _encoder = enc
    _indexes.clear()


def semantic_status() -> dict:
    s = get_settings()
    if not s.embeddings_enabled:
        return {"available": False, "model": None, "reason": "Disabled by EMBEDDINGS_ENABLED=false"}
    enc = get_encoder()
    if enc._model is None and enc.error is None:
        return {"available": None, "model": enc.model_name, "reason": "Not loaded yet (loads on first search)"}
    return {"available": enc._model is not None, "model": enc.model_name, "reason": enc.error}


def _build(db: Session, dataset_id: str) -> DatasetIndex:
    rows = db.execute(select(Message.id, Message.conversation_id, Message.text, Message.role)
                      .where(Message.dataset_id == dataset_id).order_by(Message.id)).all()
    texts = [r.text for r in rows]
    idx = DatasetIndex(dataset_id, [r.id for r in rows], [r.conversation_id for r in rows], texts, BM25([tokenize(t) for t in texts]))
    enc = get_encoder()
    if enc is None:
        idx.semantic_error = "Semantic retrieval disabled by configuration"
    elif texts:
        try:
            import faiss
            roles = getattr(enc, "roles", None)  # remote encoders embed only the roles search targets, to save quota
            if roles:
                idx.sem_pos = [i for i, r in enumerate(rows) if r.role in roles]
            vecs = enc.encode([texts[i] for i in idx.sem_pos] if idx.sem_pos is not None else texts)
            fi = faiss.IndexFlatIP(vecs.shape[1])
            fi.add(vecs)
            idx.faiss_index = fi
        except Exception as exc:
            idx.semantic_error = str(exc)[:300]
    return idx


def get_index(db: Session, dataset_id: str) -> DatasetIndex:
    with _lock:
        idx = _indexes.get(dataset_id)
        if idx is None:
            idx = _build(db, dataset_id)
            _indexes[dataset_id] = idx
        return idx


def invalidate(dataset_id: str | None = None) -> None:
    with _lock:
        if dataset_id:
            _indexes.pop(dataset_id, None)
        else:
            _indexes.clear()


def search(db: Session, dataset_id: str, query: str, filters: Filters | None = None, k: int = 8,
           mode: str = "hybrid", extra_queries: list[str] | None = None, role: str | None = "customer") -> dict:
    t0 = time.perf_counter()
    idx = get_index(db, dataset_id)
    allowed = set(db.scalars(select(Conversation.id).where(*conditions(dataset_id, filters))).all())
    role_ok = None
    if role:
        role_ok = set(db.scalars(select(Message.id).where(Message.dataset_id == dataset_id, Message.role == role)).all())
    pos_ok = [i for i, (mid, cid) in enumerate(zip(idx.msg_ids, idx.conv_ids)) if cid in allowed and (role_ok is None or mid in role_ok)]
    pos_set = set(pos_ok)
    queries = [query] + [q for q in (extra_queries or []) if q and q != query]
    rankings: list[list[int]] = []
    used = []
    if mode in ("hybrid", "keyword"):
        for q in queries:
            sc = idx.bm25.scores(tokenize(q))
            rankings.append([i for i, _ in sorted(((i, s) for i, s in sc.items() if i in pos_set), key=lambda x: -x[1])][:200])
        used.append("keyword_bm25")
    semantic_note = None
    if mode in ("hybrid", "semantic"):
        if idx.faiss_index is not None and pos_ok:
            import faiss  # noqa: F401
            try:
                qv = get_encoder().encode(queries)
            except Exception as exc:
                qv, semantic_note = None, f"Query embedding failed: {str(exc)[:200]}"
            if qv is not None:
                kk = min(idx.faiss_index.ntotal, 400)
                D, I = idx.faiss_index.search(qv, kk)
                pos = idx.sem_pos
                for row in I:
                    mapped = (int(i) if pos is None else pos[int(i)] for i in row if int(i) >= 0)
                    rankings.append([i for i in mapped if i in pos_set][:200])
                used.append("semantic_faiss")
        else:
            semantic_note = idx.semantic_error or "No documents in scope"
    fused: dict[int, float] = defaultdict(float)
    for r in rankings:
        for rank, i in enumerate(r):
            fused[i] += 1.0 / (60 + rank)
    top = sorted(fused.items(), key=lambda x: -x[1])
    # Diversify: at most two hits per conversation.
    per_conv: Counter = Counter()
    hits = []
    conv_cache: dict[int, Conversation] = {}
    for i, score in top:
        cid = idx.conv_ids[i]
        if per_conv[cid] >= 2:
            continue
        per_conv[cid] += 1
        m = db.get(Message, idx.msg_ids[i])
        conv = conv_cache.get(cid) or db.get(Conversation, cid)
        conv_cache[cid] = conv
        hits.append({"evidence_id": evidence_id(conv.key, m.source_id), "conversation_key": conv.key, "message_id": m.source_id,
                     "role": m.role, "language": m.language, "text": m.text, "score": round(score, 5),
                     "primary_topic": conv.primary_topic, "resolution_status": conv.resolution_status})
        if len(hits) >= k:
            break
    return {"query": query, "extra_queries": queries[1:], "mode": mode, "methods_used": used,
            "semantic_unavailable_reason": semantic_note, "candidates_in_scope": len(pos_ok), "hits": hits,
            "evidence_ids": [h["evidence_id"] for h in hits],
            "meta": {"operation": "search", "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                     "fusion": "reciprocal_rank_fusion(k=60)"}}
