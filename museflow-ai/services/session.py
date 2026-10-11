"""Everything one visitor owns. Created per Streamlit session — never cached globally."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from services.demo_engine import DemoEngine

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "Unicorn Dream",
    "animation": "Gentle",  # Off | Gentle | Sparkly
    "reduced_motion": False,
    "show_avatar": True,
    "chat_style": "Bubbles",  # Bubbles | Compact
    "viz_style": "Graph",  # Graph | Timeline
    "typing_effect": True,
}


@dataclass
class SessionContext:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    engine: DemoEngine | None = None
    settings: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    chat: list[dict[str, Any]] = field(default_factory=list)
    pages_visited: set[str] = field(default_factory=set)
    celebrated: set[str] = field(default_factory=set)
    focus_run: str | None = None

    def __post_init__(self) -> None:
        if self.engine is None:
            self.engine = DemoEngine(self.session_id)


def new_session(today: date | None = None) -> SessionContext:
    session_id = uuid.uuid4().hex
    return SessionContext(session_id=session_id, engine=DemoEngine(session_id, today=today))
