import pytest

from app.core import policy
from app.core.policy import PolicyRequest, evaluate
from app.core.security import Actor, load_actor


def a(uid):
    return load_actor(uid)


AGENT = Actor(id="agent.test", display_name="t", role="agent", org="FF-Demo-MRO", is_agent=True)


@pytest.mark.parametrize("uid,label,expected", [
    ("guest", "PUBLIC", "ALLOW"), ("guest", "INTERNAL", "DENY"), ("exec.ava", "INTERNAL", "ALLOW"), ("exec.ava", "RESTRICTED", "DENY"),
    ("planner.marco", "RESTRICTED", "ALLOW"), ("arch.olu", "RESTRICTED", "DENY"), ("supplier.lee", "INTERNAL", "DENY"),
    ("planner.marco", "UNKNOWN", "DENY"), ("sec.ines", "UNKNOWN", "ALLOW"),
])
def test_classification_matrix(uid, label, expected):
    assert evaluate(a(uid), PolicyRequest(action="read", label=label)).decision == expected


def test_deny_by_default_for_unknown_role():
    rogue = Actor(id="x", display_name="x", role="contractor", org="FF-Demo-MRO")
    d = evaluate(rogue, PolicyRequest(action="read", label="PUBLIC"))
    assert d.decision == "DENY" and d.policy_id == "POL-001"


def test_rbac_denies_ungranted_action():
    d = evaluate(a("tech.jun"), PolicyRequest(action="approve", approval_id="APR-x"))
    assert d.decision == "DENY" and d.policy_id == "POL-002"


@pytest.mark.parametrize("dest,label,pid", [("personal_email", "RESTRICTED", "POL-004"), ("external_email", "INTERNAL", "POL-004"),
                                            ("external_url", "UNKNOWN", "POL-004")])
def test_external_export_denied(dest, label, pid):
    d = evaluate(a("planner.marco"), PolicyRequest(action="export", label=label, destination=dest))
    assert d.decision == "DENY" and d.policy_id == pid


def test_local_download_export_allowed_for_planner():
    assert evaluate(a("planner.marco"), PolicyRequest(action="export", label="INTERNAL", destination="local_download")).allowed


def test_agent_rights_are_intersection_with_human():
    d = evaluate(AGENT, PolicyRequest(action="read", label="RESTRICTED"), on_behalf_of=a("exec.ava"))
    assert d.decision == "DENY" and d.policy_id == "POL-003"
    d = evaluate(AGENT, PolicyRequest(action="read", label="INTERNAL"), on_behalf_of=a("guest"))
    assert d.decision == "DENY"


def test_retrieved_content_cannot_trigger_tools():
    d = evaluate(a("planner.marco"), PolicyRequest(action="tool_call", tool="docs.search", instruction_source="retrieved_content",
                                                   tool_registered=True, tool_pinned=True))
    assert d.decision == "DENY" and d.policy_id == "POL-011"


def test_unpinned_tool_denied():
    d = evaluate(a("planner.marco"), PolicyRequest(action="read", tool="shadow.tool", tool_registered=False))
    assert d.policy_id == "POL-006" and not d.allowed


def test_no_self_escalation():
    assert evaluate(AGENT, PolicyRequest(action="role_change", target_actor="someone")).policy_id == "POL-007"
    assert evaluate(a("sec.ines"), PolicyRequest(action="role_change", target_actor="sec.ines")).policy_id == "POL-007"
    assert evaluate(a("sec.ines"), PolicyRequest(action="policy_change")).policy_id == "POL-007"


def test_model_calls_must_be_local_and_enabled():
    d = evaluate(a("planner.marco"), PolicyRequest(action="model_call", model_target="https://api.example.com"))
    assert d.policy_id == "POL-008" and not d.allowed
    d = evaluate(a("planner.marco"), PolicyRequest(action="model_call", model_target="http://127.0.0.1:11434"))
    assert d.policy_id == "POL-008" and not d.allowed  # LLM disabled by default


def test_kill_switch_blocks_and_releases():
    sec = a("sec.ines")
    policy.set_kill_switch(True, sec)
    try:
        d = evaluate(a("planner.marco"), PolicyRequest(action="query"))
        assert d.policy_id == "POL-009" and not d.allowed
        assert evaluate(a("planner.marco"), PolicyRequest(action="read", label="INTERNAL")).allowed  # reads stay available
    finally:
        policy.set_kill_switch(False, sec)
    assert evaluate(a("planner.marco"), PolicyRequest(action="query")).allowed


def test_decisions_are_recorded_with_checks():
    d = evaluate(a("guest"), PolicyRequest(action="read", resource="unit-test", label="RESTRICTED"))
    rows = [r for r in policy.list_decisions("DENY", 50) if r["id"] == d.id]
    assert rows and rows[0]["checks"][-1]["result"] == "fail"


def test_stale_document_cannot_be_authoritative():
    d = evaluate(a("planner.marco"), PolicyRequest(action="read", label="INTERNAL", extra={"authoritative_citation": True, "doc_status": "superseded", "provenance": True}))
    assert d.policy_id == "POL-010" and not d.allowed
