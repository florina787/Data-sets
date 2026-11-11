"""Agent measurement: the semantic-spine scorecard and the knowledge graph."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from ..agents.spine import knowledge_graph
from ..analytics.agents import scorecard
from .state import AppState, get_state

router = APIRouter(prefix="/api/agents")


@router.get("/scorecard")
async def get_scorecard(days: int = Query(30, ge=1, le=365), st: AppState = Depends(get_state)):
    if st.telemetry:
        st.telemetry.track("feature", feature="agents")
    return await asyncio.to_thread(scorecard, st.store, days)


@router.get("/knowledge-graph")
async def get_knowledge_graph(collection_id: str, limit: int = Query(40, ge=5, le=120), st: AppState = Depends(get_state)):
    if not st.kb.get_collection(collection_id):
        raise HTTPException(404, "collection not found")
    passages = await asyncio.to_thread(st.kb.passages, collection_id)
    return await asyncio.to_thread(knowledge_graph, passages, limit)
