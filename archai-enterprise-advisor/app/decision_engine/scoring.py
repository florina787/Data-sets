"""Deterministic scoring.

All scores are 0–100 and computed from explicit weights in
:mod:`app.decision_engine.weights`. Each score carries its factor breakdown and
any gate/penalty adjustments, so every number is explainable.
"""

from __future__ import annotations

from app.data_readiness.assessment import data_readiness_score
from app.decision_engine import weights as W
from app.infrastructure.assessment import infrastructure_score
from app.models.enums import (
    DETERMINISTIC_ONLY_ACTIONS,
    DETERMINISTIC_TASKS,
    GENAI_TASKS,
    HIGH_RISK_WRITE_ACTIONS,
    ML_TASKS,
    DataStore,
    IdentitySecurity,
    Integration,
    TaskType,
)
from app.models.inputs import AssessmentRequest
from app.models.outputs import ROIResult, Score, ScoreCard, ScoreFactor


def _u(rating: int) -> float:
    """Normalize a 0–5 rating to 0..1."""
    return rating / 5


def _weighted(key: str, label: str, raws: dict[str, float], weights: dict[str, float]) -> Score:
    factors = [
        ScoreFactor(name=name, raw=round(raws[name], 3), weight=w, contribution=round(raws[name] * w, 2))
        for name, w in weights.items()
    ]
    value = round(min(max(sum(f.contribution for f in factors), 0.0), 100.0), 1)
    return Score(key=key, label=label, value=value, factors=factors)


def _cap(score: Score, cap: float, reason: str) -> None:
    if score.value > cap:
        score.adjustments.append(f"Capped at {cap:.0f}: {reason}")
        score.value = cap


def regulatory_intensity(req: AssessmentRequest) -> int:
    org = req.organization
    if org.regulatory_intensity is not None:
        return org.regulatory_intensity
    return W.INDUSTRY_DEFAULT_REGULATORY_INTENSITY[org.industry]


def agentic_gate(req: AssessmentRequest) -> tuple[bool, dict[str, int]]:
    """Return (gate met, signal ratings). Agents need several *simultaneous* needs."""
    uc = req.use_case
    signals = {dim: getattr(uc, dim) for dim in W.AGENTIC_GATE_DIMENSIONS}
    met = sum(1 for v in signals.values() if v >= W.AGENTIC_GATE_MIN_RATING)
    return met >= W.AGENTIC_GATE_MIN_DIMENSIONS, signals


def is_deterministic_workload(req: AssessmentRequest) -> bool:
    """A workload governed by explicit rules where AI adds little incremental value."""
    uc = req.use_case
    rules_dominant = uc.deterministic_requirement >= W.DETERMINISTIC_WORKLOAD_MIN_RATING
    little_ai_signal = (
        uc.prediction_requirement <= 2
        and uc.generation_requirement <= 2
        and uc.proprietary_knowledge_need <= 2
        and uc.workflow_variability <= 1
    )
    tasks = set(uc.primary_tasks)
    deterministic_tasks_only = bool(tasks) and tasks <= DETERMINISTIC_TASKS
    return rules_dominant and (little_ai_signal or deterministic_tasks_only)


# ------------------------------------------------------------------ suitability
def ml_score(req: AssessmentRequest) -> Score:
    uc, dp = req.use_case, req.data_profile
    raws = {
        "prediction_requirement": _u(uc.prediction_requirement),
        "structured_data_share": dp.structured_share_pct / 100,
        "data_quality": _u(dp.quality),
        "ml_task_match": 1.0 if set(uc.primary_tasks) & ML_TASKS else 0.0,
    }
    s = _weighted("ml_suitability", "ML Suitability", raws, W.ML_WEIGHTS)
    if uc.prediction_requirement <= 1:
        _cap(s, W.GATE_CAP_ML, "no meaningful prediction/classification/forecasting requirement")
    return s


def genai_score(req: AssessmentRequest) -> Score:
    uc, dp = req.use_case, req.data_profile
    tasks = set(uc.primary_tasks)
    raws = {
        "generation_requirement": _u(uc.generation_requirement),
        "unstructured_data_share": 1 - dp.structured_share_pct / 100,
        "genai_task_match": 1.0 if tasks & (GENAI_TASKS | {TaskType.KNOWLEDGE_SEARCH}) else 0.0,
        "hallucination_tolerance": _u(uc.hallucination_tolerance),
        "non_deterministic_fit": 1 - _u(uc.deterministic_requirement),
    }
    s = _weighted("genai_suitability", "GenAI Suitability", raws, W.GENAI_WEIGHTS)
    if uc.generation_requirement <= 1:
        _cap(s, W.GATE_CAP_GENAI, "no summarization/extraction/generation/conversation requirement")
    return s


def rag_score(req: AssessmentRequest) -> Score:
    uc, dp = req.use_case, req.data_profile
    raws = {
        "proprietary_knowledge_need": _u(uc.proprietary_knowledge_need),
        "citation_requirement": _u(uc.citation_requirement),
        "knowledge_change_frequency": _u(uc.knowledge_change_frequency),
        "unstructured_data_share": 1 - dp.structured_share_pct / 100,
        "knowledge_fragmentation": _u(dp.knowledge_fragmentation),
        "document_quality": _u(dp.document_quality),
    }
    s = _weighted("rag_suitability", "RAG Suitability", raws, W.RAG_WEIGHTS)
    if DataStore.VECTOR_DATABASE in req.current_architecture.data_stores:
        s.adjustments.append("Existing vector database contributes 0 points: tooling presence does not justify RAG.")
    if uc.proprietary_knowledge_need <= 1 and uc.citation_requirement <= 1:
        _cap(s, W.GATE_CAP_RAG, "no proprietary-knowledge grounding or citation requirement")
    return s


def agentic_score(req: AssessmentRequest, infra_value: float) -> Score:
    uc = req.use_case
    raws = {name: _u(getattr(uc, name)) for name in W.AGENTIC_NEED_WEIGHTS}
    s = _weighted("agentic_readiness", "Agentic AI Readiness", raws, W.AGENTIC_NEED_WEIGHTS)
    multiplier = 0.75 + 0.25 * infra_value / 100
    s.value = round(s.value * multiplier, 1)
    s.adjustments.append(f"Platform readiness multiplier ×{multiplier:.2f} (infrastructure {infra_value:.0f}/100).")
    if uc.deterministic_requirement >= W.DETERMINISTIC_WORKLOAD_MIN_RATING:
        s.value = round(s.value * 0.4, 1)
        s.adjustments.append("×0.40: workload is governed by deterministic rules.")
    gate_met, signals = agentic_gate(req)
    if not gate_met:
        _cap(
            s,
            W.GATE_CAP_AGENTIC_NEED,
            f"agentic need gate unmet — fewer than {W.AGENTIC_GATE_MIN_DIMENSIONS} of "
            f"{list(signals)} rated ≥{W.AGENTIC_GATE_MIN_RATING}",
        )
    forbidden = set(uc.action_types) & DETERMINISTIC_ONLY_ACTIONS
    if forbidden:
        _cap(
            s,
            W.GATE_CAP_AGENTIC_FORBIDDEN,
            "workload includes deterministic-only actions (" + ", ".join(sorted(a.value for a in forbidden)) + ")",
        )
    return s


def ai_suitability_score(req: AssessmentRequest) -> Score:
    """Does AI add meaningful value at all, versus deterministic software?"""
    uc, dp = req.use_case, req.data_profile
    signals = {
        "prediction_signal": _u(uc.prediction_requirement),
        "generation_signal": _u(uc.generation_requirement),
        "knowledge_signal": 0.85 * max(_u(uc.proprietary_knowledge_need), _u(dp.knowledge_fragmentation) * 0.8),
        "reasoning_signal": (
            _u(uc.multi_step_reasoning) + _u(uc.workflow_variability) + _u(uc.cross_system_interaction)
        )
        / 3,
    }
    ranked = sorted(signals.items(), key=lambda kv: kv[1], reverse=True)
    weight_for = {ranked[0][0]: 65.0, ranked[1][0]: 35.0}
    factors = [
        ScoreFactor(name=n, raw=round(v, 3), weight=weight_for.get(n, 0.0), contribution=round(v * weight_for.get(n, 0.0), 2))
        for n, v in signals.items()
    ]
    base = sum(f.contribution for f in factors)
    multiplier = 1 - 0.45 * _u(uc.deterministic_requirement)
    s = Score(
        key="ai_suitability",
        label="AI Suitability",
        value=round(min(base * multiplier, 100.0), 1),
        factors=factors,
        adjustments=[
            "Strongest AI signal weighted 65, second strongest 35.",
            f"Deterministic-requirement multiplier ×{multiplier:.2f}.",
        ],
    )
    if is_deterministic_workload(req):
        _cap(s, 20.0, "deterministic, rules-governed workload — traditional software is the better fit")
    return s


# ------------------------------------------------------------------------ risk
def security_risk_score(req: AssessmentRequest) -> Score:
    org, dp, uc = req.organization, req.data_profile, req.use_case
    P = W.SECURITY_RISK_POINTS
    factors = [ScoreFactor(name=f"industry_baseline:{org.industry.value}", raw=1.0, weight=0, contribution=W.INDUSTRY_BASE_SECURITY_RISK[org.industry])]

    def add(name: str, active: bool, points: float) -> None:
        factors.append(ScoreFactor(name=name, raw=1.0 if active else 0.0, weight=points, contribution=points if active else 0.0))

    add("contains_pii", dp.contains_pii, P["contains_pii"])
    add("contains_financial_data", dp.contains_financial_data, P["contains_financial_data"])
    add("confidential", dp.confidential, P["confidential"])
    add("privileged", dp.privileged, P["privileged"])
    add("data_residency_required", dp.data_residency_required, P["data_residency_required"])
    ri = regulatory_intensity(req)
    factors.append(
        ScoreFactor(name="regulatory_intensity", raw=_u(ri), weight=5 * P["regulatory_intensity_per_point"], contribution=ri * P["regulatory_intensity_per_point"])
    )
    add("customer_facing", uc.customer_facing, P["customer_facing"])
    add("high_risk_write_actions", bool(set(uc.action_types) & HIGH_RISK_WRITE_ACTIONS), P["high_risk_write_actions"])
    add("deterministic_only_actions", bool(set(uc.action_types) & DETERMINISTIC_ONLY_ACTIONS), P["deterministic_only_actions"])

    ids = set(req.current_architecture.identity_security)
    M = W.SECURITY_MITIGATION_POINTS
    mitigations = {
        "rbac_or_abac": bool(ids & {IdentitySecurity.RBAC, IdentitySecurity.ABAC}),
        "secrets_management": IdentitySecurity.SECRETS_MANAGEMENT in ids,
        "private_networking": IdentitySecurity.PRIVATE_NETWORKING in ids,
        "api_gateway": IdentitySecurity.API_GATEWAY in ids,
    }
    for name, active in mitigations.items():
        factors.append(ScoreFactor(name=f"mitigation:{name}", raw=1.0 if active else 0.0, weight=-M[name], contribution=-M[name] if active else 0.0))
    value = round(min(max(sum(f.contribution for f in factors), 0.0), 100.0), 1)
    return Score(key="security_risk", label="Security Risk", value=value, factors=factors)


def operational_risk_score(req: AssessmentRequest, infra_value: float) -> Score:
    uc, org, cost = req.use_case, req.organization, req.cost_inputs
    volume = cost.requests_per_month
    volume_raw = 1.0 if volume > 1_000_000 else 0.6 if volume > 100_000 else 0.2 if volume > 10_000 else 0.0
    raws = {
        "transaction_criticality": _u(uc.transaction_criticality),
        "availability_requirement": _u(uc.availability_requirement),
        "latency_sensitivity": _u(uc.latency_sensitivity),
        "integration_complexity": _u(uc.cross_system_interaction),
        "legacy_interfaces": 1.0 if Integration.LEGACY_INTERFACE in req.current_architecture.integration else 0.0,
        "platform_gap": 1 - infra_value / 100,
        "ai_maturity_gap": 1 - _u(org.ai_maturity),
        "volume": volume_raw,
        "workflow_variability": _u(uc.workflow_variability),
    }
    weights = {
        "transaction_criticality": 25,
        "availability_requirement": 15,
        "latency_sensitivity": 10,
        "integration_complexity": 10,
        "legacy_interfaces": 5,
        "platform_gap": 15,
        "ai_maturity_gap": 10,
        "volume": 5,
        "workflow_variability": 5,
    }
    return _weighted("operational_risk", "Operational Risk", raws, weights)


def overall_risk_score(security: Score, operational: Score, data_value: float) -> Score:
    w = W.OVERALL_RISK_WEIGHTS
    raws = {"security_risk": security.value / 100, "operational_risk": operational.value / 100, "data_gap": 1 - data_value / 100}
    return _weighted("overall_risk", "Overall Risk", raws, {k: v * 100 for k, v in w.items()})


def roi_score(roi: ROIResult | None) -> Score:
    """Business value from benefit-to-cost ratio r: score = 100·r/(r+1.5)."""
    if roi is None:
        return Score(key="roi_business_value", label="ROI / Business Value", value=50.0, adjustments=["Pending cost/ROI calculation."])
    r = max(roi.benefit_to_cost_ratio, 0.0)
    value = round(100 * r / (r + 1.5), 1)
    return Score(
        key="roi_business_value",
        label="ROI / Business Value",
        value=value,
        factors=[ScoreFactor(name="benefit_to_cost_ratio", raw=round(r, 3), weight=100, contribution=value)],
        adjustments=[f"Verdict: {roi.verdict.value}"],
    )


_INTERPRETATIONS = {
    "ai_suitability": "Does AI add meaningful value over deterministic software?",
    "ml_suitability": "Is this primarily a prediction/classification/forecasting/ranking problem?",
    "genai_suitability": "Is generation/summarization/extraction/conversation central?",
    "rag_suitability": "Must answers be grounded in proprietary, changing documents with citations?",
    "agentic_readiness": "Does the workload genuinely need multi-step, tool-using, cross-system agents?",
    "infrastructure_readiness": "Can the existing platform host AI services safely?",
    "data_readiness": "Is the data available, governed and of sufficient quality?",
    "security_risk": "Inherent security/regulatory exposure of the workload (higher = riskier).",
    "operational_risk": "Operational criticality and delivery risk (higher = riskier).",
    "overall_risk": "Weighted blend of security, operational and data risk (higher = riskier).",
    "roi_business_value": "Business value relative to AI implementation and run cost.",
}
_RISK_KEYS = {"security_risk", "operational_risk", "overall_risk"}


def finalize(card: ScoreCard) -> ScoreCard:
    for key in type(card).model_fields:
        s: Score = getattr(card, key)
        s.band = W.band(s.value, higher_is_better=key not in _RISK_KEYS)
        s.interpretation = _INTERPRETATIONS[key]
    return card


def compute_scores(req: AssessmentRequest, roi: ROIResult | None = None) -> ScoreCard:
    """Compute the complete scorecard for a request."""
    infra = infrastructure_score(req.current_architecture)
    data = data_readiness_score(req.data_profile)
    security = security_risk_score(req)
    operational = operational_risk_score(req, infra.value)
    card = ScoreCard(
        ai_suitability=ai_suitability_score(req),
        ml_suitability=ml_score(req),
        genai_suitability=genai_score(req),
        rag_suitability=rag_score(req),
        agentic_readiness=agentic_score(req, infra.value),
        infrastructure_readiness=infra,
        data_readiness=data,
        security_risk=security,
        operational_risk=operational,
        overall_risk=overall_risk_score(security, operational, data.value),
        roi_business_value=roi_score(roi),
    )
    return finalize(card)
