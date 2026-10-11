"""Strict, allowlist-based validation of scenario parameters.

Every workflow input passes through here before any agent runs. Unknown keys are rejected.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from services import scenario_loader as fixtures
from services.validation import (
    MAX_TITLE_CHARS,
    MAX_UPLOAD_BYTES,
    ValidationError,
    clean_text,
    ensure_not_sensitive,
    validate_choice,
    validate_time,
)
from services.memory_store import MEMORY_CATEGORIES

DREAM_TEAM_GOALS = ("research", "calendar", "email", "analytics", "document", "memory", "browser")
PRIORITIES = ("low", "medium", "high")
BUDGETS = ("low", "mid", "high")
VIBES = ("relaxing", "adventurous", "cultural")
DOC_EDITS = ("add_review_note", "add_summary_header")
DURATIONS = (15, 30, 45, 60, 90, 120)
ASSIGNEES = ("auto", "planning", "research", "memory", "email", "calendar", "document", "browser", "analytics")


def _int(value: Any, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValidationError(f"{field} must be a whole number between {low} and {high}.")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be true or false.")
    return value


def _doc_id(value: Any) -> str:
    return validate_choice(value, [d.id for d in fixtures.list_documents()], "document")


def _safe_text(value: Any, field: str, max_chars: int, allow_empty: bool = False) -> str:
    text = clean_text(value, max_chars=max_chars, field=field, allow_empty=allow_empty)
    ensure_not_sensitive(text, field)
    return text


def _interview(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": _doc_id(p["document_id"]),
        "role": _safe_text(p["role"], "Role", MAX_TITLE_CHARS),
        "days_until": _int(p["days_until"], "Days until interview", 1, 60),
    }


def _email(p: dict[str, Any]) -> dict[str, Any]:
    fx = fixtures.email_fixture()
    out = {
        "email_scenario": validate_choice(p["email_scenario"], list(fx["scenarios"]), "email scenario"),
        "recipient_role": validate_choice(p["recipient_role"], list(fx["recipients"]), "recipient"),
        "tone": validate_choice(p["tone"], list(fx["tones"]), "tone"),
    }
    if p.get("custom_subject"):
        out["custom_subject"] = _safe_text(p["custom_subject"], "Subject", 120)
    if p.get("custom_body"):
        out["custom_body"] = _safe_text(p["custom_body"], "Email body", 2000)
    return out


def _weekly(p: dict[str, Any]) -> dict[str, Any]:
    return {"plan_template": validate_choice(p["plan_template"], ["week"], "plan template")}


def _research(p: dict[str, Any]) -> dict[str, Any]:
    return {"topic": validate_choice(p["topic"], fixtures.research_fixture()["studio_topics"], "research topic")}


def _document(p: dict[str, Any]) -> dict[str, Any]:
    if p.get("document_id") == "upload":
        return {
            "document_id": "upload",
            "upload_name": clean_text(p.get("upload_name", "upload.txt"), max_chars=120, field="File name"),
            "upload_text": clean_text(p.get("upload_text", ""), max_chars=MAX_UPLOAD_BYTES, field="Uploaded text"),
        }
    return {"document_id": _doc_id(p["document_id"])}


def _travel(p: dict[str, Any]) -> dict[str, Any]:
    return {"budget": validate_choice(p["budget"], BUDGETS, "budget"), "vibe": validate_choice(p["vibe"], VIBES, "vibe")}


def _browser(p: dict[str, Any]) -> dict[str, Any]:
    return {"task": validate_choice(p["task"], list(fixtures.browser_fixture()["tasks"]), "browser task")}


def _memory_add(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation": validate_choice(p["operation"], ["add"], "operation"),
        "category": validate_choice(p["category"], MEMORY_CATEGORIES, "memory category"),
        "text": _safe_text(p["text"], "Memory", 280),
    }


def _memory_recall(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation": validate_choice(p["operation"], ["search"], "operation"),
        "query": clean_text(p.get("query", ""), max_chars=100, field="Query", allow_empty=True),
    }


def _project(p: dict[str, Any]) -> dict[str, Any]:
    out = {
        "plan_template": validate_choice(p["plan_template"], list(fixtures.planning_fixture()["templates"]), "plan template"),
        "priority": validate_choice(p["priority"], PRIORITIES, "priority"),
        "execute": _bool(p.get("execute", False), "execute"),
        "assignee": validate_choice(p.get("assignee", "auto"), ASSIGNEES, "assignee"),
    }
    if p.get("target_date"):
        try:
            out["target_date"] = date.fromisoformat(str(p["target_date"])).isoformat()
        except ValueError as exc:
            raise ValidationError("Target date must be YYYY-MM-DD.") from exc
    return out


def _dream_team(p: dict[str, Any]) -> dict[str, Any]:
    goals = p.get("goals")
    if not isinstance(goals, list) or not goals:
        raise ValidationError("Pick at least one goal for the dream team.")
    for goal in goals:
        validate_choice(goal, DREAM_TEAM_GOALS, "dream-team goal")
    ordered = [g for g in DREAM_TEAM_GOALS if g in goals]
    return {"goals": ordered}


def _schedule(p: dict[str, Any]) -> dict[str, Any]:
    duration = p["duration_min"]
    if duration not in DURATIONS:
        raise ValidationError(f"Duration must be one of {DURATIONS} minutes.")
    return {
        "title": _safe_text(p["title"], "Meeting title", MAX_TITLE_CHARS),
        "day_offset": _int(p["day_offset"], "Day", 0, 27),
        "start": validate_time(p["start"], "Start time"),
        "duration_min": duration,
    }


def _doc_edit(p: dict[str, Any]) -> dict[str, Any]:
    return {"document_id": _doc_id(p["document_id"]), "edit": validate_choice(p["edit"], DOC_EDITS, "edit")}


VALIDATORS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "interview_prep": _interview,
    "email_followup": _email,
    "weekly_planning": _weekly,
    "research": _research,
    "document_analysis": _document,
    "travel_planning": _travel,
    "browser": _browser,
    "personal_memory": _memory_add,
    "memory_recall": _memory_recall,
    "project_planning": _project,
    "dream_team": _dream_team,
    "schedule_meeting": _schedule,
    "document_edit": _doc_edit,
}

ALLOWED_KEYS: dict[str, set[str]] = {
    "interview_prep": {"document_id", "role", "days_until"},
    "email_followup": {"email_scenario", "recipient_role", "tone", "custom_subject", "custom_body"},
    "weekly_planning": {"plan_template"},
    "research": {"topic"},
    "document_analysis": {"document_id", "upload_name", "upload_text"},
    "travel_planning": {"budget", "vibe"},
    "browser": {"task"},
    "personal_memory": {"operation", "category", "text"},
    "memory_recall": {"operation", "query"},
    "project_planning": {"plan_template", "priority", "execute", "assignee", "target_date"},
    "dream_team": {"goals"},
    "schedule_meeting": {"title", "day_offset", "start", "duration_min"},
    "document_edit": {"document_id", "edit"},
}


def validate_params(scenario_id: str, params: dict[str, Any] | None) -> dict[str, Any]:
    if scenario_id not in VALIDATORS:
        raise ValidationError(f"Unsupported scenario: {scenario_id!r}.")
    if params is not None and not isinstance(params, dict):
        raise ValidationError("Parameters must be a mapping.")
    unknown = set(params or {}) - ALLOWED_KEYS[scenario_id]
    if unknown:
        raise ValidationError(f"Unsupported parameter(s) for {scenario_id}: {sorted(unknown)}.")
    merged = {**fixtures.get_scenario(scenario_id).default_params, **(params or {})}
    try:
        return VALIDATORS[scenario_id](merged)
    except KeyError as exc:
        raise ValidationError(f"Missing parameter: {exc.args[0]}") from exc
