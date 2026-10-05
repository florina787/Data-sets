"""Typed LangGraph state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class LexGuardState(TypedDict, total=False):
    request_id: str
    user: dict
    role: str
    client: dict
    matter: dict
    task: str
    intent: str
    intent_detail: dict
    destination: str
    requested_provider: str | None
    selected_finding_id: str | None
    documents: dict                 # counts + ids of documents in scope
    matter_access: dict
    ethical_wall_status: dict
    ai_policy: dict                 # MatterGuard result
    ai_suitability: dict
    risk: str
    routing_decision: dict
    plan: list[str]
    plan_index: int
    iterations: int
    retrieved_sources: list[dict]
    review: dict                    # change-of-control review summary
    analysis: dict                  # other analysis outputs
    findings: list[dict]
    citations: list[dict]
    playbook_results: list[dict]
    privilege_flags: list[dict]
    assurance_result: dict
    work_product: dict
    draft: dict
    human_review: dict
    approval_status: str
    provider: str | None
    workflow: str | None
    cost: float
    latency: float
    status: str
    answer: str
    response_extras: dict
    injection_flags: list[dict]
    audit_events: Annotated[list[str], operator.add]
    agent_trace: Annotated[list[dict], operator.add]
    graph_path: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    agents_invoked: Annotated[list[str], operator.add]
    response: dict
    _extra: Any
