"""Mandatory decision-engine behaviours."""

from __future__ import annotations

from app.decision_engine.engine import decide
from app.decision_engine.scoring import compute_scores
from app.models.enums import (
    ActionType,
    AgenticVerdict,
    ArchitectureOption,
    AutonomyLevel,
    DataStore,
    Industry,
    MatrixDecision,
)
from app.models.inputs import AssessmentRequest
from app.scenarios import scenario_request
from app.services import run_assessment
from tests.conftest import agentic_request

A = ArchitectureOption


# 1
def test_banking_deterministic_transaction_rules_reject_agentic_ai(assess):
    r = assess("banking-transaction-rules")
    d = r.decision
    assert d.agentic_verdict is AgenticVerdict.NOT_RECOMMENDED
    assert d.agentic_verdict_label == "AGENTIC AI NOT RECOMMENDED"
    assert d.primary_architecture is A.KEEP_EXISTING
    assert d.ai_recommended is False
    assert d.ai_verdict_label == "DO NOT USE AI"
    assert "Rules Engine" in d.architecture_label
    assert any(rule.startswith("R-DET-01") for rule in d.triggered_rules)
    assert any(rule.startswith("R-REPL-01") for rule in d.triggered_rules)
    rules_engine = next(m for m in r.matrix if m.component == "Transaction Rules Engine")
    assert rules_engine.decision is MatrixDecision.KEEP
    reasons = " ".join(d.agentic_rationale).lower()
    for word in ("nondeterminism", "hallucination", "latency", "cost"):
        assert word in reasons


# 2
def test_document_heavy_knowledge_workflow_can_recommend_rag(assess):
    d = assess("banking-policy-knowledge").decision
    assert d.primary_architecture is A.RAG_GENAI
    assert A.RAG_GENAI in d.ai_patterns
    assert d.citations_mandatory is True
    assert d.human_review_mandatory is True


# 3
def test_cross_system_variable_investigation_can_recommend_agentic(assess):
    d = assess("finops-incident-investigation").decision
    assert d.primary_architecture is A.AGENTIC_AI
    assert d.agentic_verdict is AgenticVerdict.CONSTRAINED
    assert "CONSTRAINED AGENTIC AI RECOMMENDED" in d.agentic_verdict_label


# 4
def test_high_regulatory_risk_reduces_autonomy():
    low_risk_actions = [ActionType.READ_ONLY, ActionType.TICKET_UPDATE]
    retail = agentic_request(Industry.RETAIL, low_risk_actions)
    banking = agentic_request(Industry.BANKING, low_risk_actions)
    retail_level = run_assessment(retail).decision.autonomy_level
    banking_level = run_assessment(banking).decision.autonomy_level
    assert banking_level < retail_level
    assert banking_level <= AutonomyLevel.APPROVAL_REQUIRED
    explicit = agentic_request(Industry.RETAIL, low_risk_actions)
    explicit.organization.regulatory_intensity = 5
    assert run_assessment(explicit).decision.autonomy_level <= AutonomyLevel.APPROVAL_REQUIRED


# 5
def test_existing_kubernetes_is_not_replaced(assess):
    for sid in ["banking-transaction-rules", "banking-policy-knowledge", "retail-customer-service", "finops-incident-investigation", "retail-demand-forecasting"]:
        r = assess(sid)
        k8s = [m for m in r.matrix if m.component == "Kubernetes"]
        assert k8s and all(m.decision is MatrixDecision.KEEP for m in k8s), sid
        assert not any(m.decision is MatrixDecision.REPLACE for m in r.matrix), sid
        assert "Kubernetes" in r.target_architecture.target_state_mermaid


def test_replace_only_for_components_flagged_end_of_life():
    req = scenario_request("banking-policy-knowledge")
    req.current_architecture.end_of_life_components = ["Enterprise Search"]
    r = run_assessment(req)
    replaced = [m.component for m in r.matrix if m.decision is MatrixDecision.REPLACE]
    assert replaced == ["Enterprise Search"]


# 6
def test_existing_microservices_remain_authoritative(assess):
    for sid in ["finops-incident-investigation", "retail-customer-service", "banking-incident-investigation"]:
        r = assess(sid)
        assert "Existing microservices" in r.decision.authoritative_systems
        ms = next(m for m in r.matrix if m.component == "Microservices")
        assert ms.decision is MatrixDecision.KEEP
        assert "authoritative" in ms.reason
    retail = assess("retail-customer-service").decision
    assert retail.primary_architecture is A.HYBRID
    assert retail.architecture_label.startswith("Existing Microservices")


# 7
def test_rag_is_not_automatically_recommended(assess):
    r = assess("retail-demand-forecasting")  # vector DB exists in current state
    assert DataStore.VECTOR_DATABASE.value in [d.value for d in scenario_request("retail-demand-forecasting").current_architecture.data_stores]
    assert A.RAG_GENAI not in r.decision.ai_patterns
    assert r.decision.primary_architecture is A.TRADITIONAL_ML
    assert any("vector database" in adj.lower() for adj in r.scores.rag_suitability.adjustments)
    rag_rows = [m for m in r.matrix if m.component == "RAG Service"]
    assert rag_rows[0].decision is MatrixDecision.NOT_ADDED
    default = run_assessment(AssessmentRequest())
    assert A.RAG_GENAI not in default.decision.ai_patterns


def test_rag_deferred_when_data_not_ready():
    req = scenario_request("banking-policy-knowledge")
    req.data_profile.document_quality = 1
    req.data_profile.permissions = 1
    r = run_assessment(req)
    assert A.RAG_GENAI not in r.decision.ai_patterns
    assert any("R-RAG-DATA" in rule for rule in r.decision.triggered_rules)


# 8
def test_agentic_ai_is_not_automatically_recommended(assess):
    for sid in ["banking-policy-knowledge", "legal-research", "retail-customer-service", "retail-demand-forecasting", "banking-transaction-rules"]:
        assert assess(sid).decision.agentic_verdict is AgenticVerdict.NOT_RECOMMENDED, sid
    default = run_assessment(AssessmentRequest())
    assert default.decision.agentic_verdict is AgenticVerdict.NOT_RECOMMENDED
    lg = next(m for m in assess("banking-policy-knowledge").matrix if m.component == "LangGraph AI Orchestrator")
    assert lg.decision is MatrixDecision.NOT_ADDED


def test_deterministic_only_actions_cap_agentic_even_with_high_need():
    req = scenario_request("finops-incident-investigation")
    req.use_case.action_types = [ActionType.READ_ONLY, ActionType.MONEY_MOVEMENT]
    scores = compute_scores(req)
    assert scores.agentic_readiness.value <= 20
    d = decide(req, scores)
    assert d.agentic_verdict is AgenticVerdict.NOT_RECOMMENDED
    money = next(p for p in d.action_policies if p.action is ActionType.MONEY_MOVEMENT)
    assert "deterministic" in money.executor.lower()


# 13
def test_high_risk_write_actions_require_human_approval(assess):
    d = assess("finops-incident-investigation").decision
    assert d.requires_human_approval is True
    assert d.autonomy_level <= AutonomyLevel.APPROVAL_REQUIRED
    remediation = next(p for p in d.action_policies if p.action is ActionType.PRODUCTION_REMEDIATION)
    assert remediation.max_ai_autonomy <= AutonomyLevel.APPROVAL_REQUIRED
    assert "approves" in remediation.executor
    retail = run_assessment(agentic_request(Industry.RETAIL, [ActionType.READ_ONLY, ActionType.PRODUCTION_REMEDIATION]))
    assert retail.decision.requires_human_approval is True
    assert retail.decision.autonomy_level <= AutonomyLevel.APPROVAL_REQUIRED


def test_legal_requires_citations_and_human_review(assess):
    r = assess("legal-research")
    assert r.decision.primary_architecture is A.RAG_GENAI
    assert r.decision.architecture_label.startswith("Secure RAG")
    assert r.decision.citations_mandatory and r.decision.human_review_mandatory
    assert r.decision.autonomy_level <= AutonomyLevel.SUGGEST


def test_scores_are_bounded_and_explainable(assess):
    r = assess("retail-customer-service")
    for key in type(r.scores).model_fields:
        s = getattr(r.scores, key)
        assert 0 <= s.value <= 100
        assert s.band and s.interpretation


def test_engine_is_deterministic():
    req = scenario_request("retail-customer-service")
    a, b = run_assessment(req), run_assessment(req)
    assert a.scores.as_dict() == b.scores.as_dict()
    assert a.decision.model_dump(exclude={"pattern_design"}) == b.decision.model_dump(exclude={"pattern_design"})
