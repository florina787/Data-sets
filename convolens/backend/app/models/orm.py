"""SQLAlchemy models.

Unit of analysis: a *conversation* is one reply tree (a connected component of the
reply graph rooted at a message with no in-dataset parent). Every message belongs
to exactly one conversation, so counts never double-count shared messages.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # demo | synthetic_multilingual | kaggle_twcs
    kind: Mapped[str] = mapped_column(String(40))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="importing")  # importing | ready | failed
    source: Mapped[str] = mapped_column(Text, default="")
    file_hash: Mapped[str | None] = mapped_column(String(64))
    sample_seed: Mapped[int | None] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    active_analysis: Mapped[str] = mapped_column(String(120), default="rules:rules-v1")
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    dataset_id: Mapped[str | None] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))  # upload | local_path | kaggle | demo | analysis
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|cancelled|failed|completed|interrupted
    stage: Mapped[str] = mapped_column(String(80), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(40))  # stable: hash(source kind + root source id)
    root_source_id: Mapped[str] = mapped_column(String(40))
    brand: Mapped[str | None] = mapped_column(String(80))  # support account handle (public brand account)
    message_count: Mapped[int] = mapped_column(Integer)
    customer_turns: Mapped[int] = mapped_column(Integer)
    support_turns: Mapped[int] = mapped_column(Integer)
    branch_count: Mapped[int] = mapped_column(Integer, default=0)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)
    completeness: Mapped[str] = mapped_column(String(20), default="complete")  # complete | partial
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_s: Mapped[float | None] = mapped_column(Float)
    content_hash: Mapped[str] = mapped_column(String(64))
    languages: Mapped[list] = mapped_column(JSON, default=list)
    # Effective labels = active analysis with reviewer corrections applied.
    primary_topic: Mapped[str] = mapped_column(String(40), default="unknown")
    secondary_topics: Mapped[list] = mapped_column(JSON, default=list)
    subtheme: Mapped[str | None] = mapped_column(String(60))
    resolution_status: Mapped[str] = mapped_column(String(40), default="unknown")
    sentiment_start: Mapped[str] = mapped_column(String(20), default="unknown")
    sentiment_end: Mapped[str] = mapped_column(String(20), default="unknown")
    escalation_requested: Mapped[str] = mapped_column(String(10), default="unknown")  # yes | no | unknown
    channel_handoff: Mapped[str] = mapped_column(String(12), default="unknown")  # observable; independent of labelling method
    handoff_evidence: Mapped[list] = mapped_column(JSON, default=list)
    analysis_id: Mapped[int | None] = mapped_column(Integer)
    corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.position")

    __table_args__ = (
        UniqueConstraint("dataset_id", "key"),
        Index("ix_conv_ds_topic", "dataset_id", "primary_topic"),
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(40))
    parent_source_id: Mapped[str | None] = mapped_column(String(40))
    author_ref: Mapped[str] = mapped_column(String(80))  # brand handle for support; salted hash for customers
    role: Mapped[str] = mapped_column(String(10))  # customer | support
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    position: Mapped[int] = mapped_column(Integer)  # chronological order inside conversation
    depth: Mapped[int] = mapped_column(Integer)
    child_count: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)  # REDACTED text - authoritative evidence
    redactions: Mapped[dict] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(16), default="unknown")  # iso code | mixed | unknown
    language_confidence: Mapped[float | None] = mapped_column(Float)
    language_detail: Mapped[dict] = mapped_column(JSON, default=dict)
    language_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    stage: Mapped[str | None] = mapped_column(String(30))  # inferred journey stage (rules)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    __table_args__ = (UniqueConstraint("dataset_id", "source_id"),)


class Exclusion(Base):
    """Threads not selected, with reason (one row per excluded reason bucket sample + counts in manifest)."""
    __tablename__ = "exclusions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    root_source_id: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(40))
    message_count: Mapped[int] = mapped_column(Integer)


class Analysis(Base):
    """Original per-conversation prediction. Never overwritten by corrections."""
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(20))  # rules | llm
    model_id: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64))
    source_text: Mapped[str] = mapped_column(String(20), default="original")  # original | translated
    fields: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | failed
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("conversation_id", "method", "model_id", "prompt_version", "content_hash", "source_text"),)


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # conversation | message
    target_id: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(40))
    original_value: Mapped[str | None] = mapped_column(Text)
    corrected_value: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewLabel(Base):
    """A blind human label set for one conversation: the gold standard that rules and model labels are scored against.
    Separate from Correction, which changes what dashboards show; a review never alters labels."""
    __tablename__ = "review_labels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(40), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str] = mapped_column(String(80))
    labels: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("conversation_id", "reviewer"),)


class EmbeddingCache(Base):
    """Remote embedding vectors keyed by (model, sha256 of the redacted text): paid for once, reused by every dataset."""
    __tablename__ = "embedding_cache"
    model: Mapped[str] = mapped_column(String(80), primary_key=True)
    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    dims: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Translation(Base):
    __tablename__ = "translations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    target_language: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(20))  # llm | reference (synthetic fixture)
    model_id: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Run(Base):
    """One Flo graph execution (request)."""
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # request_id
    session_id: Mapped[str] = mapped_column(String(40), index=True)
    dataset_id: Mapped[str | None] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="running")
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    response: Mapped[dict | None] = mapped_column(JSON)
    model_id: Mapped[str | None] = mapped_column(String(120))
    prompt_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    langsmith_run_id: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)  # 1 helpful, 0 not helpful
    comment: Mapped[str | None] = mapped_column(Text)
    correction: Mapped[str | None] = mapped_column(Text)
    sent_to_langsmith: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(40), index=True)
    run_id: Mapped[str | None] = mapped_column(String(40))
    dataset_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    dataset_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    issue: Mapped[str] = mapped_column(String(120))
    intervention: Mapped[str] = mapped_column(Text)
    proposed_department: Mapped[str | None] = mapped_column(String(120))
    owner: Mapped[str | None] = mapped_column(String(120))
    owner_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    due_date: Mapped[str | None] = mapped_column(String(10))
    intended_outcome: Mapped[str] = mapped_column(Text, default="")
    success_measure: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed|approved|in_progress|completed|rejected
    investigation: Mapped[dict] = mapped_column(JSON, default=dict)  # run id, question, filters, evidence ids
    brief: Mapped[dict] = mapped_column(JSON, default=dict)
    session_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    history: Mapped[list["ActionEvent"]] = relationship(order_by="ActionEvent.id", cascade="all, delete-orphan")


class ActionEvent(Base):
    __tablename__ = "action_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OpportunityReview(Base):
    """Reviewer inputs for an improvement candidate (effort, severity override)."""
    __tablename__ = "opportunity_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(40))
    candidate_key: Mapped[str] = mapped_column(String(80))
    effort: Mapped[int | None] = mapped_column(Integer)  # 1 (small) .. 5 (very large)
    effort_source: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[int | None] = mapped_column(Integer)
    reviewer: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("dataset_id", "candidate_key"),)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    suite: Mapped[str] = mapped_column(String(60))
    judgment: Mapped[str] = mapped_column(String(20))  # deterministic | human | llm_judge
    mode: Mapped[str] = mapped_column(String(20))
    system: Mapped[str] = mapped_column(String(120))  # e.g. rules:rules-v1 or llm:<model>:<prompt>
    language: Mapped[str] = mapped_column(String(16), default="all")
    n: Mapped[int] = mapped_column(Integer)
    passed: Mapped[int] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    langsmith_experiment: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImpactReview(Base):
    __tablename__ = "impact_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int | None] = mapped_column(Integer)
    dataset_id: Mapped[str] = mapped_column(String(40))
    intervention_date: Mapped[str] = mapped_column(String(10))
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    reviewer: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
