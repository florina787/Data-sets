"""Permission-checked document access. Analysis code can only obtain documents through here."""

from __future__ import annotations

from app.access.matter_access import AccessScope
from app.models.domain import Document, sensitivity_rank
from app.rag.retriever import ScopeViolation
from app.services.data_store import DataStore


def permitted_documents(store: DataStore, scope: AccessScope, matter_id: str) -> list[Document]:
    if not scope.is_sealed():
        raise ScopeViolation("Document access requires a sealed AccessScope.")
    if matter_id not in scope.permitted_matter_ids:
        raise ScopeViolation(f"Matter {matter_id} is outside the permitted scope for this request.")
    clearance = sensitivity_rank(scope.max_sensitivity)
    return [d for d in store.matter_documents(matter_id) if sensitivity_rank(d.sensitivity) <= clearance]


def permitted_document(store: DataStore, scope: AccessScope, doc_id: str) -> Document | None:
    doc = store.documents.get(doc_id)
    if doc is None or doc.matter_id not in scope.permitted_matter_ids:
        return None
    if sensitivity_rank(doc.sensitivity) > sensitivity_rank(scope.max_sensitivity):
        return None
    return doc
