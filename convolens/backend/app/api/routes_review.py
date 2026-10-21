"""Blind human review queue and label-accuracy endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import review
from app.analytics.taxonomy import (
    ESCALATION,
    RESOLUTION,
    SENTIMENT,
    TOPIC_KEYS,
    topic_label,
)
from app.api.common import ready_dataset
from app.db import get_db
from app.models.orm import Conversation, Dataset, ReviewLabel
from app.tools.catalog import get_conversation_detail

router = APIRouter(prefix="/api")

ALLOWED = {"primary_topic": TOPIC_KEYS, "resolution_status": list(RESOLUTION), "sentiment_start": list(SENTIMENT),
           "sentiment_end": list(SENTIMENT), "escalation_requested": list(ESCALATION)}


def _options() -> dict:
    return {"primary_topic": [{"key": k, "label": topic_label(k)} for k in TOPIC_KEYS],
            "resolution_status": [{"key": k, "label": v} for k, v in RESOLUTION.items()],
            "sentiment_start": [{"key": k, "label": v} for k, v in SENTIMENT.items()],
            "sentiment_end": [{"key": k, "label": v} for k, v in SENTIMENT.items()],
            "escalation_requested": [{"key": k, "label": v} for k, v in ESCALATION.items()]}


@router.get("/datasets/{dataset_id}/review/next")
def review_next(ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    """Next conversation to label. System labels are deliberately omitted so the review is blind."""
    items = review.next_items(db, ds.id, 1)
    out = {"reviewed": review.reviewed_count(db, ds.id), "target": review.TARGET_REVIEWS, "options": _options(), "item": None}
    if items:
        d = get_conversation_detail(db, ds.id, items[0].key)
        out["item"] = {"conversation_key": d["conversation_key"],
                       "brand": items[0].brand, "customer_turns": items[0].customer_turns,
                       "messages": [{"message_id": m["message_id"], "role": m["role"], "text": m["text"], "language": m["language"]}
                                    for m in d["messages"]]}
    return out


class ReviewIn(BaseModel):
    reviewer: str = Field(min_length=1, max_length=80)
    labels: dict[str, str]
    note: str | None = Field(default=None, max_length=500)


@router.post("/datasets/{dataset_id}/review/{key}")
def review_submit(key: str, body: ReviewIn, ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    if set(body.labels) != set(ALLOWED) or any(v not in ALLOWED[k] for k, v in body.labels.items()):
        raise HTTPException(422, "Provide one allowed value for each of: " + ", ".join(ALLOWED))
    conv = db.scalar(select(Conversation).where(Conversation.dataset_id == ds.id, Conversation.key == key))
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    if db.scalar(select(ReviewLabel.id).where(ReviewLabel.conversation_id == conv.id, ReviewLabel.reviewer == body.reviewer)):
        raise HTTPException(409, "This reviewer already labelled this conversation")
    db.add(ReviewLabel(dataset_id=ds.id, conversation_id=conv.id, reviewer=body.reviewer, labels=body.labels, note=body.note))
    db.commit()
    # Reveal after submission: how each system labelled the same conversation.
    systems = review.system_labels(db, conv)
    return {"saved": True, "reviewed": review.reviewed_count(db, ds.id),
            "comparison": {name: {f: {"system": pred.get(f), "human": body.labels[f], "agree": pred.get(f) == body.labels[f]}
                                  for f in review.FIELDS} for name, pred in systems.items()}}


@router.get("/datasets/{dataset_id}/review/accuracy")
def review_accuracy(ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    out = review.accuracy(db, ds.id)
    out["active_analysis"] = ds.active_analysis
    return out
