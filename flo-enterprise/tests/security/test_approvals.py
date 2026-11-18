from datetime import datetime, timedelta

import pytest

from approvals.service import ApprovalError, payload_hash
from backend.db import models as m
from backend.db.session import session_scope
from governance.policy import Resource

pytestmark = pytest.mark.critical
PAYLOAD = {"to": "client", "subject": "Review", "body": "Approved text"}


@pytest.fixture
def svc(st):
    from backend import runtime as R
    return R.approval_service(st)


def _request(svc, P, cid, payload=PAYLOAD):
    with session_scope() as s:
        return svc.request(s, P["u-advisor"], "comms:send", f"client:{cid}", payload, [{"type": "test"}]).id


def _decide(svc, P, aid, user="u-compliance", h=None, approve=True):
    with session_scope() as s:
        return svc.decide(s, P[user], aid, approve, h or payload_hash(PAYLOAD)).status


def _exec(svc, P, aid, payload=PAYLOAD, user="u-advisor"):
    with session_scope() as s:
        try:
            return svc.execute(s, P[user], aid, payload).status
        except ApprovalError as e:
            return e.code


def test_full_lifecycle_and_replay(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    with session_scope() as s:
        a = s.get(m.Approval, aid)
        assert a.status == "pending" and a.payload_hash == payload_hash(PAYLOAD) and a.risk_class == "high"
        assert a.expires_at > datetime.utcnow() and a.approver_role == "compliance_officer"
    assert _exec(svc, P, aid) == "NOT_APPROVED"
    assert _decide(svc, P, aid) == "approved"
    assert _exec(svc, P, aid) == "executed"
    assert _exec(svc, P, aid) == "REPLAY"
    with session_scope() as s:
        ob = s.query(m.Outbox).filter(m.Outbox.approval_id == aid).one()
        assert ob.status == "queued_mock"


def test_requester_must_be_authorized(svc, P, other_client):
    with session_scope() as s, pytest.raises(ApprovalError) as e:
        svc.request(s, P["u-advisor"], "comms:send", f"client:{other_client}", PAYLOAD, [])
    assert e.value.code == "REQUEST_NOT_AUTHORIZED"


def test_self_approval_and_wrong_role(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    with session_scope() as s, pytest.raises(ApprovalError) as e:
        svc.decide(s, P["u-advisor"], aid, True, payload_hash(PAYLOAD))
    assert e.value.code == "APPROVER_NOT_AUTHORIZED"
    with session_scope() as s, pytest.raises(ApprovalError) as e:
        svc.decide(s, P["u-cio"], aid, True, payload_hash(PAYLOAD))
    assert e.value.code == "APPROVER_ROLE_MISMATCH"


def test_cross_tenant_approver_cannot_see(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    with session_scope() as s, pytest.raises(ApprovalError) as e:
        svc.decide(s, P["u-nw-advisor"], aid, True, payload_hash(PAYLOAD))
    assert e.value.code == "NOT_FOUND"


def test_approver_must_confirm_reviewed_hash(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    with session_scope() as s, pytest.raises(ApprovalError) as e:
        svc.decide(s, P["u-compliance"], aid, True, "0" * 64)
    assert e.value.code == "PAYLOAD_HASH_MISMATCH"


def test_payload_change_invalidates(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    _decide(svc, P, aid)
    assert _exec(svc, P, aid, {**PAYLOAD, "body": "Approved text - plus a guaranteed 12% return!"}) == "PAYLOAD_CHANGED"
    with session_scope() as s:
        assert s.get(m.Approval, aid).status == "invalidated"
    assert _exec(svc, P, aid) == "NOT_APPROVED"  # even the original payload cannot run after invalidation


def test_expiry(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    _decide(svc, P, aid)
    with session_scope() as s:
        s.get(m.Approval, aid).expires_at = datetime.utcnow() - timedelta(minutes=1)
    assert _exec(svc, P, aid) == "EXPIRED"


def test_only_requester_executes(svc, P, a001_client):
    aid = _request(svc, P, a001_client)
    _decide(svc, P, aid)
    assert _exec(svc, P, aid, user="u-advisor2") in ("NOT_REQUESTER",)


def test_revalidation_at_execution(st, P, a001_client):
    """If the client is reassigned after approval, execution is denied."""
    from approvals.service import ApprovalService
    from governance.policy import get_policy_engine
    state = {"advisor": "A-001"}
    svc = ApprovalService(get_policy_engine(), lambda tid, ref: Resource("client", ref.split(":")[1], "t-flo",
                                                                         {"advisor_id": state["advisor"], "classification": "confidential"}))
    aid = _request(svc, P, a001_client)
    _decide(svc, P, aid)
    state["advisor"] = "A-009"
    assert _exec(svc, P, aid) == "REVALIDATION_FAILED"
