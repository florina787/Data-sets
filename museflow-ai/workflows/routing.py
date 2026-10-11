"""Deterministic intent routing and supervisor edge selection.

The chat engine does NOT interpret arbitrary language. It matches a small, documented set
of intents with keyword rules and extracts parameters with regular expressions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from services import scenario_loader as fixtures
from workflows.state import MuseState

SPECIALIST_ORDER = ["memory", "research", "document", "calendar", "browser", "planning", "email", "analytics"]
AGENT_NODES = SPECIALIST_ORDER + ["governance", "approval", "simulate_action", "audit"]

NAV_PAGES = {
    "dashboard": "dashboard", "home": "dashboard", "chat": "chat", "memory": "memory", "garden": "memory",
    "agents": "agents", "universe": "agents", "planner": "planner", "task": "planner", "research": "research",
    "email": "email", "calendar": "calendar", "document": "documents", "browser": "browser",
    "workflow": "galaxy", "galaxy": "galaxy", "approval": "approvals", "analytics": "analytics",
    "governance": "governance", "trust": "governance", "achievement": "achievements", "settings": "settings",
}


@dataclass
class IntentMatch:
    intent: str
    scenario_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    matched: list[str] = field(default_factory=list)
    page: str | None = None


def _has(text: str, *patterns: str) -> list[str]:
    return [p for p in patterns if re.search(rf"\b{p}", text)]


def _research_topic(text: str) -> str:
    if _has(text, "crewai", "langgraph", "framework"):
        return "ai_frameworks"
    if _has(text, "industry", "market"):
        return "industry"
    if _has(text, "company", "starlace"):
        return "fictional_company"
    if _has(text, "architecture", "microservice", "monolith"):
        return "architectures"
    if _has(text, "strateg", "implement", "adopt"):
        return "ai_strategy"
    return "ai_frameworks"


def _email_params(text: str) -> dict[str, Any]:
    tones = list(fixtures.email_fixture()["tones"])
    params: dict[str, Any] = {}
    for tone in tones:
        if re.search(rf"\b{tone}", text):
            params["tone"] = tone
            break
    if _has(text, "thank"):
        params["email_scenario"] = "thank_you"
    elif _has(text, "meeting"):
        params["email_scenario"] = "meeting_request"
    elif _has(text, "update", "status report"):
        params["email_scenario"] = "project_update"
    elif _has(text, "intro"):
        params["email_scenario"] = "introduction"
    for role, words in {"client": ("client",), "mentor": ("mentor",), "team_lead": ("team lead", "manager", "boss"), "vendor": ("vendor", "supplier")}.items():
        if _has(text, *words):
            params["recipient_role"] = role
            break
    return params


def _document_id(text: str) -> str:
    table = [
        ("insurance_policy", ("insurance", "policy")),
        ("job_description", ("job", "description")),
        ("project_requirements", ("requirement",)),
        ("meeting_notes", ("meeting notes", "notes")),
        ("business_report", ("report", "business")),
        ("tech_spec", ("spec", "technical")),
    ]
    for doc_id, words in table:
        if _has(text, *words):
            return doc_id
    return "insurance_policy"


def _browser_task(text: str) -> str:
    if _has(text, "compare product", "lamp", "product"):
        return "compare_products"
    if _has(text, "form", "newsletter"):
        return "fill_form"
    if _has(text, "itinerary"):
        return "review_itinerary"
    if _has(text, "book", "reserve"):
        return "booking"
    return "hotel_search"


def _memory_category(text: str) -> str:
    if _has(text, "prefer", "like", "love", "favou?rite", "enjoy"):
        return "Preferences"
    if _has(text, "goal", "want to", "aim", "dream"):
        return "Goals"
    if _has(text, "project"):
        return "Projects"
    if _has(text, "todo", "to-do", "task", "need to"):
        return "Tasks"
    return "Important notes"


def classify_intent(raw: str) -> IntentMatch:
    """Map a chat message to one supported intent (or ``unsupported``)."""
    text = raw.lower().strip()

    remember = re.search(r"\bremember(?: that)?\s+(.+)", raw, re.I)
    if remember and not _has(text, "what do you remember"):
        body = remember.group(1).strip().rstrip(".!") + "."
        return IntentMatch("memory_add", "personal_memory",
                           {"operation": "add", "category": _memory_category(body.lower()), "text": body[:280]}, ["remember"])
    if hits := _has(text, "what do you remember", "what do you know about me", "recall", "my memories"):
        about = re.search(r"\babout\s+(?!me\b)(.+?)[?.!]*$", text)
        return IntentMatch("memory_recall", "memory_recall", {"operation": "search", "query": about.group(1) if about else ""}, hits)
    nav = re.match(r"^(?:go to|open|show me|take me to|navigate to)\s+(?:the\s+)?(.+)", text)
    if nav:
        for word, page in NAV_PAGES.items():
            if word in nav.group(1):
                return IntentMatch("navigation", page=page, matched=[word])
    if hits := _has(text, "dream team", "agent team", "all agents", "launch my"):
        return IntentMatch("agent_orchestration", "dream_team", {}, hits)
    if (hits := _has(text, "status", "pending", "what's running", "approvals?")) and not _has(text, "email", "draft", "update"):
        return IntentMatch("workflow_status", matched=hits)
    if hits := _has(text, "interview"):
        return IntentMatch("interview", "interview_prep", {}, hits)
    if hits := _has(text, r"week\b", "weekly"):
        if _has(text, "plan", "organi[sz]e", "schedule", "productive"):
            return IntentMatch("calendar_planning", "weekly_planning", {}, hits)
    if hits := _has(text, "getaway", "trip", "travel", "vacation", "holiday"):
        return IntentMatch("travel", "travel_planning", {"budget": "low" if _has(text, "cheap", "budget", "low") else "high" if _has(text, "luxur", "splurge") else "mid",
                                                          "vibe": "adventurous" if _has(text, "adventur", "hike", "active") else "cultural" if _has(text, "cultur", "museum", "city") else "relaxing"}, hits)
    if hits := _has(text, "book", "hotel", "browse", "website", r"form\b", "itinerary", "compare product"):
        return IntentMatch("browser", "browser", {"task": _browser_task(text)}, hits)
    if hits := _has(text, "email", "e-mail", "draft", "follow-up", "follow up", "reply"):
        return IntentMatch("email", "email_followup", _email_params(text), hits)
    if hits := _has(text, "schedule", "meeting", "appointment", "calendar"):
        return IntentMatch("calendar", "schedule_meeting", {}, hits)
    if hits := _has(text, "research", "compare", "langgraph", "crewai", "industry", "architecture", "strateg"):
        return IntentMatch("research", "research", {"topic": _research_topic(text)}, hits)
    if hits := _has(text, "document", "summari[sz]e", "summary", "analy[sz]e", "policy", "insurance", "notes"):
        return IntentMatch("document", "document_analysis", {"document_id": _document_id(text)}, hits)
    if hits := _has(text, "project", "presentation", "task", "plan", "organi[sz]e"):
        template = "presentation" if _has(text, "presentation") else "project"
        return IntentMatch("task_planning", "project_planning", {"plan_template": template}, hits)
    if hits := _has(text, "hello", r"hi\b", r"hey\b", "good morning", "good afternoon", "good evening", "greetings"):
        return IntentMatch("greeting", matched=hits)
    if hits := _has(text, "help", "what can you do", "how do", "how does"):
        return IntentMatch("help", matched=hits)
    return IntentMatch("unsupported")


def research_has_matrix(topic: str) -> bool:
    return bool(fixtures.research_fixture()["topics"][topic].get("matrix"))


def build_queue(scenario_id: str, params: dict[str, Any]) -> list[str]:
    """Initial agent queue for a scenario. Agents may extend it at run time."""
    spec = fixtures.get_scenario(scenario_id)
    queue = list(spec.specialists)
    if scenario_id == "research" and research_has_matrix(params["topic"]):
        queue.append("analytics")
    if spec.governance:
        queue.append("governance")
    queue.append("audit")
    return queue


def route_from_supervisor(state: MuseState) -> str:
    """Conditional edge: the supervisor's next hop is the head of the queue."""
    queue = state.get("queue") or []
    return queue[0] if queue and queue[0] in AGENT_NODES else "respond"
