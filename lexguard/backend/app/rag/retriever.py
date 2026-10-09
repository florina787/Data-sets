"""Permission-aware retrieval. Security is applied BEFORE retrieval: the candidate set is built only
from partitions in the sealed AccessScope and filtered by role sensitivity clearance before scoring."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel

from app.access.matter_access import AccessScope
from app.models.domain import sensitivity_rank
from app.rag.index import PartitionedIndex, chunk_sections
from app.security.injection import detect_injection
from app.services.data_store import DataStore, get_store


class ScopeViolation(PermissionError):
    pass


class RetrievedSource(BaseModel):
    source_id: str
    doc_id: str
    section_id: str
    title: str
    heading: str
    text: str
    score: float
    kind: str
    matter_id: str | None
    client_id: str | None
    practice_id: str | None
    access_label: str
    sensitivity: str
    untrusted_instruction_detected: bool = False


@dataclass
class RagConfig:
    top_k: int = 5
    chunk_words: int = 120
    overlap: int = 20


def build_index(store: DataStore, cfg: RagConfig | None = None) -> PartitionedIndex:
    cfg = cfg or RagConfig()
    idx = PartitionedIndex()
    for d in store.documents.values():
        if d.status != "active":
            continue
        meta = dict(access_label=d.access_label, sensitivity=d.sensitivity, matter_id=d.matter_id,
                    client_id=d.client_id, practice_id=store.matters[d.matter_id].practice_id, kind="matter_document")
        for c in chunk_sections(d.doc_id, d.title, d.sections, meta, cfg.chunk_words, cfg.overlap):
            idx.add(c)
    for k in store.knowledge.values():
        meta = dict(access_label=k.access_label, sensitivity=k.sensitivity, matter_id=k.matter_id,
                    client_id=k.client_id, practice_id=k.practice_id, kind=k.kind)
        for c in chunk_sections(k.doc_id, k.title, k.sections, meta, cfg.chunk_words, cfg.overlap):
            idx.add(c)
    return idx


@lru_cache
def get_index() -> PartitionedIndex:
    return build_index(get_store())


def search(scope: AccessScope, query: str, *, top_k: int = 5, kinds: set[str] | None = None,
           doc_ids: set[str] | None = None, index: PartitionedIndex | None = None) -> list[RetrievedSource]:
    if not isinstance(scope, AccessScope) or not scope.is_sealed():
        raise ScopeViolation("Retrieval requires a sealed AccessScope produced by the access-control layer.")
    index = index or get_index()
    clearance = sensitivity_rank(scope.max_sensitivity)

    def predicate(c) -> bool:
        # Defence in depth: partition already restricts, re-check matter + sensitivity metadata.
        if c.matter_id is not None and c.matter_id not in scope.permitted_matter_ids:
            return False
        if sensitivity_rank(c.sensitivity) > clearance:
            return False
        if kinds is not None and c.kind not in kinds:
            return False
        if doc_ids is not None and c.doc_id not in doc_ids:
            return False
        return True

    hits = index.search(scope.permitted_labels, query, predicate, top_k=top_k)
    return [RetrievedSource(source_id=c.chunk_id, doc_id=c.doc_id, section_id=c.section_id, title=c.title,
                            heading=c.heading, text=c.text, score=s, kind=c.kind, matter_id=c.matter_id,
                            client_id=c.client_id, practice_id=c.practice_id, access_label=c.access_label,
                            sensitivity=c.sensitivity, untrusted_instruction_detected=bool(detect_injection(c.text)))
            for s, c in hits]
