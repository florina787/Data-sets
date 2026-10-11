"""Session-scoped stores. One instance lives in each visitor's Streamlit session.

Nothing here touches disk or a shared database: when the session ends, the data is gone.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from services.validation import MAX_MEMORY_CHARS, ValidationError, clean_text, ensure_not_sensitive, validate_choice

MEMORY_CATEGORIES = ("Preferences", "Goals", "Projects", "Tasks", "Conversations", "Important notes")
CATEGORY_FLOWERS = {
    "Preferences": "🌸", "Goals": "🌻", "Projects": "🌷", "Tasks": "🌼", "Conversations": "🪻", "Important notes": "🌹",
}
MAX_MEMORIES = 200


class MemoryItem(BaseModel):
    id: str
    category: str
    text: str = Field(max_length=MAX_MEMORY_CHARS)
    created_at: str
    updated_at: str
    source: str = "user"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemoryStore:
    """CRUD + keyword search over a visitor's session memories."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._ids = itertools.count(1)

    def _validate(self, category: str, text: str) -> tuple[str, str]:
        category = validate_choice(category, MEMORY_CATEGORIES, "memory category")
        text = clean_text(text, max_chars=MAX_MEMORY_CHARS, field="Memory")
        ensure_not_sensitive(text, "Memory")
        return category, text

    def add(self, category: str, text: str, source: str = "user") -> MemoryItem:
        category, text = self._validate(category, text)
        if len(self._items) >= MAX_MEMORIES:
            raise ValidationError(f"The demo garden holds at most {MAX_MEMORIES} memories.")
        now = _now()
        item = MemoryItem(id=f"M{next(self._ids)}", category=category, text=text, created_at=now, updated_at=now, source=source)
        self._items[item.id] = item
        return item.model_copy()

    def update(self, memory_id: str, category: str, text: str) -> MemoryItem:
        if memory_id not in self._items:
            raise KeyError(memory_id)
        category, text = self._validate(category, text)
        item = self._items[memory_id].model_copy(update={"category": category, "text": text, "updated_at": _now()})
        self._items[memory_id] = item
        return item.model_copy()

    def delete(self, memory_id: str) -> None:
        self._items.pop(memory_id, None)

    def clear(self) -> None:
        self._items.clear()

    def all(self) -> list[MemoryItem]:
        return [item.model_copy() for item in self._items.values()]

    def search(self, query: str = "", category: str | None = None) -> list[MemoryItem]:
        terms = [t for t in query.lower().split() if len(t) > 2]
        results = []
        for item in self._items.values():
            if category and item.category != category:
                continue
            haystack = f"{item.category} {item.text}".lower()
            if not terms or any(term in haystack for term in terms):
                results.append(item.model_copy())
        return results

    def __len__(self) -> int:
        return len(self._items)


@dataclass
class SessionStores:
    """Every mutable thing a visitor's simulated actions can touch."""

    memory: MemoryStore = field(default_factory=MemoryStore)
    calendar_events: list[dict[str, Any]] = field(default_factory=list)
    outbox: list[dict[str, Any]] = field(default_factory=list)
    bookings: list[dict[str, Any]] = field(default_factory=list)
    form_submissions: list[dict[str, Any]] = field(default_factory=list)
    document_edits: dict[str, str] = field(default_factory=dict)
    task_board: list[dict[str, Any]] = field(default_factory=list)
