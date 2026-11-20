"""Phased migration roadmap. Never jumps to unrestricted autonomy."""

from __future__ import annotations

from app.models.enums import ArchitectureOption, AutonomyLevel
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, Roadmap, RoadmapPhase, ROIResult

A = ArchitectureOption


def build_roadmap(req: AssessmentRequest, decision: Decision, roi: ROIResult) -> Roadmap:
    level = decision.autonomy_level
    ai = decision.ai_recommended
    agent = A.AGENTIC_AI in decision.ai_patterns
    phases: list[RoadmapPhase] = []

    phases.append(RoadmapPhase(
        phase=0, name="Validate business case", objective="Confirm the problem, baseline and value before building anything.",
        activities=[
            "Measure current baseline (effort, error rate, cycle time, cost)",
            "Confirm data owners, access rights and classification",
            "Agree acceptance criteria (see Evaluation) and kill criteria",
        ] + ([] if ai else ["Address the pain point with deterministic improvements (rule tooling, workflow, search)"]),
        exit_criteria=["Signed-off baseline and KPIs", "Risk/compliance pre-assessment complete"],
        autonomy_ceiling=AutonomyLevel.NO_AI,
    ))
    if not ai:
        for n, name in [(1, "POC"), (2, "Controlled pilot"), (3, "Human-in-the-loop production"), (4, "Limited automation"), (5, "Scale")]:
            phases.append(RoadmapPhase(
                phase=n, name=name, objective="Not applicable", activities=[], exit_criteria=[],
                autonomy_ceiling=AutonomyLevel.NO_AI, included=False,
                note="Not planned — no AI component is recommended. Re-assess if requirements change.",
            ))
        return Roadmap(summary="No AI roadmap: keep/extend the existing deterministic solution. Re-assess on the conditions listed in the ADR.", phases=phases)

    phases.append(RoadmapPhase(
        phase=1, name="POC", objective="Prove technical feasibility on representative, non-production data.",
        activities=[
            "Build thin slice on the existing platform (no changes to systems of record)",
            "Assemble evaluation set with domain experts",
            "Run offline evaluation against acceptance criteria",
        ] + (["Read-only tools only; write tools disabled"] if agent else []),
        exit_criteria=["Offline metrics meet POC thresholds", "Security review of data flows"],
        autonomy_ceiling=min(level, AutonomyLevel.READ_ONLY),
    ))
    phases.append(RoadmapPhase(
        phase=2, name="Controlled pilot", objective="Small user group; every output reviewed.",
        activities=["Pilot with 5–20 trained users", "Capture feedback and override reasons", "Monitor cost, latency, guardrail events"],
        exit_criteria=["Acceptance criteria met on live traffic", "No critical security findings", "Positive user value signal"],
        autonomy_ceiling=min(level, AutonomyLevel.SUGGEST),
    ))
    phases.append(RoadmapPhase(
        phase=3, name="Human-in-the-loop production",
        objective="Production rollout with human review/approval at every material step.",
        activities=["Gradual rollout behind feature flag", "Approval workflow with segregation of duties" if decision.requires_human_approval else "Sampled human review", "Graceful degradation tested (AI off → process continues)"],
        exit_criteria=["KPIs vs baseline confirmed", "Override and error rates stable", "Model risk / governance sign-off"],
        autonomy_ceiling=min(level, AutonomyLevel.APPROVAL_REQUIRED),
    ))
    if level >= AutonomyLevel.LIMITED_AUTONOMY:
        phases.append(RoadmapPhase(
            phase=4, name="Limited automation", objective="Automate only low-risk, reversible actions within strict policy.",
            activities=["Enable allow-listed low-risk actions", "Keep approval for high-risk actions", "Continuous evaluation and audit"],
            exit_criteria=["Zero unauthorized actions", "Automation accuracy ≥ agreed threshold"],
            autonomy_ceiling=AutonomyLevel.LIMITED_AUTONOMY,
        ))
    else:
        phases.append(RoadmapPhase(
            phase=4, name="Limited automation", objective="Automate only read-only / low-risk steps.",
            activities=["Automate evidence gathering and drafting only", "Every write/action remains human-approved"],
            exit_criteria=["Sustained KPI improvement"], autonomy_ceiling=level,
            note=f"Autonomy ceiling remains {decision.autonomy_label}; no autonomous execution of material actions.",
        ))
    phases.append(RoadmapPhase(
        phase=5, name="Scale only if KPIs justify it", objective="Expand users/use cases only when measured value is proven.",
        activities=["Re-run ROI with measured data", "Extend to adjacent workflows", "Optimize cost (routing, caching, self-hosting)"],
        exit_criteria=["Measured ROI meets business case", "Governance re-approval"],
        autonomy_ceiling=level,
        note="Scaling is conditional; stop or roll back if KPIs regress." + (" Business case is marginal — scale cautiously." if roi.verdict.name == "MARGINAL" else ""),
    ))
    return Roadmap(summary=f"Phased adoption of {decision.architecture_label}; autonomy never exceeds {decision.autonomy_label}.", phases=phases)
