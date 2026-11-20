"""Human-in-the-loop autonomy policy.

Autonomy starts from what the architecture could technically do and is then
*capped* by risk. Caps only ever lower the level, so regulated or high-risk
workloads default conservatively.
"""

from __future__ import annotations

from app.decision_engine.scoring import regulatory_intensity
from app.models.enums import (
    AUTONOMY_LABELS,
    DETERMINISTIC_ONLY_ACTIONS,
    GENAI_TASKS,
    HIGH_RISK_WRITE_ACTIONS,
    LOW_RISK_WRITE_ACTIONS,
    REGULATED_INDUSTRIES,
    ActionType,
    ArchitectureOption,
    AutonomyLevel,
    Industry,
)
from app.models.inputs import AssessmentRequest
from app.models.outputs import ActionPolicy, ScoreCard

_BASE_LEVEL = {
    ArchitectureOption.KEEP_EXISTING: AutonomyLevel.NO_AI,
    ArchitectureOption.TRADITIONAL_SOFTWARE: AutonomyLevel.NO_AI,
    ArchitectureOption.TRADITIONAL_ML: AutonomyLevel.SUGGEST,
    ArchitectureOption.GENERATIVE_AI: AutonomyLevel.READ_ONLY,
    ArchitectureOption.RAG_GENAI: AutonomyLevel.READ_ONLY,
    ArchitectureOption.AGENTIC_AI: AutonomyLevel.LIMITED_AUTONOMY,
}


def human_review_mandatory(req: AssessmentRequest, ai_patterns: list[ArchitectureOption]) -> tuple[bool, str]:
    """Is review of *every* AI output mandatory?"""
    if not ai_patterns:
        return False, "No AI output to review."
    uc = req.use_case
    generative = bool(set(ai_patterns) & {ArchitectureOption.GENERATIVE_AI, ArchitectureOption.RAG_GENAI, ArchitectureOption.AGENTIC_AI})
    if req.organization.industry == Industry.LEGAL and generative:
        return True, "Legal work product: a qualified lawyer must review every AI-generated output."
    if generative and uc.hallucination_tolerance <= 1 and (uc.generation_requirement >= 2 or set(uc.primary_tasks) & GENAI_TASKS):
        return True, "Near-zero hallucination tolerance for generated content requires human review of all output."
    if req.data_profile.privileged and generative:
        return True, "Privileged material: outputs must be reviewed before use."
    return False, "Sampled review is sufficient given tolerance and risk."


def determine_autonomy(
    req: AssessmentRequest,
    primary: ArchitectureOption,
    ai_patterns: list[ArchitectureOption],
    scores: ScoreCard,
) -> tuple[AutonomyLevel, list[str], bool]:
    """Return (autonomy level, rationale, human_review_mandatory)."""
    if not ai_patterns:
        return AutonomyLevel.NO_AI, ["No AI component is recommended — Level 0."], False

    uc, org = req.use_case, req.organization
    actions = set(uc.action_types)
    level = max(_BASE_LEVEL[p] for p in ai_patterns)
    rationale = [f"Base level for {', '.join(p.value for p in ai_patterns)}: {AUTONOMY_LABELS[level]}."]

    if level == AutonomyLevel.READ_ONLY and actions - {ActionType.READ_ONLY}:
        level = AutonomyLevel.SUGGEST
        rationale.append("Workload produces drafts/actions, so AI moves from read-only to suggest.")

    def cap(limit: AutonomyLevel, reason: str) -> None:
        nonlocal level
        if level > limit:
            level = limit
            rationale.append(f"Capped to {AUTONOMY_LABELS[limit]}: {reason}")

    review, review_reason = human_review_mandatory(req, ai_patterns)
    if review:
        if ArchitectureOption.AGENTIC_AI in ai_patterns:
            # The agent's findings are evidence for a human; every action passes an approval gate.
            cap(AutonomyLevel.APPROVAL_REQUIRED, review_reason + " Agent output is reviewed at the approval gate.")
        else:
            cap(AutonomyLevel.SUGGEST, review_reason)
    if actions & HIGH_RISK_WRITE_ACTIONS:
        cap(
            AutonomyLevel.APPROVAL_REQUIRED,
            "high-risk write actions (" + ", ".join(sorted(a.value for a in actions & HIGH_RISK_WRITE_ACTIONS)) + ") require human approval.",
        )
    if org.industry in REGULATED_INDUSTRIES:
        cap(AutonomyLevel.APPROVAL_REQUIRED, f"regulated industry ({org.industry.value}) defaults to human approval.")
    if regulatory_intensity(req) >= 4:
        cap(AutonomyLevel.APPROVAL_REQUIRED, "high regulatory intensity.")
    if scores.security_risk.value >= 60:
        cap(AutonomyLevel.APPROVAL_REQUIRED, f"security risk {scores.security_risk.value:.0f} ≥ 60.")
    if uc.human_oversight_available <= 1 and level >= AutonomyLevel.APPROVAL_REQUIRED:
        rationale.append("WARNING: limited human oversight capacity — staff the approval step before go-live.")

    fully_autonomous_ok = (
        org.industry in {Industry.RETAIL, Industry.GENERAL_ENTERPRISE}
        and scores.overall_risk.value < 30
        and actions <= ({ActionType.READ_ONLY} | LOW_RISK_WRITE_ACTIONS)
        and uc.hallucination_tolerance >= 3
    )
    if not fully_autonomous_ok:
        cap(AutonomyLevel.LIMITED_AUTONOMY, "Level 5 requires low-risk, bounded, non-regulated workloads.")
    return level, rationale, review


def action_policies(req: AssessmentRequest, level: AutonomyLevel, ai_present: bool) -> list[ActionPolicy]:
    """Per-action execution policy: who executes, and the maximum AI autonomy."""
    policies: list[ActionPolicy] = []
    for action in req.use_case.action_types:
        if action in DETERMINISTIC_ONLY_ACTIONS:
            policies.append(
                ActionPolicy(
                    action=action,
                    max_ai_autonomy=AutonomyLevel.READ_ONLY if ai_present else AutonomyLevel.NO_AI,
                    executor="Existing deterministic system (authoritative)",
                    reason="Deterministic, auditable, regulated action — AI may only read/explain, never decide or execute.",
                )
            )
        elif action in HIGH_RISK_WRITE_ACTIONS:
            policies.append(
                ActionPolicy(
                    action=action,
                    max_ai_autonomy=min(level, AutonomyLevel.APPROVAL_REQUIRED),
                    executor="AI prepares; named human approves; existing system executes",
                    reason="Material business impact — human approval gate with audit trail.",
                )
            )
        elif action in LOW_RISK_WRITE_ACTIONS:
            policies.append(
                ActionPolicy(
                    action=action,
                    max_ai_autonomy=min(level, AutonomyLevel.LIMITED_AUTONOMY),
                    executor="AI within policy (allow-listed tool, schema-validated)",
                    reason="Low-impact, reversible write.",
                )
            )
        else:
            policies.append(
                ActionPolicy(
                    action=action,
                    max_ai_autonomy=min(level, AutonomyLevel.READ_ONLY) if ai_present else AutonomyLevel.NO_AI,
                    executor="AI (read-only, permission-aware)" if ai_present else "Existing system",
                    reason="Read access only, scoped to the requesting user's entitlements.",
                )
            )
    return policies
