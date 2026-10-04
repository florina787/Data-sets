"""Challenger / validation agent.

Deterministically challenges the recommendation with the questions an
experienced architecture review board would ask. A FAIL triggers a bounded
revision loop in the LangGraph workflow (the engine re-decides with the
offending pattern excluded).
"""

from __future__ import annotations

from app.decision_engine import weights as W
from app.decision_engine.scoring import agentic_gate, is_deterministic_workload
from app.models.enums import ArchitectureOption, ChallengeVerdict, ROIVerdict
from app.models.inputs import AssessmentRequest
from app.models.outputs import ChallengeQuestion, ChallengerResult, Decision, ROIResult, ScoreCard

A = ArchitectureOption
P, F, X = ChallengeVerdict.PASS, ChallengeVerdict.FLAG, ChallengeVerdict.FAIL
_COMPLEXITY_ORDER = [A.AGENTIC_AI, A.RAG_GENAI, A.GENERATIVE_AI, A.TRADITIONAL_ML]


def challenge(req: AssessmentRequest, decision: Decision, scores: ScoreCard, roi: ROIResult) -> ChallengerResult:
    uc = req.use_case
    patterns = set(decision.ai_patterns)
    ai = bool(patterns)
    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    qs: list[ChallengeQuestion] = []
    exclude: set[ArchitectureOption] = set()
    reasons: list[str] = []

    def q(question: str, verdict: ChallengeVerdict, finding: str) -> None:
        qs.append(ChallengeQuestion(question=question, verdict=verdict, finding=finding))

    # 1
    if not ai:
        q("Do we actually need AI?", P, "No — and no AI is recommended.")
    elif scores.ai_suitability.value >= W.AI_SUITABILITY_MIN:
        q("Do we actually need AI?", P, f"Yes — AI suitability {scores.ai_suitability.value:.0f} ≥ {W.AI_SUITABILITY_MIN:.0f}.")
    else:
        q("Do we actually need AI?", X, f"AI suitability {scores.ai_suitability.value:.0f} is below threshold.")
        exclude |= patterns
        reasons.append("AI suitability below threshold")
    # 2
    if ai and is_deterministic_workload(req):
        q("Could traditional software solve this?", X, "Yes — the workload is deterministic; AI must be removed.")
        exclude |= patterns
        reasons.append("deterministic workload")
    elif ai and uc.deterministic_requirement >= 3:
        q("Could traditional software solve this?", F, "Partially — deterministic parts must stay in existing systems (hybrid).")
    else:
        q("Could traditional software solve this?", P, "Not fully — rules cannot provide the required capability." if ai else "Yes — existing/deterministic software is recommended.")
    # 3
    if llm and scores.ml_suitability.value >= max(scores.genai_suitability.value, scores.rag_suitability.value) and uc.prediction_requirement > uc.generation_requirement:
        q("Could ML solve this without an LLM?", F, "Prediction dominates — consider classical ML before an LLM.")
    elif A.TRADITIONAL_ML in patterns and not llm:
        q("Could ML solve this without an LLM?", P, "Yes — classical ML is recommended; no LLM.")
    else:
        q("Could ML solve this without an LLM?", P, "No — the need is generative/knowledge/reasoning, not prediction." if llm else "Not applicable.")
    # 4
    if A.RAG_GENAI in patterns and uc.proprietary_knowledge_need <= 2:
        q("Do we need RAG?", X, "No proprietary-knowledge grounding need — RAG removed.")
        exclude.add(A.RAG_GENAI)
        reasons.append("RAG without grounding need")
    elif A.RAG_GENAI in patterns:
        q("Do we need RAG?", P, f"Yes — proprietary knowledge {uc.proprietary_knowledge_need}/5, citations {uc.citation_requirement}/5.")
    else:
        q("Do we need RAG?", P, "No — and RAG is not recommended (existing tooling is not a reason to add it).")
    # 5
    gate_met, _ = agentic_gate(req)
    if A.AGENTIC_AI in patterns and not gate_met:
        q("Do we actually need an agent?", X, "Agentic need gate unmet — agent removed.")
        exclude.add(A.AGENTIC_AI)
        reasons.append("agent without need")
    elif A.AGENTIC_AI in patterns:
        q("Do we actually need an agent?", P, "Yes, constrained — variable multi-step cross-system investigation.")
    else:
        q("Do we actually need an agent?", P, "No — and no agent is recommended.")
    # 6
    if A.AGENTIC_AI in patterns and uc.workflow_variability <= 2:
        q("Could a workflow engine solve this?", F, "Workflow is fairly predictable — prefer deterministic workflow edges with LLM steps only where needed.")
    elif A.AGENTIC_AI in patterns:
        q("Could a workflow engine solve this?", P, "Not fully — investigation paths vary per case; deterministic steps remain graph edges.")
    else:
        q("Could a workflow engine solve this?", P, "Where orchestration is needed, a deterministic workflow suffices.")
    # 7
    if uc.replaces_existing_component:
        q("Are we replacing a deterministic component unnecessarily?", P,
          f"Replacement of '{uc.replaces_existing_component}' was rejected; the component is kept.")
    else:
        q("Are we replacing a deterministic component unnecessarily?", P, "No — existing components are KEPT or ENHANCED.")
    # 8
    if ai and roi.verdict is ROIVerdict.NOT_JUSTIFIED:
        q("Does the ROI justify the complexity?", X, f"No — {roi.verdict.value} (net annual benefit ${roi.net_annual_benefit:,.0f}).")
        reasons.append("ROI does not justify AI")
        if roi.estimated_annual_benefit <= roi.estimated_implementation_cost / 3:
            exclude |= set(_COMPLEXITY_ORDER)  # even a zero-run-cost AI solution could not recover the implementation
        else:
            for p in _COMPLEXITY_ORDER:
                if p in patterns:
                    exclude.add(p)
                    break
    elif ai and roi.verdict is ROIVerdict.MARGINAL:
        q("Does the ROI justify the complexity?", F, f"Marginal — payback {roi.payback_months} months; pilot narrowly.")
    elif ai:
        q("Does the ROI justify the complexity?", P, f"Yes — {roi.verdict.value}; payback {roi.payback_months} months.")
    else:
        q("Does the ROI justify the complexity?", P, "No AI investment proposed.")

    requires = any(item.verdict is X for item in qs)
    return ChallengerResult(
        questions=qs,
        requires_revision=requires,
        exclude_patterns=sorted(exclude, key=lambda o: o.value),
        revision_reason="; ".join(reasons),
        final_verdict="Revision required" if requires else "Recommendation upheld",
    )
