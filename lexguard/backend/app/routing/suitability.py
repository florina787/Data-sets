"""Deterministic AI-suitability scoring. Same inputs -> same scores, always."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.domain import sensitivity_rank

# Factors in [0, 1]. Documented in docs/GOVERNANCE.md.
TASK_PROFILES: dict[str, dict[str, float]] = {
    "contract_review":   dict(repeatability=0.9, legal_judgment=0.35, knowledge_retrieval=0.6, cross_system=0.3, consequence=0.5, hallucination_tolerance=0.2, source_availability=1.0),
    "playbook_compare":  dict(repeatability=0.9, legal_judgment=0.35, knowledge_retrieval=0.7, cross_system=0.3, consequence=0.5, hallucination_tolerance=0.2, source_availability=1.0),
    "escalation_query":  dict(repeatability=0.8, legal_judgment=0.4, knowledge_retrieval=0.6, cross_system=0.2, consequence=0.5, hallucination_tolerance=0.2, source_availability=1.0),
    "show_evidence":     dict(repeatability=0.9, legal_judgment=0.1, knowledge_retrieval=0.9, cross_system=0.1, consequence=0.3, hallucination_tolerance=0.1, source_availability=1.0),
    "draft_memo":        dict(repeatability=0.6, legal_judgment=0.5, knowledge_retrieval=0.7, cross_system=0.4, consequence=0.6, hallucination_tolerance=0.1, source_availability=0.9),
    "client_draft":      dict(repeatability=0.5, legal_judgment=0.6, knowledge_retrieval=0.7, cross_system=0.4, consequence=0.8, hallucination_tolerance=0.05, source_availability=0.9),
    "research":          dict(repeatability=0.6, legal_judgment=0.4, knowledge_retrieval=0.9, cross_system=0.3, consequence=0.5, hallucination_tolerance=0.1, source_availability=0.8),
    "knowledge_question": dict(repeatability=0.8, legal_judgment=0.2, knowledge_retrieval=0.9, cross_system=0.1, consequence=0.2, hallucination_tolerance=0.3, source_availability=0.9),
    "summarize":         dict(repeatability=0.9, legal_judgment=0.15, knowledge_retrieval=0.5, cross_system=0.1, consequence=0.3, hallucination_tolerance=0.3, source_availability=1.0),
    "extract_obligations": dict(repeatability=0.9, legal_judgment=0.2, knowledge_retrieval=0.4, cross_system=0.1, consequence=0.4, hallucination_tolerance=0.2, source_availability=1.0),
    "extract_timeline":  dict(repeatability=0.9, legal_judgment=0.1, knowledge_retrieval=0.4, cross_system=0.2, consequence=0.4, hallucination_tolerance=0.2, source_availability=1.0),
    "extract_entities":  dict(repeatability=0.95, legal_judgment=0.05, knowledge_retrieval=0.3, cross_system=0.1, consequence=0.2, hallucination_tolerance=0.3, source_availability=1.0),
    "compare_documents": dict(repeatability=0.9, legal_judgment=0.2, knowledge_retrieval=0.3, cross_system=0.1, consequence=0.4, hallucination_tolerance=0.2, source_availability=1.0),
    "citation_verify":   dict(repeatability=1.0, legal_judgment=0.1, knowledge_retrieval=0.8, cross_system=0.1, consequence=0.6, hallucination_tolerance=0.0, source_availability=1.0),
    "recommendation_check": dict(repeatability=0.9, legal_judgment=0.3, knowledge_retrieval=0.7, cross_system=0.1, consequence=0.6, hallucination_tolerance=0.1, source_availability=1.0),
    "privilege_review":  dict(repeatability=0.7, legal_judgment=0.6, knowledge_retrieval=0.5, cross_system=0.2, consequence=0.8, hallucination_tolerance=0.05, source_availability=1.0),
    "legal_judgment":    dict(repeatability=0.1, legal_judgment=1.0, knowledge_retrieval=0.5, cross_system=0.5, consequence=1.0, hallucination_tolerance=0.0, source_availability=0.6),
    "external_provider_request": dict(repeatability=0.8, legal_judgment=0.35, knowledge_retrieval=0.5, cross_system=0.6, consequence=0.6, hallucination_tolerance=0.2, source_availability=1.0),
    "policy_question":   dict(repeatability=1.0, legal_judgment=0.05, knowledge_retrieval=0.8, cross_system=0.0, consequence=0.3, hallucination_tolerance=0.0, source_availability=1.0),
    "explain_block":     dict(repeatability=1.0, legal_judgment=0.0, knowledge_retrieval=0.6, cross_system=0.0, consequence=0.2, hallucination_tolerance=0.0, source_availability=1.0),
    "value_query":       dict(repeatability=1.0, legal_judgment=0.0, knowledge_retrieval=0.2, cross_system=0.2, consequence=0.1, hallucination_tolerance=0.2, source_availability=1.0),
    "cross_matter_request": dict(repeatability=0.0, legal_judgment=0.0, knowledge_retrieval=0.0, cross_system=0.0, consequence=1.0, hallucination_tolerance=0.0, source_availability=0.0),
    "search":            dict(repeatability=1.0, legal_judgment=0.0, knowledge_retrieval=0.8, cross_system=0.0, consequence=0.2, hallucination_tolerance=0.3, source_availability=1.0),
}


class SuitabilityResult(BaseModel):
    intent: str
    ai_suitability: int
    agentic_suitability: int
    legal_judgment_risk: int
    confidentiality_risk: int
    privilege_risk: int
    autonomy_risk: int
    evidence_requirement: int
    human_review_requirement: int
    bands: dict[str, str]
    factors: dict[str, float]


def band(v: int) -> str:
    return "HIGH" if v >= 70 else "MEDIUM" if v >= 40 else "LOW"


def score(*, intent: str, doc_count: int, doc_sensitivities: list[str], privileged_share: float,
          client_ai_allowed: bool, client_external_allowed: bool, external_destination: bool,
          external_provider: bool, human_review_level: int) -> SuitabilityResult:
    p = dict(TASK_PROFILES.get(intent, TASK_PROFILES["knowledge_question"]))
    volume = min(1.0, doc_count / 200.0)
    p.update(volume=round(volume, 3), external_distribution=1.0 if external_destination else 0.0,
             client_restriction=0.0 if client_ai_allowed and client_external_allowed else 0.5 if client_ai_allowed else 1.0)
    lj, cons, ht = p["legal_judgment"], p["consequence"], p["hallucination_tolerance"]
    max_sens = max((sensitivity_rank(s) for s in doc_sensitivities), default=1)

    ai = 100 * (0.25 * p["repeatability"] + 0.20 * volume + 0.20 * p["knowledge_retrieval"]
                + 0.15 * p["source_availability"] + 0.20 * (1 - lj))
    ai -= 15 * p["client_restriction"] if client_ai_allowed else 100
    agentic = 100 * (0.35 * p["cross_system"] + 0.25 * p["repeatability"] + 0.20 * (1 - lj) + 0.20 * (1 - cons))
    legal_risk = 100 * (0.7 * lj + 0.3 * cons)
    conf = 100 * (max_sens / 4) * 0.7 + 15 * int(external_provider) + 15 * int(external_destination)
    priv = min(100, 100 * privileged_share * 2 + (40 if privileged_share > 0 else 0))
    autonomy = 100 * (0.5 * cons + 0.3 * lj + 0.2 * (1 - ht))
    evidence = 100 * (0.6 * (1 - ht) + 0.4 * p["external_distribution"])
    review = max(25 * human_review_level, round(0.5 * evidence + 0.5 * legal_risk))

    def clamp(v: float) -> int:
        return int(max(0, min(100, round(v))))

    ai_i = clamp(ai)
    agentic_i = min(clamp(agentic), ai_i)
    vals = dict(ai_suitability=ai_i, agentic_suitability=agentic_i, legal_judgment_risk=clamp(legal_risk),
                confidentiality_risk=clamp(conf), privilege_risk=clamp(priv), autonomy_risk=clamp(autonomy),
                evidence_requirement=clamp(evidence), human_review_requirement=clamp(review))
    return SuitabilityResult(intent=intent, **vals, bands={k: band(v) for k, v in vals.items()}, factors=p)
