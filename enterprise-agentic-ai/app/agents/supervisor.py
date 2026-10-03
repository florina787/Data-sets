"""Supervisor agent: classifies intent, plans the route and decides when work is complete."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.agents.prompts import SUPERVISOR_SYSTEM
from app.graph.state import CopilotState
from app.llm.provider import LLMError, LLMProvider, estimate_tokens
from app.models.domain import AgentName, Intent, TokenUsage
from app.tools.repository import EnterpriseDataRepository

logger = logging.getLogger(__name__)

# Which specialist agents each intent needs, in execution order.
ROUTING_PLANS: dict[Intent, list[AgentName]] = {
    Intent.PROJECT_STATUS: [AgentName.RAG, AgentName.TOOLS],
    Intent.RISK_ANALYSIS: [AgentName.RAG, AgentName.ANALYSIS],
    Intent.SUMMARIZATION: [AgentName.RAG, AgentName.ANALYSIS],
    Intent.ISSUE_LOOKUP: [AgentName.TOOLS],
    Intent.COMPARISON: [AgentName.RAG, AgentName.TOOLS, AgentName.ANALYSIS],
    Intent.ACTION_PLANNING: [AgentName.RAG, AgentName.TOOLS, AgentName.ANALYSIS],
    Intent.PEOPLE_LOOKUP: [AgentName.TOOLS],
    Intent.GENERAL_QA: [AgentName.RAG],
}

# Ordered rules: the first matching intent wins (more specific intents first).
_INTENT_RULES: list[tuple[Intent, re.Pattern[str]]] = [
    (Intent.COMPARISON, re.compile(r"\bcompar|\bversus\b|\bvs\.?\s|\bdifference between\b|\breconcile|\bconsistent with\b")),
    (Intent.ACTION_PLANNING, re.compile(r"\bactions?\b|\bshould\b|\bnext steps?\b|\brecommend|\bwhat to do\b|\bpriorit|\bthis week\b|\bto-?dos?\b")),
    (Intent.SUMMARIZATION, re.compile(r"\bsummar|\boverview\b|\btl;?dr\b|\bkey points\b|\bbrief me\b|\bgist\b")),
    (Intent.ISSUE_LOOKUP, re.compile(r"\bissues?\b|\bbugs?\b|\bblock(?:er|ers|ing|ed)?\b|\btickets?\b|\bdefects?\b")),
    (Intent.PEOPLE_LOOKUP, re.compile(r"\bwho\b|\bcontact\b|\bemployees?\b|\bdirectory\b|\bemail\b|\bowns?\b|\bworks? on\b")),
    (Intent.RISK_ANALYSIS, re.compile(r"\brisks?\b|\bthreats?\b|\bconcerns?\b|\bmitigat|\bjeopard")),
    (Intent.PROJECT_STATUS, re.compile(r"\bstatus\b|\bprogress\b|\bon track\b|\bhealth\b|\bhow is\b|\bupdate on\b")),
]


class IntentDecision(BaseModel):
    """Structured supervisor output (LIVE mode)."""

    intent: Intent
    project_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""


def classify_intent_rules(query: str) -> tuple[Intent, str]:
    """Deterministic keyword classifier (DEMO mode and LIVE-mode fallback)."""
    lowered = query.lower()
    for intent, pattern in _INTENT_RULES:
        match = pattern.search(lowered)
        if match:
            return intent, f"Rule match on '{match.group(0).strip()}' → {intent.value}."
    return Intent.GENERAL_QA, "No specific intent keywords; answering from documents."


class SupervisorAgent:
    """LangGraph supervisor node.

    First visit: classify intent and create a plan. Every visit: pick the next
    specialist from the plan, adapt the plan to what earlier agents found, and
    hand over to the response agent once the plan is exhausted.
    """

    def __init__(self, repo: EnterpriseDataRepository, llm: LLMProvider | None = None) -> None:
        self._repo = repo
        self._llm = llm

    def _classify(self, query: str) -> tuple[Intent, list[str], str, TokenUsage, list[str]]:
        errors: list[str] = []
        project_ids = self._repo.match_projects(query)
        known = [p["project_id"] for p in self._repo.projects]
        if self._llm is not None:
            try:
                decision, usage = self._llm.structured(
                    SUPERVISOR_SYSTEM.format(project_ids=", ".join(known)), query, IntentDecision
                )
                llm_projects = [p.upper() for p in decision.project_ids if p.upper() in known]
                return decision.intent, llm_projects or project_ids, decision.reasoning, usage, errors
            except LLMError as exc:
                logger.warning("Supervisor LLM failed, using rule-based routing: %s", exc)
                errors.append(f"supervisor: {exc} (fell back to rule-based routing)")
        intent, reasoning = classify_intent_rules(query)
        usage = TokenUsage(
            input_tokens=estimate_tokens(SUPERVISOR_SYSTEM + query), output_tokens=30, estimated=True
        )
        return intent, project_ids, reasoning, usage, errors

    def __call__(self, state: CopilotState) -> dict[str, Any]:
        update: dict[str, Any] = {}
        if "intent" not in state:
            intent, project_ids, reasoning, usage, errors = self._classify(state["user_query"])
            if not project_ids:
                release = self._repo.match_release(state["user_query"])
                if release:
                    project_ids = self._repo.projects_for_release(release)
            plan = [a.value for a in ROUTING_PLANS[intent]]
            update.update(
                intent=intent,
                intent_reasoning=reasoning,
                project_ids=project_ids,
                token_usage=usage,
                errors=errors,
            )
            detail = f"intent={intent.value}; plan={' → '.join(plan) or 'response'}"
        else:
            plan = list(state.get("plan", []))
            detail = ""
            # Adaptive routing: if retrieval found nothing, fall back to enterprise tools.
            path = state.get("execution_path", [])
            if (
                path
                and path[-1] == AgentName.RAG.value
                and not state.get("retrieved_documents")
                and AgentName.TOOLS.value not in plan
                and AgentName.TOOLS.value not in path
                and state.get("project_ids")
            ):
                plan.insert(0, AgentName.TOOLS.value)
                detail = "no documents retrieved → adding tool agent; "

        next_agent = plan.pop(0) if plan else AgentName.RESPONSE.value
        update.update(plan=plan, next_agent=next_agent, _detail=f"{detail}next={next_agent}")
        return update


def route_from_supervisor(state: CopilotState) -> str:
    """Conditional-edge function: the node the supervisor selected."""
    return state["next_agent"]
