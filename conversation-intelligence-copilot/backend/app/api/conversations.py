"""Conversation explorer endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.analytics.db import DATASET_SOURCES, get_db
from app.analytics.topics import _rows
from app.analytics.trajectories import conversation_messages

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
SORTS = {"id": "conversation_id", "date": "start_timestamp DESC", "most_negative": "sentiment_score_mean ASC", "most_positive": "sentiment_score_mean DESC"}


@router.get("")
def list_conversations(q: str | None = Query(None, max_length=100), topic: str | None = None, sentiment: str | None = None,
                       product: str | None = None, agent: str | None = None, month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
                       dataset_mode: str = "original", sort: str = "id", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)) -> dict:
    if dataset_mode not in DATASET_SOURCES or sort not in SORTS:
        raise HTTPException(400, "Invalid dataset_mode or sort")
    clauses = [f"dataset_source IN ({','.join('?' * len(DATASET_SOURCES[dataset_mode]))})"]
    params: list = list(DATASET_SOURCES[dataset_mode])
    for col, val in (("topic", topic), ("sentiment", sentiment), ("product", product), ("agent_id", agent), ("month", month)):
        if val:
            clauses.append(f"{col} = ?")
            params.append(val)
    if q:
        clauses.append("(conversation_id ILIKE ? OR agent_id ILIKE ? OR conversation_id IN (SELECT conversation_id FROM messages WHERE masked_text ILIKE ?))")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    where = " AND ".join(clauses)
    db = get_db()
    total = int(db.scalar(f"SELECT COUNT(*) FROM conversations WHERE {where}", params) or 0)
    df = db.query(f"""SELECT conversation_id, CAST(start_timestamp AS VARCHAR) AS start_timestamp, agent_id, topic, topic_label, product, domain,
                             sentiment, ROUND(sentiment_score_mean, 3) AS mean_sentiment, message_count, escalation_requests,
                             final_resolution, resolution_relevant, dataset_source
                      FROM conversations WHERE {where} ORDER BY {SORTS[sort]}, conversation_id LIMIT ? OFFSET ?""",
                  params + [page_size, (page - 1) * page_size])
    return {"total": total, "page": page, "page_size": page_size, "items": _rows(df)}


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    db = get_db()
    conv = db.query("SELECT * FROM conversations WHERE conversation_id = ?", [conversation_id])
    if conv.empty:
        raise HTTPException(404, f"Conversation {conversation_id} not found")
    msgs = conversation_messages(db, conversation_id)
    msgs["timestamp"] = msgs["timestamp"].astype(str)
    c = _rows(conv.astype({"start_timestamp": str, "end_timestamp": str, "conversation_date": str}))[0]
    raw = db.query("SELECT message_id, text FROM messages WHERE conversation_id = ? ORDER BY turn_index", [conversation_id])
    raw_map = dict(zip(raw["message_id"], raw["text"]))
    items = _rows(msgs)
    for m in items:
        m["raw_text_length"] = len(raw_map.get(m["message_id"], ""))
    return {"conversation": c, "messages": items}
