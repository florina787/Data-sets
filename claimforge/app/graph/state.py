"""Typed LangGraph state for the ClaimForge closed-loop workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ClaimForgeState(TypedDict, total=False):
    # request / control
    request_id: str
    request_text: str
    persona: str
    workflow: str
    clarifications: dict[str, str]
    approval: dict | None
    stop_after: str | None
    inject_defect: bool
    n_claims: int
    seed: int
    max_agent_iterations: int | None
    status: str
    halted_reason: str | None
    step_count: int
    agent_calls: dict[str, int]
    request_screen: dict
    supervisor: dict
    # SDLC artifacts
    requirement: Any
    requirement_narrative: dict
    policy: dict
    ambiguity: dict
    impact: dict
    architecture: dict
    development_plan: dict
    tests: dict
    simulation: Any
    security: dict
    governance: dict
    release_risk: Any
    release_assessment: dict
    release: dict
    # ClaimIQ artifacts
    production: dict
    anomaly: dict
    root_cause: Any
    root_cause_narrative: dict
    root_cause_stop_reason: str | None
    release_correlation: dict
    remediation: Any
    regression: dict
    defect: Any
    feedback: dict
    # heavy, non-serialised objects (DataFrames / production context)
    artifacts: dict
    # append-only
    trace: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]


TERMINAL_STATUSES = {"HALTED", "FAILED"}
