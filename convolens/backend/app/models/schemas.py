"""Pydantic schemas shared by extraction, tools, graph and API."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.analytics.taxonomy import ESCALATION, HANDOFF, INTENTS, RESOLUTION, SENTIMENT, TOPIC_KEYS

TopicKey = Literal[tuple(TOPIC_KEYS)]  # type: ignore[valid-type]
ResolutionKey = Literal[tuple(RESOLUTION)]  # type: ignore[valid-type]
SentimentKey = Literal[tuple(SENTIMENT)]  # type: ignore[valid-type]
EscalationKey = Literal[tuple(ESCALATION)]  # type: ignore[valid-type]
HandoffKey = Literal[tuple(HANDOFF)]  # type: ignore[valid-type]
IntentKey = Literal[tuple(INTENTS)]  # type: ignore[valid-type]


class EvidenceSpan(BaseModel):
    message_id: str = Field(description="Source message id (tweet_id) inside this conversation")
    quote: str = Field(description="Exact substring copied from the redacted message text", max_length=400)
    supports: str = Field(description="Which field or claim this evidence supports, e.g. resolution_status")
    start: int | None = None
    end: int | None = None


class Claim(BaseModel):
    kind: Literal["observed", "inference", "hypothesis", "recommendation"]
    text: str = Field(max_length=500)


class ConversationAnalysis(BaseModel):
    """Structured extraction output. Evidence spans are validated against stored text after generation."""
    primary_topic: TopicKey
    secondary_topics: list[TopicKey] = Field(default_factory=list, max_length=3)
    customer_intent: IntentKey
    sentiment_start: SentimentKey
    sentiment_end: SentimentKey
    resolution_status: ResolutionKey
    escalation_requested: EscalationKey
    summary: str = Field(max_length=600)
    reported_problem: str = Field(max_length=400)
    support_action: str = Field(default="", max_length=400)
    evidence: list[EvidenceSpan] = Field(default_factory=list, max_length=12)
    claims: list[Claim] = Field(default_factory=list, max_length=8)


class Filters(BaseModel):
    """Allowlisted analytical filters. Every value is validated; nothing is interpolated into SQL."""
    model_config = ConfigDict(extra="forbid")
    topics: list[TopicKey] = Field(default_factory=list)
    resolution: list[ResolutionKey] = Field(default_factory=list)
    sentiment_end: list[SentimentKey] = Field(default_factory=list)
    escalation: list[EscalationKey] = Field(default_factory=list)
    handoff: list[HandoffKey] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list, max_length=20)
    languages: list[str] = Field(default_factory=list, max_length=20)
    date_from: date | None = None
    date_to: date | None = None
    conversation_keys: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("brands", "languages", "conversation_keys")
    @classmethod
    def _safe_tokens(cls, v: list[str]) -> list[str]:
        out = []
        for s in v:
            s = s.strip()
            if not s or len(s) > 64 or any(c in s for c in "\"';\\\n\r"):
                raise ValueError(f"invalid filter token {s!r}")
            out.append(s)
        return out

    def is_empty(self) -> bool:
        return not any(getattr(self, f) for f in type(self).model_fields)

    def describe(self) -> str:
        from app.analytics.taxonomy import RESOLUTION as R, topic_label
        parts = []
        if self.topics:
            parts.append("topic = " + " or ".join(topic_label(t) for t in self.topics))
        if self.resolution:
            parts.append("resolution = " + " or ".join(R[r] for r in self.resolution))
        if self.sentiment_end:
            parts.append("ending sentiment = " + " or ".join(self.sentiment_end))
        if self.escalation:
            parts.append("escalation = " + " or ".join(self.escalation))
        if self.handoff:
            parts.append("private-channel handoff = " + " or ".join(self.handoff))
        if self.brands:
            parts.append("support account = " + ", ".join(self.brands))
        if self.languages:
            parts.append("message language = " + ", ".join(self.languages))
        if self.date_from or self.date_to:
            parts.append(f"dates {self.date_from or '…'} to {self.date_to or '…'}")
        if self.conversation_keys:
            parts.append(f"{len(self.conversation_keys)} selected conversations")
        return "; ".join(parts) if parts else "all selected conversations"


class ProposedAction(BaseModel):
    title: str = Field(max_length=200)
    issue: str = Field(max_length=120)
    intervention: str = Field(max_length=1000)
    proposed_department: str | None = Field(default=None, max_length=120)
    owner: str | None = Field(default=None, max_length=120)
    due_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    intended_outcome: str = Field(default="", max_length=600)
    success_measure: str = Field(default="", max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class KeyedConversationAnalysis(ConversationAnalysis):
    conversation_key: str = Field(description="The conversation_key given in the input")


class ConversationBatchAnalysis(BaseModel):
    items: list[KeyedConversationAnalysis] = Field(max_length=25)
