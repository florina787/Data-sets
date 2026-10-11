"""Loads immutable, bundled demo fixtures.

Fixtures are read once per process (``lru_cache``) and validated with Pydantic.
Callers receive deep copies so no visitor can mutate shared fixture data.
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPECIALIST_KEYS = {"planning", "research", "memory", "email", "calendar", "document", "browser", "analytics"}


class ScenarioSpec(BaseModel):
    id: str
    title: str
    emoji: str
    prompt: str
    description: str
    specialists: list[str]
    governance: bool
    dynamic: bool = False
    showcase: bool = False
    minutes_saved_estimate: int = Field(ge=0)
    default_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("specialists")
    @classmethod
    def _known_specialists(cls, value: list[str]) -> list[str]:
        unknown = set(value) - SPECIALIST_KEYS
        if unknown:
            raise ValueError(f"unknown specialists: {sorted(unknown)}")
        return value


class AgentProfile(BaseModel):
    key: str
    name: str
    emoji: str
    role: str
    color: str
    personality: str
    capabilities: list[str]
    tools: list[str]
    scenarios: list[str]


class DocumentMeta(BaseModel):
    id: str
    file: str
    title: str
    type: str
    emoji: str
    glossary_topic: str
    key_fields: list[str]


def _read_json(relative: str) -> Any:
    path = DATA_DIR / relative
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)  # JSON only: no unsafe deserialisation


@lru_cache(maxsize=None)
def _scenarios() -> tuple[ScenarioSpec, ...]:
    raw = _read_json("scenarios/registry.json")
    return tuple(ScenarioSpec(**item) for item in raw["scenarios"])


@lru_cache(maxsize=None)
def _agents() -> tuple[AgentProfile, ...]:
    return tuple(AgentProfile(**item) for item in _read_json("agents.json")["agents"])


@lru_cache(maxsize=None)
def _documents() -> tuple[DocumentMeta, ...]:
    return tuple(DocumentMeta(**item) for item in _read_json("documents/index.json")["documents"])


@lru_cache(maxsize=None)
def _fixture(relative: str) -> Any:
    return _read_json(relative)


@lru_cache(maxsize=None)
def _document_text(doc_id: str) -> str:
    meta = get_document_meta(doc_id)
    return (DATA_DIR / "documents" / meta.file).read_text(encoding="utf-8")


# ---- public accessors (always return copies) -------------------------------------------

def list_scenarios(showcase_only: bool = False) -> list[ScenarioSpec]:
    items = [s for s in _scenarios() if s.showcase or not showcase_only]
    return [s.model_copy(deep=True) for s in items]


def get_scenario(scenario_id: str) -> ScenarioSpec:
    for spec in _scenarios():
        if spec.id == scenario_id:
            return spec.model_copy(deep=True)
    raise KeyError(f"Unknown scenario: {scenario_id}")


def scenario_ids() -> set[str]:
    return {s.id for s in _scenarios()}


def list_agents() -> list[AgentProfile]:
    return [a.model_copy(deep=True) for a in _agents()]


def get_agent(key: str) -> AgentProfile:
    for agent in _agents():
        if agent.key == key:
            return agent.model_copy(deep=True)
    raise KeyError(f"Unknown agent: {key}")


def list_documents() -> list[DocumentMeta]:
    return [d.model_copy(deep=True) for d in _documents()]


def get_document_meta(doc_id: str) -> DocumentMeta:
    for doc in _documents():
        if doc.id == doc_id:
            return doc.model_copy(deep=True)
    raise KeyError(f"Unknown document: {doc_id}")


def get_document_text(doc_id: str) -> str:
    return _document_text(doc_id)


def research_fixture() -> dict[str, Any]:
    return copy.deepcopy(_fixture("scenarios/research.json"))


def planning_fixture() -> dict[str, Any]:
    return copy.deepcopy(_fixture("scenarios/planning.json"))


def browser_fixture() -> dict[str, Any]:
    return copy.deepcopy(_fixture("scenarios/browser.json"))


def travel_fixture() -> dict[str, Any]:
    return copy.deepcopy(_fixture("scenarios/travel.json"))


def email_fixture() -> dict[str, Any]:
    return copy.deepcopy(_fixture("synthetic_emails.json"))


def calendar_fixture() -> dict[str, Any]:
    return copy.deepcopy(_fixture("synthetic_calendar.json"))


def week_start(today: date) -> date:
    """Monday of the planning week: this week on weekdays, next week on Saturday/Sunday."""
    monday = today - timedelta(days=today.weekday())
    return monday + timedelta(days=7) if today.weekday() >= 5 else monday


def resolve_calendar_events(today: date) -> list[dict[str, Any]]:
    """Turn relative fixture events into concrete dates anchored on this week's Monday."""
    monday = week_start(today)
    events = []
    for event in calendar_fixture()["events"]:
        day = monday + timedelta(days=int(event["day_offset"]))
        events.append({**event, "date": day.isoformat(), "source": "fixture"})
    return events


def parse_hhmm(value: str) -> int:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def format_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
