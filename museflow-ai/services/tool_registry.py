"""Allowlisted, simulated tools.

Every tool an agent can use is declared here. Tools marked ``consequential`` represent
real-world side effects; in the public demo they only append to session-scoped lists, and
they refuse to run unless the caller proves a human approval was recorded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable

from services import scenario_loader as fixtures
from services.memory_store import SessionStores


class ToolNotAllowedError(PermissionError):
    """Raised for any tool outside the allowlist or without the required approval."""


ToolHandler = Callable[["ToolEnv", dict[str, Any]], Any]


@dataclass
class ToolEnv:
    stores: SessionStores
    today: date


@dataclass(frozen=True)
class ToolSpec:
    name: str
    agent: str
    description: str
    consequential: bool
    handler: ToolHandler


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- handlers ---------------------------------------------------------------------------

def _research_lookup(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    topics = fixtures.research_fixture()["topics"]
    topic = args["topic"]
    if topic not in topics:
        raise KeyError(f"Unknown research topic {topic!r}")
    return topics[topic]


def _travel_destinations(env: ToolEnv, args: dict[str, Any]) -> list[dict[str, Any]]:
    return fixtures.travel_fixture()["destinations"]


def _memory_add(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return env.stores.memory.add(args["category"], args["text"], source=args.get("source", "agent")).model_dump()


def _memory_search(env: ToolEnv, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [m.model_dump() for m in env.stores.memory.search(args.get("query", ""), args.get("category"))]


def _calendar_read(env: ToolEnv, args: dict[str, Any]) -> list[dict[str, Any]]:
    events = fixtures.resolve_calendar_events(env.today) + [dict(e) for e in env.stores.calendar_events]
    return sorted(events, key=lambda e: (e["date"], e["start"]))


def _document_read(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    doc_id = args["document_id"]
    meta = fixtures.get_document_meta(doc_id)
    text = env.stores.document_edits.get(doc_id) or fixtures.get_document_text(doc_id)
    return {"meta": meta.model_dump(), "text": text}


def _email_templates(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return fixtures.email_fixture()


def _planning_templates(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return fixtures.planning_fixture()


def _browser_navigate(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    tasks = fixtures.browser_fixture()["tasks"]
    task = tasks[args["task"]]
    return {"url": task["url"], "title": task["title"], "page_data": task["page_data"], "form": task["form"]}


def _browser_fill_form(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return {"filled_fields": sorted(args.get("form", {}).keys()), "submitted": False}


def _append(target: list[dict[str, Any]], payload: dict[str, Any], prefix: str) -> dict[str, Any]:
    record = {**payload, "confirmation": f"{prefix}-{len(target) + 1:04d}", "simulated": True, "at": _stamp()}
    target.append(record)
    return record


def _email_send(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return _append(env.stores.outbox, args, "SIM-MAIL")


def _calendar_create(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    event = {
        "id": f"S{len(env.stores.calendar_events) + 1}", "title": args["title"], "date": args["date"],
        "start": args["start"], "end": args["end"], "category": args.get("category", "simulated"), "source": "session",
    }
    env.stores.calendar_events.append(event)
    return {**event, "confirmation": f"SIM-CAL-{len(env.stores.calendar_events):04d}", "simulated": True}


def _browser_submit(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return _append(env.stores.form_submissions, args, "SIM-FORM")


def _browser_booking(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return _append(env.stores.bookings, args, "SIM-BOOK")


def _travel_hold(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    return _append(env.stores.bookings, args, "SIM-TRIP")


def _document_modify(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    env.stores.document_edits[args["document_id"]] = args["new_text"]
    return {"document_id": args["document_id"], "simulated": True, "chars": len(args["new_text"])}


def _planning_schedule(env: ToolEnv, args: dict[str, Any]) -> dict[str, Any]:
    for task in args.get("tasks", []):
        env.stores.task_board.append({**task, "done": False, "plan": args.get("plan_title", "")})
    return {"scheduled": len(args.get("tasks", [])), "simulated": True}


def default_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec("research.lookup_fixture", "research", "Read a curated synthetic research fixture", False, _research_lookup),
        ToolSpec("travel.list_destinations", "research", "Read fictional destinations", False, _travel_destinations),
        ToolSpec("memory.add", "memory", "Add a validated memory to this session", False, _memory_add),
        ToolSpec("memory.search", "memory", "Keyword search over this session's memories", False, _memory_search),
        ToolSpec("calendar.read_events", "calendar", "Read fictional + session calendar events", False, _calendar_read),
        ToolSpec("document.read_fixture", "document", "Read a bundled synthetic document", False, _document_read),
        ToolSpec("email.compose_draft", "email", "Load synthetic email templates", False, _email_templates),
        ToolSpec("planning.build_plan", "planning", "Load task templates", False, _planning_templates),
        ToolSpec("browser.simulate_navigate", "browser", "Read a fictional page from fixtures", False, _browser_navigate),
        ToolSpec("browser.simulate_fill_form", "browser", "Fill a fictional form in memory", False, _browser_fill_form),
        # Consequential (simulated) actions — require approval.
        ToolSpec("email.simulate_send", "email", "SIMULATE sending an email (session outbox only)", True, _email_send),
        ToolSpec("calendar.simulate_create_event", "calendar", "SIMULATE adding an appointment", True, _calendar_create),
        ToolSpec("browser.simulate_submit_form", "browser", "SIMULATE submitting a form", True, _browser_submit),
        ToolSpec("browser.simulate_booking", "browser", "SIMULATE completing a booking", True, _browser_booking),
        ToolSpec("travel.simulate_hold_itinerary", "planning", "SIMULATE holding a fictional itinerary", True, _travel_hold),
        ToolSpec("document.simulate_modify", "document", "SIMULATE modifying a document (session copy)", True, _document_modify),
        ToolSpec("planning.simulate_schedule_tasks", "planning", "SIMULATE scheduling plan tasks", True, _planning_schedule),
    ]


@dataclass
class ToolRegistry:
    specs: dict[str, ToolSpec] = field(default_factory=lambda: {s.name: s for s in default_tool_specs()})

    def allowlist(self) -> list[str]:
        return sorted(self.specs)

    def is_allowed(self, name: str) -> bool:
        return name in self.specs

    def is_consequential(self, name: str) -> bool:
        if name not in self.specs:
            raise ToolNotAllowedError(f"Tool {name!r} is not on the allowlist.")
        return self.specs[name].consequential

    def execute(self, name: str, args: dict[str, Any], env: ToolEnv, *, approved: bool = False) -> Any:
        spec = self.specs.get(name)
        if spec is None:
            raise ToolNotAllowedError(f"Tool {name!r} is not on the allowlist.")
        if spec.consequential and not approved:
            raise ToolNotAllowedError(f"Tool {name!r} is consequential and needs a recorded human approval.")
        return spec.handler(env, dict(args))


def _summarize(value: Any, limit: int = 140) -> str:
    text = repr(value) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ToolRecorder:
    """Per-node wrapper that records every tool call into the execution trace."""

    def __init__(self, registry: ToolRegistry, env: ToolEnv) -> None:
        self.registry = registry
        self.env = env
        self.calls: list[dict[str, Any]] = []

    def call(self, name: str, args: dict[str, Any] | None = None, *, approved: bool = False) -> Any:
        args = args or {}
        record: dict[str, Any] = {
            "tool": name,
            "args": {k: _summarize(v, 60) for k, v in args.items()},
            "consequential": bool(self.registry.specs[name].consequential) if name in self.registry.specs else None,
        }
        try:
            result = self.registry.execute(name, args, self.env, approved=approved)
        except Exception as exc:
            record.update(ok=False, result=f"{type(exc).__name__}: {exc}")
            self.calls.append(record)
            raise
        record.update(ok=True, result=_summarize(result))
        self.calls.append(record)
        return result
