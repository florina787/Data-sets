"""Step 1: identity, authorization-before-retrieval, audit and tracing."""

import jwt
import pytest

from wealth_ai.audit.log import AuditLog
from wealth_ai.observability.tracing import new_trace, span, trace_store
from wealth_ai.security.authz import AuthorizationError, entitlements
from wealth_ai.security.identity import AuthenticationError, Role, authenticate, issue_token


def test_valid_token_becomes_principal():
    p = authenticate(issue_token("adv-001", "Jordan Lee", ["advisor"]))
    assert p.user_id == "adv-001" and p.has_role(Role.ADVISOR)


def test_tampered_or_unsigned_tokens_are_rejected():
    forged = jwt.encode({"sub": "adv-001", "roles": ["compliance"]}, "wrong-secret", algorithm="HS256")
    with pytest.raises(AuthenticationError):
        authenticate(forged)
    with pytest.raises(AuthenticationError):
        authenticate(jwt.encode({"sub": "adv-001"}, None, algorithm="none"))


def test_expired_token_is_rejected():
    with pytest.raises(AuthenticationError):
        authenticate(issue_token("adv-001", "Jordan Lee", ["advisor"], ttl_s=-10))


def test_advisor_scope_is_limited_to_their_book():
    scope = entitlements.scope_for(authenticate(issue_token("adv-001", "Jordan Lee", ["advisor"])))
    scope.require_client("C-1001")
    with pytest.raises(AuthorizationError):
        scope.require_client("C-1003")  # another advisor's client
    assert "restricted" not in scope.classifications


def test_compliance_can_read_restricted_documents():
    scope = entitlements.scope_for(authenticate(issue_token("cmp-001", "Grace Kim", ["compliance"])))
    assert "restricted" in scope.classifications


def test_cache_partition_differs_per_entitlement():
    a = entitlements.scope_for(authenticate(issue_token("adv-001", "Jordan Lee", ["advisor"])))
    b = entitlements.scope_for(authenticate(issue_token("adv-002", "Priya Nair", ["advisor"])))
    assert a.fingerprint != b.fingerprint


def test_audit_log_detects_tampering():
    log = AuditLog()
    log.record("adv-001", "client_data_accessed", {"client_id": "C-1001"})
    log.record("adv-001", "llm_call", {"model": "mock"})
    assert log.verify() == (True, None)
    object.__setattr__(log._records[0], "details", {"client_id": "C-9999"})
    assert log.verify() == (False, 0)


def test_trace_records_spans():
    trace = new_trace(principal="adv-001", route="test")
    with span("retrieval", k=5):
        pass
    stored = trace_store.get(trace.trace_id).to_dict()
    assert stored["spans"][0]["name"] == "retrieval"
