"""Per-collection FAISS indexes persisted to disk.

Vectors are L2-normalised and stored in an inner-product index, so scores are
cosine similarities. Vector ids are the SQLite chunk ids.
"""

from __future__ import annotations

import threading
from pathlib import Path

import faiss
import numpy as np

from ..security.paths import safe_join


class VectorIndex:
    def __init__(self, root: Path, dim: int):
        self.root = root
        self.dim = dim
        self._indexes: dict[str, faiss.IndexIDMap2] = {}
        self._lock = threading.Lock()

    def _path(self, collection_id: str) -> Path:
        if not collection_id.isalnum():
            raise ValueError("invalid collection id")
        return safe_join(self.root, f"{collection_id}.faiss")

    def _get(self, collection_id: str) -> faiss.IndexIDMap2:
        idx = self._indexes.get(collection_id)
        if idx is None:
            p = self._path(collection_id)
            if p.exists():
                idx = faiss.read_index(str(p))
                if idx.d != self.dim:
                    raise ValueError("index dimension does not match the embedding model; re-index the collection")
            else:
                idx = faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))
            self._indexes[collection_id] = idx
        return idx

    def _save(self, collection_id: str) -> None:
        p = self._path(collection_id)
        tmp = p.with_suffix(".tmp")
        faiss.write_index(self._indexes[collection_id], str(tmp))
        tmp.replace(p)

    def add(self, collection_id: str, ids: list[int], vectors: np.ndarray) -> None:
        with self._lock:
            idx = self._get(collection_id)
            idx.add_with_ids(vectors.astype(np.float32), np.asarray(ids, dtype=np.int64))
            self._save(collection_id)

    def remove(self, collection_id: str, ids: list[int]) -> None:
        with self._lock:
            idx = self._get(collection_id)
            idx.remove_ids(np.asarray(ids, dtype=np.int64))
            self._save(collection_id)

    def drop(self, collection_id: str) -> None:
        with self._lock:
            self._indexes.pop(collection_id, None)
            p = self._path(collection_id)
            if p.exists():
                p.unlink()

    def search(self, collection_id: str, vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        with self._lock:
            idx = self._get(collection_id)
            if idx.ntotal == 0:
                return []
            scores, ids = idx.search(vector.reshape(1, -1).astype(np.float32), min(k, idx.ntotal))
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]

    def count(self, collection_id: str) -> int:
        with self._lock:
            return self._get(collection_id).ntotal
