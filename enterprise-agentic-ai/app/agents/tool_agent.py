"""Tool agent: decides which enterprise tools to call and executes them."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from app.agents.prompts import TOOL_PLANNER_SYSTEM
from app.graph.state import CopilotState
from app.llm.provider import LLMError, LLMProvider
from app.models.domain import Intent, TokenUsage
from app.tools.enterprise_tools import ToolRegistry
from app.tools.repository import EnterpriseDataRepository

logger = logging.getLogger(__name__)

_MAX_CALLS = 6


class PlannedToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolPlan(BaseModel):
    """Structured tool-selection output (LIVE mode)."""

    calls: list[PlannedToolCall] = Field(default_factory=list)


class ToolAgent:
    """Selects tool calls (Claude in LIVE mode, deterministic rules in DEMO mode) and runs them."""

    def __init__(self, registry: ToolRegistry, repo: EnterpriseDataRepository, llm: LLMProvider | None = None) -> None:
        self._registry = registry
        self._repo = repo
        self._llm = llm

    # --- project resolution ----------------------------------------------
    def _resolve_projects(self, state: CopilotState) -> list[str]:
        if state.get("project_ids"):
            return list(state["project_ids"])
        # Infer the project from the retrieved evidence (most frequently mentioned).
        counts: Counter[str] = Counter()
        for chunk in state.get("retrieved_documents", []):
            for pid in self._repo.match_projects(chunk.text):
                counts[pid] += 1
        return [counts.most_common(1)[0][0]] if counts else []

    # --- planning ----------------------------------------------------------
    def plan_rules(self, query: str, intent: Intent, project_ids: list[str]) -> list[PlannedToolCall]:
        """Deterministic tool plan per intent."""
        release = self._repo.match_release(query)
        blocking = bool(re.search(r"\bblock", query.lower()))
        calls: list[PlannedToolCall] = []

        if intent is Intent.PEOPLE_LOOKUP:
            return [PlannedToolCall(tool_name="search_employee_directory", arguments={"query": query})]
        if intent is Intent.ISSUE_LOOKUP:
            targets = project_ids or [None]
            return [
                PlannedToolCall(
                    tool_name="get_open_issues",
                    arguments={"project_id": pid, "blocking_only": blocking, "release": release},
                )
                for pid in targets
            ]
        if not project_ids:
            return [PlannedToolCall(tool_name="list_projects")]

        for pid in project_ids:
            calls.append(PlannedToolCall(tool_name="get_project_status", arguments={"project_id": pid}))
            if intent in (Intent.PROJECT_STATUS, Intent.ACTION_PLANNING):
                calls.append(
                    PlannedToolCall(tool_name="get_open_issues", arguments={"project_id": pid, "blocking_only": True})
                )
            if intent in (Intent.COMPARISON, Intent.ACTION_PLANNING, Intent.RISK_ANALYSIS):
                calls.append(PlannedToolCall(tool_name="get_delivery_metrics", arguments={"project_id": pid}))
        return calls[:_MAX_CALLS]

    def _plan_llm(self, query: str, intent: Intent, project_ids: list[str]) -> tuple[list[PlannedToolCall], TokenUsage]:
        assert self._llm is not None
        system = TOOL_PLANNER_SYSTEM.format(
            tools=json.dumps(self._registry.describe(), indent=1),
            project_ids=", ".join(p["project_id"] for p in self._repo.projects),
        )
        prompt = f"Request: {query}\nIntent: {intent.value}\nProjects in scope: {project_ids or 'not specified'}"
        plan, usage = self._llm.structured(system, prompt, ToolPlan)
        valid = [c for c in plan.calls if c.tool_name in self._registry.names]
        if not valid:
            raise LLMError("Tool planner returned no valid tool calls")
        return valid[:_MAX_CALLS], usage

    def __call__(self, state: CopilotState) -> dict[str, Any]:
        query = state["user_query"]
        intent = state.get("intent", Intent.GENERAL_QA)
        project_ids = self._resolve_projects(state)
        usage = TokenUsage()
        errors: list[str] = []
        calls: list[PlannedToolCall] | None = None

        if self._llm is not None:
            try:
                calls, usage = self._plan_llm(query, intent, project_ids)
            except LLMError as exc:
                logger.warning("Tool planner LLM failed, using rule-based plan: %s", exc)
                errors.append(f"tool_agent: {exc} (fell back to rule-based tool plan)")
        if calls is None:
            calls = self.plan_rules(query, intent, project_ids)

        results = [self._registry.execute(c.tool_name, c.arguments) for c in calls]
        errors += [f"tool {r.tool_name}: {r.error}" for r in results if not r.success]
        names = ", ".join(r.tool_name for r in results)
        return {
            "tool_results": results,
            "project_ids": project_ids,
            "token_usage": usage,
            "errors": errors,
            "_detail": f"called {len(results)} tools: {names}",
        }
