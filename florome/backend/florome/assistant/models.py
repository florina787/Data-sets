"""Assistant conversation memory (tenant- and user-scoped)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from florome.models import Base, new_id, utcnow


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("conv"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    page: Mapped[str] = mapped_column(String(30))
    focus: Mapped[dict[str, Any]] = mapped_column(default=dict)  # entities carried between turns (incident, hypothesis, last intent)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("msg"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("assistant_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    text: Mapped[str] = mapped_column(Text)
    answer: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
