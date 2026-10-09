"""End-to-end Copilot graph flows (LangGraph supervisor) for every demo scenario."""

from app.audit import service as audit
from app.graph.builder import run_copilot
from app.providers.llm import paid_llm_calls

COC = "Review our contracts for change-of-control clauses and compare them against the firm's M&A playbook."


def test_primary_ma_demo_numbers():
    r = run_copilot(user_id="U-002", matter_id="M-1001", message=COC)
    rs = r["review_summary"]
    assert rs["documents_in_matter"] == 500 and rs["documents_processed"] == 487
    assert rs["duplicates"] == 8 and rs["unreadable"] == 5
    assert len(r["findings"]) == 63
    assert len(r["playbook_deviations"]) == 11
    assert sum(1 for d in r["playbook_deviations"] if d["result"] == "ESCALATION_REQUIRED") == 3
    assert sum(1 for f in r["findings"] if f["evidence_status"] != "VERIFIED") == 2
    assert r["status"] == "REVIEW_REQUIRED" and r["approval_required"]
    assert r["assurance"]["status"] == "REVIEW_REQUIRED"
    assert r["routing"]["route"] == "DOCUMENT_REVIEW_WORKFLOW"
    labels = [t["label"] for t in r["agent_trace"]]
    for expected in ("Matter access verified", "Client AI policy checked", "Citation verification completed",
                     "Confidentiality review completed", "Lawyer approval pending"):
        assert any(expected in l for l in labels), expected
    assert r["metrics"]["paid_llm_calls"] == 0


def test_supervisor_invokes_only_needed_agents():
    r = run_copilot(user_id="U-002", matter_id="M-1001", message="Can I use external AI for this matter?")
    agents = set(r["metrics"]["agents_invoked"])
    assert "document_analysis" not in agents and "drafting" not in agents and "citation_verification" not in agents
    assert r["status"] == "COMPLETED"


def test_draft_excludes_unverified_findings():
    r = run_copilot(user_id="U-002", matter_id="M-1001", message="Prepare a client-ready draft.")
    d = r["draft"]
    assert d["client_facing"] and len(d["excluded_pending_review"]) == 2
    included = {c["doc_id"] for p in d["paragraphs"] for c in p["citations"]}
    excluded = {e["doc_id"] for e in d["excluded_pending_review"]}
    assert not (included & excluded)


def test_aurora_external_ai_blocked_with_audit():
    r = run_copilot(user_id="U-002", matter_id="M-1002", message="Send these documents to the external legal AI provider for analysis.")
    assert r["status"] == "BLOCKED"
    assert any(e["rule_id"] == "POL-CLIENT-003" for e in r["matterguard"]["policy_evidence"])
    events = audit.events_for_request(r["request_id"])
    types = {e["event_type"] for e in events}
    assert "POLICY_BLOCK" in types and "PROVIDER_INVOKED" not in types and "RETRIEVAL" not in types
    assert any(c["type"] == "POLICY_BLOCK" for c in r["cards"])
    why = run_copilot(user_id="U-002", matter_id="M-1002", message="Why was this workflow blocked?")
    assert "POL-CLIENT-003" in why["answer"]


def test_external_provider_permitted_goes_through_gateway_and_assurance():
    r = run_copilot(user_id="U-002", matter_id="M-1001", message="Send these documents to the external legal AI provider for analysis.")
    assert r["routing"]["route"] == "EXTERNAL_LEGAL_AI"
    types = [e["event_type"] for e in audit.events_for_request(r["request_id"])]
    assert "PROVIDER_INVOKED" in types and "ASSURANCE_RESULT" in types and "HUMAN_REVIEW_PENDING" in types


def test_legal_judgment_routes_to_human():
    r = run_copilot(user_id="U-004", matter_id="M-1004", message="Should our client accept the $20 million settlement?")
    assert r["status"] == "HUMAN_DECISION_REQUIRED" and r["routing"]["route"] == "HUMAN_LAWYER"
    assert "will not recommend" in r["answer"]
    assert set(r["routing"]["ai_support_permitted"]) >= {"Evidence synthesis from matter documents"}


def test_level_zero_matter_routes_to_human_without_ai_tools():
    r = run_copilot(user_id="U-002", matter_id="M-1005", message="Summarize the findings letter.")
    assert r["status"] == "BLOCKED" and r["routing"]["route"] == "HUMAN_LAWYER"
    assert r["metrics"]["tools_invoked"] == []


def test_agent_iteration_limit_halts():
    r = run_copilot(user_id="U-002", matter_id="M-1001", message="Draft a due diligence summary using only verified findings.",
                    cfg={"max_agent_steps": 1})
    assert r["status"] == "HALTED"
    assert any("iteration limit" in e.lower() for e in r["errors"])
    assert "AGENT_ITERATION_LIMIT" in {e["event_type"] for e in audit.events_for_request(r["request_id"])}


def test_tool_budget_and_timeout_enforced():
    r = run_copilot(user_id="U-002", matter_id="M-1001", message=COC, cfg={"max_tool_calls": 2})
    assert r["status"] in ("BLOCKED", "ERROR", "HALTED") and r["errors"]
    t = run_copilot(user_id="U-002", matter_id="M-1001", message=COC, cfg={"timeout_s": 0.0})
    assert t["status"] == "HALTED"


def test_audit_trace_complete_and_chain_valid(client, as_user):
    r = run_copilot(user_id="U-002", matter_id="M-1001", message=COC)
    wp = r["work_product_id"]
    ok = client.post("/review/approve", json={"work_product_id": wp, "comment": "Reviewed."}, headers=as_user("U-001"))
    assert ok.status_code == 200
    chain = [e["event_type"] for e in audit.trace_chain(r["request_id"])]
    for t in ["REQUEST_RECEIVED", "ACCESS_DECISION", "ETHICAL_WALL_DECISION", "POLICY_DECISION", "SUITABILITY_ASSESSED",
              "ROUTING_DECISION", "RETRIEVAL", "AGENT_INVOKED", "WORK_PRODUCT_CREATED", "ASSURANCE_RESULT",
              "HUMAN_REVIEW_PENDING", "HUMAN_REVIEW_APPROVED", "FINAL_STATUS"]:
        assert t in chain, t
    assert chain.index("ACCESS_DECISION") < chain.index("POLICY_DECISION") < chain.index("ROUTING_DECISION") \
        < chain.index("ASSURANCE_RESULT") < chain.index("HUMAN_REVIEW_APPROVED")
    assert audit.verify_chain()["valid"]


def test_demo_mode_zero_paid_llm_calls_across_scenarios():
    before = paid_llm_calls()
    for u, mt, msg in [("U-002", "M-1001", COC), ("U-002", "M-1001", "Prepare a client-ready draft."),
                       ("U-002", "M-1001", "Research enforceability of sole discretion consent."),
                       ("U-004", "M-1004", "Should our client accept the $20 million settlement?")]:
        assert run_copilot(user_id=u, matter_id=mt, message=msg)["metrics"]["paid_llm_calls"] == 0
    assert paid_llm_calls() == before == 0
