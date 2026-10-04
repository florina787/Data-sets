"""AI evaluation framework: measurable acceptance criteria per architecture.

Targets are *recommended starting thresholds* to be calibrated against the
organization's measured baseline in Phase 0/1 — not claims about any system.
"""

from __future__ import annotations

from app.models.enums import ArchitectureOption, Industry
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, EvaluationMetric, EvaluationPlan

A = ArchitectureOption
DISCLAIMER = "Recommended starting thresholds; calibrate against your measured baseline before go/no-go decisions."


def build_evaluation_plan(req: AssessmentRequest, decision: Decision) -> EvaluationPlan:
    patterns = set(decision.ai_patterns)
    strict = req.organization.industry in {Industry.LEGAL, Industry.BANKING} or req.use_case.hallucination_tolerance <= 1
    m: list[EvaluationMetric] = []

    def add(name: str, target: str, why: str) -> None:
        m.append(EvaluationMetric(name=name, target=target, why=why))

    if not patterns:
        add("Rule test coverage", "100% of rules covered by golden test cases", "Deterministic correctness is provable.")
        add("Decision latency (p99)", "Within existing SLA", "No regression from status quo.")
        add("Availability", "Existing SLA (unchanged)", "No new dependencies introduced.")
        add("Rule change lead time", "Measured and reduced via rule tooling", "Addresses the original pain point without AI.")
        return EvaluationPlan(architecture=decision.architecture_label, metrics=m, disclaimer=DISCLAIMER)

    if A.TRADITIONAL_ML in patterns:
        add("Predictive accuracy vs baseline", "Beats current method (e.g. MAPE/AUC) by an agreed margin", "Justifies the model over the status quo.")
        add("Calibration & drift", "Drift alerts within agreed tolerance", "Prevents silent degradation.")
        add("Human override rate", "Tracked; < 20% after pilot", "Signals trust and fit.")
    if A.RAG_GENAI in patterns or A.AGENTIC_AI in patterns:
        add("Retrieval precision@k", "≥ 0.80", "Relevant context reduces hallucination and cost.")
        add("Retrieval recall@k", "≥ 0.85" if strict else "≥ 0.75", "Missing evidence produces wrong or incomplete answers.")
        add("Groundedness (claims supported by sources)", "≥ 0.95" if strict else "≥ 0.90", "Answers must be supported by retrieved evidence.")
    if patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI}:
        add("Answer correctness (expert-graded set)", "≥ 0.90" if strict else "≥ 0.85", "Measured on a curated evaluation set.")
        add("Hallucination rate", "≤ 1% with 100% human review" if strict else "≤ 3%", "Fabrication risk is the main GenAI failure mode.")
        add("Cost per request", "Within budget from the cost engine (alert at +20%)", "Prevents cost overrun at scale.")
        add("Latency (p95)", "≤ 3s interactive" if req.use_case.latency_sensitivity >= 4 else "≤ 8s", "User adoption depends on responsiveness.")
    if decision.citations_mandatory:
        add("Citation accuracy", "100% of citations resolve to the cited passage", "Mandatory for legal/regulated use.")
    if A.AGENTIC_AI in patterns:
        add("Tool-call success rate", "≥ 95%", "Failed/hallucinated calls waste budget and erode trust.")
        add("Task completion rate", "≥ 80% investigations with useful hypothesis", "Core value of the agent.")
        add("Guardrail breaches", "0 unauthorized tool executions; 100% writes approved", "Excessive agency must be impossible.")
        add("Iteration/token budget breaches", "< 2% of runs", "Detects loops and runaway cost.")
    if A.TRADITIONAL_ML not in patterns:
        add("Human override rate", "Tracked per release", "Measures real-world trust and quality.")
    add("Error rate", "< 1% of requests", "Operational health.")
    add("Availability", "≥ 99.5% for AI assistance (core process unaffected)", "AI degrades gracefully.")
    return EvaluationPlan(architecture=decision.architecture_label, metrics=m, disclaimer=DISCLAIMER)
