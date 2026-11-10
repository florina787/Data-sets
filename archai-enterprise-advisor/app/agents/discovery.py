"""Discovery agent: frame the business problem before any technology choice."""

from __future__ import annotations

from app.decision_engine.scoring import regulatory_intensity
from app.models.inputs import AssessmentRequest
from app.models.outputs import DiscoveryResult


def discover(req: AssessmentRequest) -> DiscoveryResult:
    uc, org = req.use_case, req.organization
    gaps: list[str] = []
    for field, label in [
        ("description", "business problem description"),
        ("users", "users"),
        ("workflow", "current workflow"),
        ("desired_outcome", "desired outcome"),
        ("current_solution", "current solution"),
    ]:
        if not getattr(uc, field).strip():
            gaps.append(f"Missing {label}.")
    if not uc.pain_points:
        gaps.append("No pain points captured — value cannot be validated.")
    if not uc.primary_tasks:
        gaps.append("Primary task types not specified.")
    if not req.current_architecture.existing_systems:
        gaps.append("No existing systems named — authoritative systems unclear.")

    assumptions = [
        "All ratings are as provided by the requester and should be validated with stakeholders.",
        "Costs use configurable SAMPLE pricing from config/model_pricing.json.",
        "ROI benefits are estimates to be validated with measured baselines in Phase 0/1.",
    ]
    if org.regulatory_intensity is None:
        assumptions.append(f"Regulatory intensity assumed from the {org.industry.value} baseline ({regulatory_intensity(req)}/5).")
    return DiscoveryResult(
        business_problem=uc.description or uc.title,
        users=uc.users or "Not specified",
        workflow=uc.workflow or "Not specified",
        pain_points=uc.pain_points,
        desired_outcome=uc.desired_outcome or "Not specified",
        current_solution=uc.current_solution or "Not specified",
        constraints=uc.constraints,
        information_gaps=gaps,
        assumptions=assumptions,
    )
