"""Session, message and settings persistence (working + session + persistent memory)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_
from sqlalchemy.engine import Engine
from sqlmodel import col, select

from .db import session as db_session
from .tables import (
    ChatSession,
    InterviewSession,
    InterviewTurn,
    Message,
    MetricEvent,
    Setting,
)

# Placeholder titles, replaced by the first question asked in the session.
DEFAULT_TITLES = {
    "conversation": "New conversation",
    "screen": "Screen session",
    "meeting": "Meeting",
    "interview": "Practice interview",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "onboarded": False,
    "profile": None,  # lite | balanced | performance
    "text_model": None,
    "vision_model": None,
    "asr_model": "base",
    "asr_language": None,  # None = auto-detect
    "answer_style": "quick",
    "retention_days": 30,  # 0 keeps history until deleted by the user
    "redact_screens": True,
    "pause_on_sensitive": True,
    "question_escalation": True,
    "auto_answer_questions": True,
    "context_turns": 8,
    "continuous_interval_s": 5,
    "speak_interviewer": False,
}


class Store:
    def __init__(self, engine: Engine):
        self.engine = engine

    # ---------- settings ----------
    def get_settings(self) -> dict[str, Any]:
        out = dict(DEFAULT_SETTINGS)
        with db_session(self.engine) as s:
            for row in s.exec(select(Setting)):
                out[row.key] = json.loads(row.value_json)
        return out

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        unknown = set(patch) - set(DEFAULT_SETTINGS)
        if unknown:
            raise KeyError(f"unknown settings: {sorted(unknown)}")
        with db_session(self.engine) as s:
            for k, v in patch.items():
                s.merge(Setting(key=k, value_json=json.dumps(v)))
            s.commit()
        return self.get_settings()

    # ---------- sessions ----------
    def create_session(self, title: str | None = None, mode: str = "conversation") -> ChatSession:
        with db_session(self.engine) as s:
            cs = ChatSession(title=(title or DEFAULT_TITLES.get(mode, "New conversation"))[:200], mode=mode)
            s.add(cs)
            s.commit()
            s.refresh(cs)
            return cs

    def get_session(self, session_id: str) -> ChatSession | None:
        with db_session(self.engine) as s:
            return s.get(ChatSession, session_id)

    def list_sessions(self, query: str | None = None, mode: str | None = None, limit: int = 100) -> list[dict]:
        with db_session(self.engine) as s:
            stmt = select(ChatSession)
            if mode:
                stmt = stmt.where(ChatSession.mode == mode)
            if query:
                like = f"%{query}%"
                sub = select(Message.session_id).where(col(Message.content).ilike(like))
                stmt = stmt.where(or_(col(ChatSession.title).ilike(like), col(ChatSession.id).in_(sub)))
            stmt = stmt.order_by(col(ChatSession.updated_at).desc()).limit(limit)
            rows = list(s.exec(stmt))
            counts = dict(
                s.exec(
                    select(Message.session_id, func.count())
                    .where(col(Message.session_id).in_([r.id for r in rows]))
                    .group_by(Message.session_id)
                ).all()
            )
            return [{**r.model_dump(mode="json"), "message_count": counts.get(r.id, 0)} for r in rows]

    def rename_session(self, session_id: str, title: str) -> ChatSession | None:
        with db_session(self.engine) as s:
            cs = s.get(ChatSession, session_id)
            if not cs:
                return None
            cs.title = title[:200]
            s.add(cs)
            s.commit()
            s.refresh(cs)
            return cs

    def set_summary(self, session_id: str, summary: str) -> None:
        with db_session(self.engine) as s:
            cs = s.get(ChatSession, session_id)
            if cs:
                cs.summary = summary
                s.add(cs)
                s.commit()

    def delete_session(self, session_id: str) -> bool:
        with db_session(self.engine) as s:
            cs = s.get(ChatSession, session_id)
            if not cs:
                return False
            self._delete_sessions(s, [session_id])
            s.commit()
            return True

    def clear_history(self) -> int:
        with db_session(self.engine) as s:
            ids = list(s.exec(select(ChatSession.id)))
            self._delete_sessions(s, ids)
            s.exec(delete(MetricEvent))
            s.commit()
            return len(ids)

    def purge_expired(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        with db_session(self.engine) as s:
            ids = list(s.exec(select(ChatSession.id).where(ChatSession.updated_at < cutoff)))
            self._delete_sessions(s, ids)
            s.commit()
            return len(ids)

    @staticmethod
    def _delete_sessions(s, ids: list[str]) -> None:
        if not ids:
            return
        iv_ids = list(s.exec(select(InterviewSession.id).where(col(InterviewSession.chat_session_id).in_(ids))))
        if iv_ids:
            s.exec(delete(InterviewTurn).where(col(InterviewTurn.interview_id).in_(iv_ids)))
            s.exec(delete(InterviewSession).where(col(InterviewSession.id).in_(iv_ids)))
        s.exec(delete(Message).where(col(Message.session_id).in_(ids)))
        s.exec(delete(ChatSession).where(col(ChatSession.id).in_(ids)))

    # ---------- messages ----------
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        intent: str | None = None,
        answer_style: str | None = None,
        model: str | None = None,
        citations: list[dict] | None = None,
        meta: dict | None = None,
    ) -> Message:
        with db_session(self.engine) as s:
            m = Message(
                session_id=session_id,
                role=role,
                content=content,
                intent=intent,
                answer_style=answer_style,
                model=model,
                citations_json=json.dumps(citations) if citations else None,
                meta_json=json.dumps(meta) if meta else None,
            )
            s.add(m)
            cs = s.get(ChatSession, session_id)
            if cs:
                cs.updated_at = datetime.now(UTC)
                if cs.title in DEFAULT_TITLES.values() and role == "user":
                    cs.title = content.strip().splitlines()[0][:80] or cs.title
                s.add(cs)
            s.commit()
            s.refresh(m)
            return m

    def messages(self, session_id: str, limit: int | None = None) -> list[dict]:
        with db_session(self.engine) as s:
            stmt = select(Message).where(Message.session_id == session_id).order_by(col(Message.id).desc())
            if limit:
                stmt = stmt.limit(limit)
            rows = list(s.exec(stmt))[::-1]
            return [self._message_dict(m) for m in rows]

    @staticmethod
    def _message_dict(m: Message) -> dict:
        d = m.model_dump(mode="json", exclude={"citations_json", "meta_json"})
        d["citations"] = json.loads(m.citations_json) if m.citations_json else []
        d["meta"] = json.loads(m.meta_json) if m.meta_json else {}
        return d

    def recent_history(self, session_id: str, turns: int) -> list[dict[str, str]]:
        """Chat-format working memory: last N user/assistant messages."""
        msgs = [m for m in self.messages(session_id, limit=turns * 3) if m["role"] in ("user", "assistant")]
        return [{"role": m["role"], "content": m["content"]} for m in msgs[-turns * 2 :]]

    def export_session(self, session_id: str, fmt: str = "markdown") -> str | None:
        cs = self.get_session(session_id)
        if not cs:
            return None
        msgs = self.messages(session_id)
        if fmt == "json":
            return json.dumps({"session": cs.model_dump(mode="json"), "messages": msgs}, indent=2)
        lines = [f"# {cs.title}", "", f"_Mode: {cs.mode} · Started {cs.created_at:%Y-%m-%d %H:%M} UTC_", ""]
        if cs.summary:
            lines += ["## Summary", "", cs.summary, ""]
        labels = {"user": "You", "assistant": "VEENA", "transcript": "Transcript", "system": "System"}
        for m in msgs:
            lines.append(f"**{labels.get(m['role'], m['role'])}** ({m['created_at'][:19].replace('T', ' ')})")
            lines.append("")
            lines.append(m["content"])
            for c in m["citations"]:
                page = f", p.{c['page']}" if c.get("page") else ""
                lines.append(f"> [{c.get('n', '')}] {c.get('filename', '')}{page}")
            lines.append("")
        return "\n".join(lines)

    # ---------- metrics ----------
    def record_metric(self, name: str, value: float, unit: str = "ms", meta: dict | None = None) -> None:
        with db_session(self.engine) as s:
            s.add(MetricEvent(name=name, value=value, unit=unit, meta_json=json.dumps(meta) if meta else None))
            s.commit()

    def metric_events(self, since: datetime | None = None, names: list[str] | None = None) -> list[MetricEvent]:
        with db_session(self.engine) as s:
            stmt = select(MetricEvent)
            if since:
                stmt = stmt.where(MetricEvent.created_at >= since)
            if names:
                stmt = stmt.where(col(MetricEvent.name).in_(names))
            return list(s.exec(stmt.order_by(col(MetricEvent.id))))

    def counts(self) -> dict[str, Any]:
        with db_session(self.engine) as s:
            by_mode = dict(s.exec(select(ChatSession.mode, func.count()).group_by(ChatSession.mode)).all())
            intents = dict(
                s.exec(
                    select(Message.intent, func.count())
                    .where(Message.role == "user", col(Message.intent).is_not(None))
                    .group_by(Message.intent)
                ).all()
            )
            total_msgs = s.exec(select(func.count()).select_from(Message)).one()
            return {"sessions_by_mode": by_mode, "question_categories": intents, "messages": total_msgs}
