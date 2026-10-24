"""Knowledge collections, document upload and retrieval."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..rag.extract import ExtractionError
from ..security.paths import UnsafePathError
from .state import AppState, get_state

router = APIRouter(prefix="/api/knowledge")


class NewCollection(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "general"


class SearchReq(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    collection_ids: list[str] = Field(default_factory=list)
    k: int = Field(default=5, ge=1, le=20)


@router.get("/collections")
async def list_collections(st: AppState = Depends(get_state)):
    return st.kb.list_collections()


@router.post("/collections")
async def create_collection(body: NewCollection, st: AppState = Depends(get_state)):
    try:
        return st.kb.create_collection(body.name, body.kind).model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, st: AppState = Depends(get_state)):
    if not st.kb.delete_collection(collection_id):
        raise HTTPException(404, "collection not found")
    return {"deleted": collection_id}


@router.post("/collections/{collection_id}/documents")
async def upload(collection_id: str, file: UploadFile = File(...), st: AppState = Depends(get_state)):
    limit = st.settings.max_upload_mb * 2**20
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"file exceeds {st.settings.max_upload_mb} MB")
    try:
        with st.metrics.timer("rag.ingest_ms"):
            return await asyncio.to_thread(st.kb.ingest, collection_id, file.filename or "", data)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except (UnsafePathError, ExtractionError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, st: AppState = Depends(get_state)):
    if not st.kb.delete_document(document_id):
        raise HTTPException(404, "document not found")
    return {"deleted": document_id}


@router.post("/search")
async def search(body: SearchReq, st: AppState = Depends(get_state)):
    with st.metrics.timer("rag.retrieval_ms") as t:
        hits = await asyncio.to_thread(st.kb.search, body.query, body.collection_ids or None, body.k)
    return {"results": [h.citation() for h in hits], "retrieval_ms": t.get("ms")}
