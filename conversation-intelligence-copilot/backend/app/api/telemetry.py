"""Telemetry, traces, agent graph and evaluation results."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import graph_definition
from app.analytics.db import get_db
from app.config import get_settings
from app.observability.store import get_telemetry
from app.retrieval.index import retriever_status

router = APIRouter(tags=["telemetry"])


@router.get("/api/telemetry/summary")
def summary() -> dict:
    db = get_db()
    meta = db.metadata()
    pipeline = db.query("""SELECT COUNT(*) AS conversations, SUM((processing_status='labelled')::INT) AS labelled,
                                  SUM((processing_status<>'labelled')::INT) AS provisional FROM conversations WHERE dataset_source='original'""").iloc[0]
    q = get_settings().manifests_dir / "data_quality_report.json"
    quality = json.loads(q.read_text()) if q.exists() else {}
    r = retriever_status()
    return {
        **get_telemetry().summary(),
        "pipeline": {"conversations": int(pipeline["conversations"]), "labelled": int(pipeline["labelled"]), "provisional": int(pipeline["provisional"]),
                     "label_coverage": meta["label_coverage"], "built_at": meta["built_at"],
                     "quality_failures": [c for c in quality.get("checks", []) if c["severity"] in ("error", "warning")],
                     "embedding": {"available": r.get("available"), "chunks": r.get("chunks"), "backend": r.get("embedding_backend"),
                                   "conversations_indexed": r.get("conversations"), "fallback_reason": r.get("fallback_reason")}},
    }


@router.get("/api/telemetry/tokens")
def tokens() -> dict:
    s = get_settings()
    acc = get_telemetry().token_accounting()
    acc["preprocessing"]["label_source"] = s.label_source
    acc["preprocessing"]["note"] = ("Analytics use deterministic template labels (LABEL_SOURCE=rules): building the dataset used no LLM tokens."
                                    if s.label_source == "rules" else "Analytics use LLM labels; the totals above are the labelling run's tokens.")
    return acc


@router.get("/api/traces")
def recent_traces(limit: int = 30) -> list[dict]:
    return get_telemetry().recent_requests(min(limit, 200))


@router.get("/api/traces/{request_id}")
def trace(request_id: str) -> dict:
    t = get_telemetry().trace(request_id)
    if not t:
        raise HTTPException(404, "Trace not found")
    return t


@router.get("/api/responses/{request_id}")
def stored_response(request_id: str) -> dict:
    r = get_telemetry().response(request_id)
    if not r:
        raise HTTPException(404, "Response not found")
    return r


@router.get("/api/agents/graph")
def agents_graph() -> dict:
    return graph_definition()


class UIEvent(BaseModel):
    event: str = Field(max_length=60, pattern=r"^[a-z0-9_.:-]+$")
    session_id: str | None = Field(None, max_length=64)
    detail: dict = {}


@router.post("/api/telemetry/ui-event")
def ui_event(ev: UIEvent) -> dict:
    get_telemetry().ui_event(ev.session_id, ev.event, {k: str(v)[:100] for k, v in list(ev.detail.items())[:8]})
    return {"ok": True}


@router.get("/api/evaluation/results")
def evaluation_results() -> dict:
    f = get_settings().manifests_dir / "evaluation_results.json"
    if not f.exists():
        return {"status": "not_run", "note": "Run `make evaluate` to produce evaluation results."}
    return json.loads(f.read_text())


@router.get("/api/replay/{request_id}")
def replay(request_id: str) -> dict:
    from app.observability.replay import build_replay

    r = build_replay(get_telemetry(), request_id)
    if not r:
        raise HTTPException(404, "No recorded run for this request")
    return r
