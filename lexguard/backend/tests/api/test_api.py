"""FastAPI contract tests."""

from app.models.api import CopilotResponse


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["demo_mode"] is True
    assert r.json()["paid_llm_calls"] == 0


def test_demo_requires_no_api_key(client, as_user):
    import os
    from app.config import get_settings
    assert "ANTHROPIC_API_KEY" not in os.environ and not get_settings().live_llm_enabled
    r = client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "Which provisions require escalation?"},
                    headers=as_user("U-002"))
    assert r.status_code == 200 and r.json()["metrics"]["paid_llm_calls"] == 0


def test_copilot_returns_typed_response(client, as_user):
    r = client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "Review the contracts in this matter for change-of-control clauses."},
                    headers=as_user("U-002"))
    assert r.status_code == 200
    body = CopilotResponse.model_validate(r.json())
    assert body.status == "REVIEW_REQUIRED" and body.approval_required and body.cards and body.agent_trace
    assert {c.type for c in body.cards} >= {"ANALYSIS_SUMMARY", "PLAYBOOK_DEVIATION", "ASSURANCE", "APPROVAL"}


def test_input_validation(client, as_user):
    assert client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "x" * 2001}, headers=as_user("U-002")).status_code == 422
    assert client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "hi", "role": "PARTNER"},
                       headers=as_user("U-002")).status_code == 422
    assert client.post("/copilot/chat", json={"matter_id": "../etc", "message": "hi"}, headers=as_user("U-002")).status_code == 422
    assert client.get("/matters", headers=as_user("admin")).status_code == 401


def test_matters_redacts_inaccessible(client, as_user):
    rows = {m["matter_id"]: m for m in client.get("/matters", headers=as_user("U-002")).json()}
    assert rows["M-1001"]["client"] == "Maple Industries"
    assert rows["M-1003"]["client"] == "Restricted" and not rows["M-1003"]["access"]["permitted"]


def test_human_approval_and_partner_escalation(client, as_user):
    r = client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "Which provisions require escalation?"},
                    headers=as_user("U-002")).json()
    wp = r["work_product_id"]
    denied = client.post("/review/approve", json={"work_product_id": wp}, headers=as_user("U-002"))
    assert denied.status_code == 403 and denied.json()["detail"]["code"] == "ESCALATION_REQUIRES_PARTNER"
    para = client.post("/review/approve", json={"work_product_id": wp}, headers=as_user("U-005"))
    assert para.status_code == 403
    ok = client.post("/review/approve", json={"work_product_id": wp, "comment": "Escalations noted."}, headers=as_user("U-001"))
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"
    again = client.post("/review/reject", json={"work_product_id": wp}, headers=as_user("U-001"))
    assert again.status_code == 409


def test_rejection(client, as_user):
    r = client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "Research enforceability of sole discretion consent."},
                    headers=as_user("U-002")).json()
    rej = client.post("/review/reject", json={"work_product_id": r["work_product_id"], "comment": "Insufficient."},
                      headers=as_user("U-002"))
    assert rej.status_code == 200 and rej.json()["status"] == "REJECTED"


def test_assurance_failure_blocks_external_delivery(client, as_user):
    r = client.post("/copilot/chat", json={"matter_id": "M-1001", "message": "Verify the citations in the draft memo."},
                    headers=as_user("U-002")).json()
    assert r["assurance"]["status"] != "PASS" and r["approval"]["external_delivery_allowed"] is False
    wp = r["work_product_id"]
    blocked = client.post("/review/approve", json={"work_product_id": wp, "destination": "external_client"},
                          headers=as_user("U-001"))
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "ASSURANCE_GATE"
    internal = client.post("/review/approve", json={"work_product_id": wp, "destination": "internal"}, headers=as_user("U-001"))
    assert internal.status_code == 200


def test_reference_and_governance_endpoints(client, as_user):
    h = as_user("U-007")
    for path in ["/users", "/clients", "/providers", "/playbooks", "/agents", "/use-cases", "/inventory",
                 "/control-tower/metrics", "/value/metrics", "/evaluation/versions", "/audit/verify", "/audit/M-1001",
                 "/audit/security"]:
        assert client.get(path, headers=h).status_code == 200, path
    uc = client.get("/use-cases").json()
    assert len(uc["use_cases"]) == 45 and uc["counts"]["IMPLEMENTED"] + uc["counts"]["PARTIAL"] + uc["counts"]["PLANNED"] == 45
    assert client.post("/changeops/analyze", json={"policy_text": "All AI-generated legal research for external use requires citation verification."},
                       headers=as_user("U-005")).status_code == 403


def test_matterguard_routing_knowledge_endpoints(client, as_user):
    h = as_user("U-002")
    mg = client.post("/matterguard/evaluate", json={"matter_id": "M-1002", "provider_id": "P-MOCK-LEGAL-AI"}, headers=h).json()
    assert mg["decision"] == "PROHIBITED"
    rt = client.post("/routing/recommend", json={"matter_id": "M-1001", "task": "Review contracts for change of control"}, headers=h).json()
    assert rt["routing"]["route"] == "DOCUMENT_REVIEW_WORKFLOW"
    ks = client.post("/knowledge/search", json={"matter_id": "M-1001", "query": "veto escalation"}, headers=h).json()
    assert ks["results"] and all(x["matter_id"] in (None, "M-1001") for x in ks["results"])
    cv = client.post("/citations/verify", json={"matter_id": "M-1001", "propositions": [
        {"pid": "a", "claim": "x", "citation": {"doc_id": "KN-PB-MA", "section_id": "schedule-9"}}]}, headers=h).json()
    assert cv["results"][0]["status"] == "SOURCE_NOT_FOUND"
    pb = client.post("/playbook/check", json={"playbook_id": "PB-MA-COC", "items": [
        {"id": "r", "kind": "recommendation", "text": "Accept unrestricted counterparty veto."}]}, headers=h).json()
    assert pb["results"][0]["result"] == "ESCALATION_REQUIRED"
    an = client.post("/documents/analyze", json={"matter_id": "M-1001", "analysis_type": "change_of_control"}, headers=h).json()
    assert an["clauses"] == 63 and an["documents_processed"] == 487
    pv = client.post("/privilege/evaluate", json={"matter_id": "M-1004"}, headers=as_user("U-004")).json()
    assert pv["flags"]
    dr = client.post("/draft/generate", json={"matter_id": "M-1001", "draft_type": "due_diligence_report",
                                             "destination": "external_client"}, headers=h).json()
    assert dr["draft"]["client_facing"]
    asr = client.post("/assurance/evaluate", json={"matter_id": "M-1001", "work_product_id": "WP-MEMO-MAPLE-001",
                                                  "destination": "external_client"}, headers=h).json()
    assert asr["assurance"]["status"] == "REVIEW_REQUIRED"
    assert client.post("/documents/analyze", json={"matter_id": "M-1005", "analysis_type": "summary"}, headers=h).status_code == 403
