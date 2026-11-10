"""Explicit, version-controlled weights and thresholds for the decision engine.

Keeping every number in one module makes the engine auditable: a reviewer can
see exactly why a score is what it is and change policy in a single place.
"""

from __future__ import annotations

from app.models.enums import Industry

ENGINE_VERSION = "1.0.0"

# --------------------------------------------------------------- suitability
ML_WEIGHTS = {"prediction_requirement": 55, "structured_data_share": 20, "data_quality": 15, "ml_task_match": 10}
GENAI_WEIGHTS = {
    "generation_requirement": 50,
    "unstructured_data_share": 15,
    "genai_task_match": 15,
    "hallucination_tolerance": 10,
    "non_deterministic_fit": 10,
}
RAG_WEIGHTS = {
    "proprietary_knowledge_need": 30,
    "citation_requirement": 15,
    "knowledge_change_frequency": 10,
    "unstructured_data_share": 15,
    "knowledge_fragmentation": 15,
    "document_quality": 15,
}
AGENTIC_NEED_WEIGHTS = {
    "multi_step_reasoning": 25,
    "workflow_variability": 20,
    "cross_system_interaction": 20,
    "tool_requirements": 20,
    "autonomy_benefit": 15,
}
#: Dimensions of the agentic need gate; at least AGENTIC_GATE_MIN_DIMENSIONS
#: must be rated >= AGENTIC_GATE_MIN_RATING before agents are even considered.
AGENTIC_GATE_DIMENSIONS = ("multi_step_reasoning", "workflow_variability", "cross_system_interaction", "tool_requirements")
AGENTIC_GATE_MIN_RATING = 3
AGENTIC_GATE_MIN_DIMENSIONS = 3

# --------------------------------------------------------------- thresholds
AI_SUITABILITY_MIN = 40.0
ML_MIN = 60.0
GENAI_MIN = 55.0
RAG_MIN = 60.0
AGENTIC_MIN = 60.0
#: Caps applied when a hard gate is not met.
GATE_CAP_ML = 30.0
GATE_CAP_GENAI = 30.0
GATE_CAP_RAG = 25.0
GATE_CAP_AGENTIC_NEED = 45.0
GATE_CAP_AGENTIC_FORBIDDEN = 20.0

DETERMINISTIC_WORKLOAD_MIN_RATING = 4

# --------------------------------------------------------------- risk
INDUSTRY_BASE_SECURITY_RISK: dict[Industry, float] = {
    Industry.BANKING: 30,
    Industry.FINANCIAL_SERVICES: 28,
    Industry.LEGAL: 26,
    Industry.RETAIL: 12,
    Industry.GENERAL_ENTERPRISE: 10,
}
INDUSTRY_DEFAULT_REGULATORY_INTENSITY: dict[Industry, int] = {
    Industry.BANKING: 5,
    Industry.FINANCIAL_SERVICES: 4,
    Industry.LEGAL: 4,
    Industry.RETAIL: 2,
    Industry.GENERAL_ENTERPRISE: 1,
}
SECURITY_RISK_POINTS = {
    "contains_pii": 10,
    "contains_financial_data": 8,
    "confidential": 6,
    "privileged": 10,
    "data_residency_required": 5,
    "regulatory_intensity_per_point": 2,
    "customer_facing": 5,
    "high_risk_write_actions": 8,
    "deterministic_only_actions": 10,
}
SECURITY_MITIGATION_POINTS = {"rbac_or_abac": 4, "secrets_management": 3, "private_networking": 3, "api_gateway": 2}

OVERALL_RISK_WEIGHTS = {"security_risk": 0.45, "operational_risk": 0.35, "data_gap": 0.20}

# --------------------------------------------------------------- ROI
ROI_PAYBACK_MAX_MONTHS = 36.0
ROI_PAYBACK_MARGINAL_MONTHS = 18.0


def band(value: float, *, higher_is_better: bool = True) -> str:
    """Human-readable band for a 0..100 score."""
    v = value if higher_is_better else 100 - value
    if v >= 75:
        return "HIGH" if higher_is_better else "LOW"
    if v >= 55:
        return "MODERATE-HIGH" if higher_is_better else "MODERATE-LOW"
    if v >= 35:
        return "MODERATE"
    return "LOW" if higher_is_better else "HIGH"
