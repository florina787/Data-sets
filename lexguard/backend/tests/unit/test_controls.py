"""Deterministic control layer: RBAC, MatterGuard, policy, risk, suitability, router."""

from app.access.matter_access import check_ethical_wall, check_matter_access
from app.access.rbac import has_permission
from app.matterguard import guard as matterguard
from app.routing import router, suitability


def test_rbac_permissions(store):
    assert has_permission(store.users["U-001"], "approve_escalation")
    assert not has_permission(store.users["U-002"], "approve_escalation")
    assert not has_permission(store.users["U-005"], "request_external_provider")
    assert not has_permission(store.users["U-009"], "view_matter_content")  # admins get no implicit matter access


def test_matter_access_named_team_and_practice_group(store):
    assert check_matter_access(store, store.users["U-002"], store.matters["M-1001"]).allowed
    assert not check_matter_access(store, store.users["U-010"], store.matters["M-1001"]).allowed
    # Matter Beta uses a practice-group model: a litigation associate passes RBAC ...
    acc = check_matter_access(store, store.users["U-003"], store.matters["M-1003"])
    assert acc.allowed and acc.via == "practice_group"
    # ... but the ethical wall still blocks.
    assert check_ethical_wall(store, store.users["U-003"], "M-1003").blocked


def test_client_external_ai_prohibition(store):
    r = matterguard.evaluate(store, user_id="U-002", matter_id="M-1002", provider_id="P-MOCK-LEGAL-AI")
    assert r.decision == "PROHIBITED"
    assert any(e.rule_id == "POL-CLIENT-003" for e in r.policy_evidence)
    assert "external_provider_call" in r.blocked_tools
    assert r.alternatives and "Internal RAG" in r.alternatives[0]


def test_provider_restrictions(store):
    harvey = matterguard.evaluate(store, user_id="U-002", matter_id="M-1001", provider_id="P-HARVEY")
    assert harvey.decision == "PROHIBITED" and any(e.rule_id == "POL-PROV-001" for e in harvey.policy_evidence)
    ent = matterguard.evaluate(store, user_id="U-004", matter_id="M-1004", provider_id="P-ENTERPRISE-COPILOT")
    assert ent.decision == "RESTRICTED" and "privileged" in ent.excluded_doc_sensitivities
    para = matterguard.evaluate(store, user_id="U-005", matter_id="M-1001", provider_id="P-MOCK-LEGAL-AI")
    assert para.decision == "PROHIBITED" and any(e.rule_id == "POL-RBAC-001" for e in para.policy_evidence)
    ok = matterguard.evaluate(store, user_id="U-002", matter_id="M-1001", provider_id="P-MOCK-LEGAL-AI")
    assert ok.decision == "PERMITTED_WITH_CONTROLS" and ok.provider_permitted


def test_ai_prohibited_client_level_zero(store):
    r = matterguard.evaluate(store, user_id="U-002", matter_id="M-1005", provider_id="P-INTERNAL-RAG")
    assert r.decision == "PROHIBITED" and r.human_review_level == 0 and not r.ai_allowed_for_matter
    assert all(t not in r.allowed_tools for t in ("clause_extraction", "draft_generate", "summarize"))
    assert "traditional_search" in r.allowed_tools


def test_risk_scoring_deterministic(store):
    a = [matterguard.evaluate(store, user_id="U-002", matter_id="M-1001", destination="external_client").model_dump()
         for _ in range(5)]
    assert all(x == a[0] for x in a)
    assert a[0]["risk"] == "MEDIUM" and a[0]["risk_score"] == 3
    aurora = matterguard.evaluate(store, user_id="U-002", matter_id="M-1002", provider_id="P-MOCK-LEGAL-AI",
                                  destination="external_client")
    assert aurora.risk == "CRITICAL" and aurora.risk_score == 6


def test_ai_suitability_deterministic():
    kw = dict(intent="contract_review", doc_count=487, doc_sensitivities=["confidential"], privileged_share=0.0,
              client_ai_allowed=True, client_external_allowed=True, external_destination=False, external_provider=False,
              human_review_level=2)
    results = [suitability.score(**kw).model_dump() for _ in range(5)]
    assert all(r == results[0] for r in results)
    r = results[0]
    assert (r["ai_suitability"], r["agentic_suitability"], r["legal_judgment_risk"]) == (82, 56, 39)
    lj = suitability.score(**{**kw, "intent": "legal_judgment"})
    assert lj.legal_judgment_risk == 100 and lj.bands["autonomy_risk"] == "HIGH"
    prohibited = suitability.score(**{**kw, "client_ai_allowed": False})
    assert prohibited.ai_suitability == 0


def test_router_never_defaults_to_agentic(store):
    mg = matterguard.evaluate(store, user_id="U-002", matter_id="M-1001", intent="contract_review")
    for intent in suitability.TASK_PROFILES:
        s = suitability.score(intent=intent, doc_count=487, doc_sensitivities=["confidential"], privileged_share=0,
                              client_ai_allowed=True, client_external_allowed=True, external_destination=False,
                              external_provider=False, human_review_level=2)
        dec = router.recommend(intent=intent, mg=mg, suit=s, doc_count=487, requested_provider=None)
        assert dec.route != "AGENTIC_WORKFLOW"
        assert any(o.route == "AGENTIC_WORKFLOW" and not o.selected for o in dec.options)


def test_due_diligence_routes_to_document_review(store):
    mg = matterguard.evaluate(store, user_id="U-002", matter_id="M-1001", intent="contract_review")
    s = suitability.score(intent="contract_review", doc_count=487, doc_sensitivities=["confidential"], privileged_share=0,
                          client_ai_allowed=True, client_external_allowed=True, external_destination=False,
                          external_provider=False, human_review_level=2)
    assert router.recommend(intent="contract_review", mg=mg, suit=s, doc_count=487, requested_provider=None).route == \
        "DOCUMENT_REVIEW_WORKFLOW"
