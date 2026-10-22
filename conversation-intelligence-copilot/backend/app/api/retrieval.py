"""Semantic retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.analytics.db import get_db
from app.analytics.time_windows import resolve_window
from app.retrieval.index import RetrievalUnavailable, get_retriever, retriever_status
from app.schemas.analysis import Scope
from app.schemas.api_response import RetrievalQuery

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.post("/search")
def search(q: RetrievalQuery) -> dict:
    try:
        scope = Scope(dataset_mode=q.dataset_mode, window=resolve_window(get_db(), q.dataset_mode, q.window), topics=q.topics, sentiments=q.sentiments)
        return get_retriever().search(q.query, scope, k=q.k, mode=q.mode)
    except RetrievalUnavailable as e:
        raise HTTPException(503, str(e)) from e


@router.get("/status")
def status() -> dict:
    return retriever_status()
