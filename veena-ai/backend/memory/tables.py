"""SQLite schema. Raw audio and screenshots are never stored here."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return uuid.uuid4().hex


class ChatSession(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str = "New conversation"
    mode: str = "conversation"  # conversation | screen | interview | meeting
    summary: str | None = None
    created_at: datetime = Field(default_factory=_now, index=True)
    updated_at: datetime = Field(default_factory=_now, index=True)


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True)
    role: str  # user | assistant | transcript | system
    content: str
    intent: str | None = None
    answer_style: str | None = None
    model: str | None = None
    citations_json: str | None = None
    meta_json: str | None = None
    created_at: datetime = Field(default_factory=_now, index=True)


class Collection(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    kind: str = "general"  # resume | project | docs | job | meeting | general
    created_at: datetime = Field(default_factory=_now)


class Document(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    collection_id: str = Field(foreign_key="collection.id", index=True)
    filename: str
    ext: str
    sha256: str = Field(index=True)
    pages: int = 0
    chunk_count: int = 0
    char_count: int = 0
    created_at: datetime = Field(default_factory=_now)


class Chunk(SQLModel, table=True):
    # The integer primary key doubles as the FAISS vector id.
    id: int | None = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key="document.id", index=True)
    collection_id: str = Field(index=True)
    page: int | None = None
    ordinal: int
    text: str
    created_at: datetime = Field(default_factory=_now)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_json: str


class MetricEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    value: float
    unit: str = "ms"
    meta_json: str | None = None
    created_at: datetime = Field(default_factory=_now, index=True)


class InterviewSession(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    chat_session_id: str = Field(foreign_key="chatsession.id", index=True)
    role: str
    resume_collection_id: str | None = None
    job_description: str | None = None
    focus: str = "mixed"  # behavioral | coding | architecture | leadership | mixed
    created_at: datetime = Field(default_factory=_now)


class InterviewTurn(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    interview_id: str = Field(foreign_key="interviewsession.id", index=True)
    ordinal: int
    category: str
    question: str
    answer: str | None = None
    score: float | None = None
    feedback_json: str | None = None
    created_at: datetime = Field(default_factory=_now)
