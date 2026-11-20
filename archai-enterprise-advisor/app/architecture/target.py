"""Target architecture assembly."""

from __future__ import annotations

from app.architecture.diagrams import current_state_mermaid, target_state_mermaid
from app.models.enums import MatrixDecision
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, MatrixRow, TargetArchitecture


def build_target_architecture(req: AssessmentRequest, decision: Decision, matrix: list[MatrixRow]) -> TargetArchitecture:
    added = [r.component for r in matrix if r.decision is MatrixDecision.ADD]
    principles = [
        "AI fits around the existing enterprise architecture; nothing working is replaced without strong justification.",
        "Existing deterministic systems remain authoritative for transactions and records.",
        "AI integrates through existing APIs and the API gateway — never directly into databases of record.",
        "AI failure degrades gracefully; the existing business process keeps running.",
    ]
    if decision.ai_recommended:
        summary = (
            f"{decision.architecture_label}. Adds: {', '.join(added) or 'no new components'}. "
            f"Autonomy: {decision.autonomy_label}."
        )
    else:
        summary = f"{decision.architecture_label}. No AI components are added; the current architecture is retained."
    return TargetArchitecture(
        summary=summary,
        current_state_mermaid=current_state_mermaid(req),
        target_state_mermaid=target_state_mermaid(req, decision),
        added_components=added,
        principles=principles,
    )
