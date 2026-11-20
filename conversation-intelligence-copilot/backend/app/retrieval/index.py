"""FAISS indexes and hybrid search with evidence references.

Two indexes are built over the same conversation-aware chunks:

* **dense** — `sentence-transformers/all-MiniLM-L6-v2` (semantic; handles paraphrases)
* **lsa** — local TF-IDF + SVD (lexical; strong when wording overlaps, always available)

Hybrid search ranks conversations in each index and fuses the two rankings with
Reciprocal Rank Fusion: score = Σ 1 / (rrf_k + rank). If the dense model could not
be loaded at build time, hybrid search degrades to LSA only and says so.

Cosine similarities are ranking signals, not probabilities or model confidence.
"""

from __future__ import annotations

import json
import logging
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
from app.retrieval.embeddings import LSAEmbedder, create_embedder, load_embedder
from app.schemas.analysis import Scope

log = logging.getLogger(__name__)
INDEX_VERSION = "idx-2.0"
METHODS = ("dense", "lsa")


def _paths(settings: Settings) -> dict[str, Path]:
    base = settings.faiss_index_path
    return {
        "dense": base, "dense_embedder": base.with_suffix(".embedder"),
        "lsa": base.with_suffix(".lsa.faiss"), "lsa_embedder": base.with_suffix(".lsa.embedder"),
        "meta": base.with_suffix(".meta.parquet"), "manifest": base.with_suffix(".manifest.json"),
    }


def _write_index(vectors: np.ndarray, path: Path) -> None:
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(vectors.shape[1]))
    index.add_with_ids(vectors, np.arange(len(vectors), dtype="int64"))
    faiss.write_index(index, str(path))


def build_index(settings: Settings | None = None, db: AnalyticsDB | None = None) -> dict:
    settings = settings or get_settings()
    db = db or get_db()
    started = time.perf_counter()
    msgs = db.frame("SELECT message_id, conversation_id, turn_index, speaker_role, masked_text, dataset_source FROM messages")
    chunks = chunk_conversations(msgs, settings.chunk_turns, settings.chunk_overlap)
    conv = db.frame("SELECT conversation_id, topic, topic_label, product, domain, sentiment, agent_id, month, "
                    "CAST(start_timestamp AS VARCHAR) AS start_timestamp FROM conversations")
    meta = pd.DataFrame(chunks).merge(conv, on="conversation_id", how="left")
    texts = meta["text"].tolist()
    p = _paths(settings)
    p["meta"].parent.mkdir(parents=True, exist_ok=True)
    for k in ("dense", "dense_embedder"):  # never leave a stale dense index behind
        p[k].unlink(missing_ok=True)

    backends: dict[str, dict] = {}
    t0 = time.perf_counter()
    lsa = LSAEmbedder()
    lsa.fit(texts)
    _write_index(lsa.encode(texts), p["lsa"])
    lsa.save(p["lsa_embedder"])
    backends["lsa"] = {"name": lsa.name, "dimensions": lsa.dim, "build_seconds": round(time.perf_counter() - t0, 2)}

    fallback = None
    if settings.embedding_backend != "lsa":
        t0 = time.perf_counter()
        dense, fallback = create_embedder(settings.embedding_backend, settings.embedding_model)
        if not isinstance(dense, LSAEmbedder):
            vectors = dense.encode(texts)
            _write_index(vectors, p["dense"])
            dense.save(p["dense_embedder"])
            backends["dense"] = {"name": dense.name, "dimensions": int(vectors.shape[1]), "build_seconds": round(time.perf_counter() - t0, 2)}

    meta["message_ids"] = meta["message_ids"].map(json.dumps)
    meta["speakers"] = meta["speakers"].map(json.dumps)
    meta.to_parquet(p["meta"], index=False)
    mode = "hybrid" if "dense" in backends else "lsa"
    manifest = {
        "index_version": INDEX_VERSION, "built_at": datetime.now(UTC).isoformat(),
        "embedding_backend": " + ".join(b["name"] for b in backends.values()) if mode == "hybrid" else backends["lsa"]["name"],
        "retrieval_mode": mode, "fusion": f"reciprocal rank fusion (k={settings.rrf_k})" if mode == "hybrid" else None,
        "backends": backends, "fallback_reason": fallback,
        "chunks": len(meta), "conversations": int(meta["conversation_id"].nunique()),
        "chunk_turns": settings.chunk_turns, "chunk_overlap": settings.chunk_overlap,
        "dataset_build": db.metadata()["built_at"], "build_seconds": round(time.perf_counter() - started, 2),
    }
    p["manifest"].write_text(json.dumps(manifest, indent=2))
    return manifest


def _clean(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v


def reciprocal_rank_fusion(rankings: dict[str, list[str]], k: int = 60, weights: dict[str, float] | None = None) -> list[tuple[str, float]]:
    """Fuse ranked lists of IDs: score(id) = Σ_lists w_list / (k + rank), rank starting at 1 (w defaults to 1)."""
    scores: dict[str, float] = {}
    for name, ranked in rankings.items():
        w = (weights or {}).get(name, 1.0)
        for rank, item in enumerate(ranked, start=1):
            scores[item] = scores.get(item, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


class RetrievalUnavailable(RuntimeError):
    pass


class Retriever:
    def __init__(self, settings: Settings):
        p = _paths(settings)
        self.rrf_k = settings.rrf_k
        self.default_mode = settings.retrieval_mode
        self.weights = {"dense": 1.0, "lsa": settings.hybrid_lsa_weight}
        for k in ("lsa", "lsa_embedder", "meta", "manifest"):
            if not p[k].exists():
                raise RetrievalUnavailable(f"Retrieval index missing ({p[k].name}). Run `make index`.")
        try:
            self.manifest = json.loads(p["manifest"].read_text())
            self.meta = pd.read_parquet(p["meta"])
            self.indexes: dict[str, tuple[faiss.Index, object]] = {"lsa": (faiss.read_index(str(p["lsa"])), LSAEmbedder.load(p["lsa_embedder"]))}
            if "dense" in self.manifest.get("backends", {}):
                self.indexes["dense"] = (faiss.read_index(str(p["dense"])), load_embedder(p["dense_embedder"], "sentence-transformers"))
        except Exception as e:  # noqa: BLE001 - corrupt or incompatible files
            raise RetrievalUnavailable(f"Retrieval index could not be loaded ({type(e).__name__}: {e}). Rebuild with `make index`.") from e
        if any(ix.ntotal != len(self.meta) for ix, _ in self.indexes.values()):
            raise RetrievalUnavailable("Retrieval index and metadata are out of sync. Rebuild with `make index`.")
        self.meta["message_ids"] = self.meta["message_ids"].map(json.loads)

    @property
    def methods(self) -> list[str]:
        return [m for m in METHODS if m in self.indexes]

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

    def _rank(self, method: str, query: str, allowed: np.ndarray, fetch: int) -> list[dict]:
        """Best chunk per conversation for one index, in rank order."""
        index, embedder = self.indexes[method]
        scores, ids = index.search(embedder.encode([query]), fetch, params=faiss.SearchParameters(sel=faiss.IDSelectorBatch(allowed)))
        seen: set[str] = set()
        out = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            cid = self.meta.iloc[int(idx)]["conversation_id"]
            if cid in seen:
                continue
            seen.add(cid)
            out.append({"conversation_id": cid, "row": int(idx), "similarity": round(float(score), 4), "rank": len(out) + 1})
        return out

    def search(self, query: str, scope: Scope, k: int = 5, mode: str | None = None) -> dict:
        started = time.perf_counter()
        mode = mode or self.default_mode
        note = None
        if mode in ("hybrid", "dense") and "dense" not in self.indexes:
            note = "Dense embeddings are not available in this index; LSA only."
            mode = "lsa"
        allowed = self._allowed(scope)
        if len(allowed) == 0:
            return {"results": [], "candidates": 0, "latency_ms": 0.0, "mode": mode, "note": "No indexed passages match the filters."}
        fetch = int(min(len(allowed), max(k * 30, 150)))
        methods = ["dense", "lsa"] if mode == "hybrid" else [mode]
        per = {m: self._rank(m, query, allowed, fetch) for m in methods}
        by_conv = {m: {r["conversation_id"]: r for r in per[m]} for m in methods}
        fused = reciprocal_rank_fusion({m: [r["conversation_id"] for r in per[m]] for m in methods}, self.rrf_k, self.weights)
        results = []
        for cid, fscore in fused[:k]:
            hits = {m: by_conv[m][cid] for m in methods if cid in by_conv[m]}
            primary = hits.get("dense") or hits["lsa"]  # show the dense model's best passage when it found one
            row = self.meta.iloc[primary["row"]]
            results.append({
                "evidence_id": row["chunk_id"], "conversation_id": cid, "message_ids": list(row["message_ids"]),
                "turn_range": [int(row["turn_start"]), int(row["turn_end"])], "text": row["text"], "similarity": primary["similarity"],
                "retrieval_method": mode, "fused_score": round(fscore, 5),
                "method_scores": {m: {"rank": h["rank"], "similarity": h["similarity"]} for m, h in hits.items()},
                "topic": row["topic_label"], "product": _clean(row["product"]), "sentiment": row["sentiment"],
                "agent_id": _clean(row["agent_id"]), "start_timestamp": row["start_timestamp"], "dataset_source": row["dataset_source"],
            })
        names = {m: self.manifest["backends"][m]["name"] for m in methods}
        return {"results": results, "candidates": len(fused), "mode": mode, "methods": names,
                "fusion": f"weighted reciprocal rank fusion (k={self.rrf_k}, MiniLM 1.0, LSA {self.weights['lsa']})" if mode == "hybrid" else None, "note": note,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "embedding_backend": " + ".join(names.values()),
                "score_note": "Similarity is cosine similarity between embeddings; hybrid ranking fuses each method's rank (RRF). Ranking signals, not probabilities."}

    def status(self) -> dict:
        return {"available": True, "methods": self.methods, "default_mode": self.default_mode, **self.manifest}


@lru_cache
def get_retriever() -> Retriever:
    return Retriever(get_settings())


def retriever_status() -> dict:
    try:
        return get_retriever().status()
    except RetrievalUnavailable as e:
        get_retriever.cache_clear()
        return {"available": False, "reason": str(e)}
