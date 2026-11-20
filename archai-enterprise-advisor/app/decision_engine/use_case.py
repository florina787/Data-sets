"""Use-case assessment: characterize the workload before choosing technology."""

from __future__ import annotations

from app.decision_engine.scoring import agentic_gate, is_deterministic_workload
from app.models.enums import DETERMINISTIC_ONLY_ACTIONS, HIGH_RISK_WRITE_ACTIONS
from app.models.inputs import AssessmentRequest
from app.models.outputs import Finding, UseCaseAssessment


def assess_use_case(req: AssessmentRequest) -> UseCaseAssessment:
    uc = req.use_case
    deterministic = is_deterministic_workload(req)
    gate_met, signals = agentic_gate(req)
    forbidden = sorted(set(uc.action_types) & DETERMINISTIC_ONLY_ACTIONS, key=lambda a: a.value)
    high_risk = sorted(set(uc.action_types) & HIGH_RISK_WRITE_ACTIONS, key=lambda a: a.value)

    dims = {
        "prediction": uc.prediction_requirement,
        "generation": uc.generation_requirement,
        "proprietary knowledge": uc.proprietary_knowledge_need,
        "multi-step reasoning": uc.multi_step_reasoning,
        "deterministic rules": uc.deterministic_requirement,
    }
    dominant = max(dims, key=lambda k: dims[k])
    if deterministic:
        character = "Deterministic, rules-governed workload"
    elif gate_met and uc.workflow_variability >= 3:
        character = "Variable, multi-step, cross-system workflow"
    else:
        character = f"Workload dominated by {dominant} (rated {dims[dominant]}/5)"

    findings: list[Finding] = []
    if deterministic:
        findings.append(
            Finding(
                area="Determinism",
                observation=f"Deterministic requirement rated {uc.deterministic_requirement}/5 with low AI signals.",
                implication="Explicit rules are cheaper, faster, auditable and exactly reproducible.",
            )
        )
    if forbidden:
        findings.append(
            Finding(
                area="Deterministic-only actions",
                observation="Workload touches " + ", ".join(a.value for a in forbidden) + ".",
                implication="These actions stay with existing deterministic systems; AI never decides or executes them.",
            )
        )
    if high_risk:
        findings.append(
            Finding(
                area="High-risk writes",
                observation="Workload performs " + ", ".join(a.value for a in high_risk) + ".",
                implication="Any AI involvement requires a human approval gate.",
            )
        )
    if uc.hallucination_tolerance <= 1:
        findings.append(
            Finding(
                area="Hallucination tolerance",
                observation=f"Tolerance rated {uc.hallucination_tolerance}/5.",
                implication="Generated output must be grounded, cited and human-reviewed.",
            )
        )
    if uc.replaces_existing_component:
        findings.append(
            Finding(
                area="Replacement request",
                observation=f"Request proposes replacing '{uc.replaces_existing_component}'.",
                implication="Replacing a working deterministic component requires strong justification.",
            )
        )
    met = [k for k, v in signals.items() if v >= 3]
    findings.append(
        Finding(
            area="Agentic need gate",
            observation=f"{len(met)} of {len(signals)} agentic dimensions rated ≥3 ({', '.join(met) or 'none'}).",
            implication="Gate met — agents may be considered." if gate_met else "Gate not met — agents are not needed.",
        )
    )
    return UseCaseAssessment(
        workload_character=character,
        is_deterministic_workload=deterministic,
        deterministic_only_actions=forbidden,
        high_risk_write_actions=high_risk,
        agentic_need_signals=signals,
        agentic_need_gate_met=gate_met,
        replacement_request=uc.replaces_existing_component,
        findings=findings,
    )
