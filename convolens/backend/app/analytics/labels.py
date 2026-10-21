"""Effective labels = active analysis prediction with reviewer corrections layered on top.

Original predictions stay in ``analyses``; corrections stay in ``corrections``. The effective
columns on ``conversations`` exist so exact counts can be computed with plain SQL.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Analysis, Conversation, Correction

CORRECTABLE = {"primary_topic", "resolution_status", "sentiment_start", "sentiment_end", "escalation_requested"}


def apply_effective_labels(conv: Conversation, fields: dict, analysis_id: int | None) -> None:
    conv.primary_topic = fields.get("primary_topic") or "unknown"
    conv.secondary_topics = list(fields.get("secondary_topics") or [])
    conv.subtheme = fields.get("subtheme")
    conv.resolution_status = fields.get("resolution_status") or "unknown"
    conv.sentiment_start = fields.get("sentiment_start") or "unknown"
    conv.sentiment_end = fields.get("sentiment_end") or "unknown"
    conv.escalation_requested = fields.get("escalation_requested") or "unknown"
    conv.analysis_id = analysis_id
    conv.corrected = False


def reapply(db: Session, conv: Conversation) -> None:
    """Recompute effective labels from the active analysis and all corrections (latest wins)."""
    a = db.get(Analysis, conv.analysis_id) if conv.analysis_id else None
    apply_effective_labels(conv, a.fields if a else {}, conv.analysis_id)
    rows = db.scalars(select(Correction).where(Correction.target_type == "conversation", Correction.target_id == conv.id)
                      .order_by(Correction.id)).all()
    for c in rows:
        if c.field in CORRECTABLE:
            setattr(conv, c.field, c.corrected_value)
            conv.corrected = True
