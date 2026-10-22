"""FAISS index build/load and filtered semantic search with evidence references.

Scores are cosine similarities between the query and chunk embeddings (inner
product of L2-normalised vectors). They rank passages; they are not
probabilities and not model confidence.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from app.analytics.db import DATASET_SOURCES, AnalyticsDB, get_db
from app.config import Settings, get_settings
from app.retrieval.chunking import chunk_conversations
from app.retrieval.embeddings import create_embedder, load_embedder
from app.schemas.analysis import Scope

log = logging.getLogger(__name__)
INDEX_VERSION = "idx-1.0"
_TOKEN = re.compile(r"[a-z0-9']+")


def _paths(settings: Settings) -> dict[str, Path]:
    base = settings.faiss_index_path
    return {"index": base, "meta": base.with_suffix(".meta.parquet"), "embedder": base.with_suffix(".embedder"),
            "manifest": base.with_suffix(".manifest.json")}


def build_index(settings: Settings | None = None, db: AnalyticsDB | None = None) -> dict:
    settings = settings or get_settings()
    db = db or get_db()
    started = time.perf_counter()
    msgs = db.frame("SELECT message_id, conversation_id, turn_index, speaker_role, masked_text, dataset_source FROM messages")
    chunks = chunk_conversations(msgs, settings.chunk_turns, settings.chunk_overlap)
    conv = db.frame("SELECT conversation_id, topic, topic_label, product, domain, sentiment, agent_id, month, "
                           "CAST(start_timestamp AS VARCHAR) AS start_timestamp FROM conversations")
    meta = pd.DataFrame(chunks).merge(conv, on="conversation_id", how="left")
    embedder, fallback = create_embedder(settings.embedding_backend, settings.embedding_model)
    embedder.fit(meta["text"].tolist())
    vectors = embedder.encode(meta["text"].tolist())
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(vectors.shape[1]))
    index.add_with_ids(vectors, np.arange(len(meta), dtype="int64"))
    p = _paths(settings)
    p["index"].parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(p["index"]))
    meta["message_ids"] = meta["message_ids"].map(json.dumps)
    meta["speakers"] = meta["speakers"].map(json.dumps)
    meta.to_parquet(p["meta"], index=False)
    embedder.save(p["embedder"])
    manifest = {
        "index_version": INDEX_VERSION, "built_at": datetime.now(UTC).isoformat(), "embedding_backend": embedder.name,
        "embedder_kind": "lsa" if embedder.name.startswith("lsa") else "sentence-transformers", "fallback_reason": fallback,
        "dimensions": int(vectors.shape[1]), "chunks": len(meta), "conversations": int(meta["conversation_id"].nunique()),
        "chunk_turns": settings.chunk_turns, "chunk_overlap": settings.chunk_overlap,
        "dataset_build": db.metadata()["built_at"], "build_seconds": round(time.perf_counter() - started, 2),
    }
    p["manifest"].write_text(json.dumps(manifest, indent=2))
    return manifest


def _clean(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v


class RetrievalUnavailable(RuntimeError):
    pass


class Retriever:
    def __init__(self, settings: Settings):
        p = _paths(settings)
        for k in ("index", "meta", "embedder", "manifest"):
            if not p[k].exists():
                raise RetrievalUnavailable(f"Retrieval index missing ({p[k].name}). Run `make index`.")
        try:
            self.manifest = json.loads(p["manifest"].read_text())
            self.index = faiss.read_index(str(p["index"]))
            self.meta = pd.read_parquet(p["meta"])
            self.embedder = load_embedder(p["embedder"], self.manifest["embedder_kind"])
        except Exception as e:  # noqa: BLE001 - corrupt or incompatible files
            raise RetrievalUnavailable(f"Retrieval index could not be loaded ({type(e).__name__}: {e}). Rebuild with `make index`.") from e
        if self.index.ntotal != len(self.meta):
            raise RetrievalUnavailable("Retrieval index and metadata are out of sync. Rebuild with `make index`.")
        self.meta["message_ids"] = self.meta["message_ids"].map(json.loads)

    def _allowed(self, scope: Scope) -> np.ndarray:
        m = self.meta
        mask = m["dataset_source"].isin(DATASET_SOURCES[scope.dataset_mode])
        if scope.window.start:
            mask &= m["start_timestamp"] >= scope.window.start
        if scope.window.end:
            mask &= m["start_timestamp"] < scope.window.end
        for col, vals in (("topic", scope.topics), ("product", scope.products), ("domain", scope.domains), ("agent_id", scope.agents),
                          ("sentiment", scope.sentiments), ("conversation_id", scope.conversation_ids)):
            if vals:
                mask &= m[col].isin(vals)
        return np.flatnonzero(mask.to_numpy()).astype("int64")

    def search(self, query: str, scope: Scope, k: int = 5, rerank: bool = True) -> dict:
        started = time.perf_counter()
        allowed = self._allowed(scope)
        if len(allowed) == 0:
            return {"results": [], "candidates": 0, "latency_ms": 0.0, "note": "No indexed passages match the filters."}
        q = self.embedder.encode([query])
        fetch = int(min(len(allowed), max(k * 30, 100)))
        params = faiss.SearchParameters(sel=faiss.IDSelectorBatch(allowed))
        scores, ids = self.index.search(q, fetch, params=params)
        q_tokens = set(_TOKEN.findall(query.lower()))
        seen_conv: set[str] = set()
        candidates = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            row = self.meta.iloc[int(idx)]
            lexical = len(q_tokens & set(_TOKEN.findall(row["text"].lower()))) / max(1, len(q_tokens)) if rerank else 0.0
            candidates.append((float(score), lexical, row))
        if rerank:
            candidates.sort(key=lambda c: 0.85 * c[0] + 0.15 * c[1], reverse=True)
        results = []
        duplicates = 0
        for score, lexical, row in candidates:
            if row["conversation_id"] in seen_conv:  # one passage per conversation
                duplicates += 1
                continue
            seen_conv.add(row["conversation_id"])
            results.append({
                "evidence_id": row["chunk_id"], "conversation_id": row["conversation_id"], "message_ids": list(row["message_ids"]),
                "turn_range": [int(row["turn_start"]), int(row["turn_end"])], "text": row["text"], "similarity": round(score, 4),
                "lexical_overlap": round(lexical, 3), "topic": row["topic_label"], "product": _clean(row["product"]), "sentiment": row["sentiment"],
                "agent_id": _clean(row["agent_id"]), "start_timestamp": row["start_timestamp"], "dataset_source": row["dataset_source"],
            })
            if len(results) >= k:
                break
        return {"results": results, "candidates": len(candidates), "duplicates_removed": duplicates,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1), "embedding_backend": self.manifest["embedding_backend"],
                "score_note": "Similarity is cosine similarity between embeddings (ranking signal, not a probability)."}

    def status(self) -> dict:
        return {"available": True, **self.manifest}


@lru_cache
def get_retriever() -> Retriever:
    return Retriever(get_settings())


def retriever_status() -> dict:
    try:
        return get_retriever().status()
    except RetrievalUnavailable as e:
        get_retriever.cache_clear()
        return {"available": False, "reason": str(e)}
