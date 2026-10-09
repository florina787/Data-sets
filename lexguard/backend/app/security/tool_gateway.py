"""Tool allowlists and limits. Every agent tool call goes through `ToolGateway.call`.

A call is permitted only if the tool is in (a) the agent's static allowlist AND (b) the request's
MatterGuard allowed_tools, and the request has not exhausted its tool-call budget.
"""

from __future__ import annotations

from typing import Any, Callable

AGENT_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "supervisor": set(),
    "matter_intake": set(),
    "ai_policy": set(),
    "ai_routing": set(),
    "legal_knowledge": {"knowledge_search"},
    "document_analysis": {"matter_document_search", "clause_extraction", "summarize", "obligation_extract",
                          "timeline_extract", "entity_extract", "document_compare", "external_provider_call",
                          "traditional_search"},
    "legal_research": {"knowledge_search", "matter_document_search", "external_provider_call"},
    "playbook": {"playbook_compare", "knowledge_search"},
    "citation_verification": {"citation_verify"},
    "workproduct_assurance": {"citation_verify"},
    "privilege": {"privilege_scan"},
    "drafting": {"draft_generate", "knowledge_search", "citation_verify", "playbook_compare"},
    "value_analysis": {"value_calc"},
    "change_impact": set(),
    "evaluation": set(),
    "policy_explainer": {"knowledge_search"},
    "traditional_search": {"traditional_search"},
}


class ToolNotPermitted(PermissionError):
    pass


class ToolBudgetExceeded(RuntimeError):
    pass


class ToolGateway:
    def __init__(self, allowed_tools: list[str], max_calls: int, audit_fn: Callable[[str, dict, str], Any]):
        self.allowed_tools = set(allowed_tools)
        self.max_calls = max_calls
        self.audit = audit_fn
        self.calls: list[dict] = []

    def call(self, agent: str, tool: str, fn: Callable, *args, **kwargs):
        if tool not in AGENT_TOOL_ALLOWLIST.get(agent, set()):
            self.audit("TOOL_DENIED", {"agent": agent, "tool": tool, "reason": "not in agent allowlist"}, "WARNING")
            raise ToolNotPermitted(f"Agent '{agent}' is not allowed to use tool '{tool}'.")
        if tool not in self.allowed_tools:
            self.audit("TOOL_DENIED", {"agent": agent, "tool": tool, "reason": "blocked by MatterGuard"}, "WARNING")
            raise ToolNotPermitted(f"Tool '{tool}' is blocked by MatterGuard for this request.")
        if len(self.calls) >= self.max_calls:
            self.audit("TOOL_BUDGET_EXCEEDED", {"agent": agent, "tool": tool}, "WARNING")
            raise ToolBudgetExceeded("Tool-call budget exhausted for this request.")
        self.calls.append({"agent": agent, "tool": tool})
        return fn(*args, **kwargs)
