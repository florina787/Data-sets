import pytest

from governance.policy import Resource

pytestmark = pytest.mark.critical


def client_res(st, cid):
    from governance import resources
    return resources.client(st, cid)


def test_default_deny_unknown_action(engine, P):
    d = engine.authorize(P["u-advisor"], "aiops:manage")
    assert not d.allowed and d.denial_codes == ["RBAC-DENY-DEFAULT"]


def test_unauthenticated_denied(engine):
    assert not engine.authorize(None, "ask:use").allowed


@pytest.mark.parametrize("user", ["u-ceo", "u-cio", "u-advisor", "u-compliance", "u-aiadmin"])
def test_trading_prohibited_for_everyone(engine, P, user):
    d = engine.authorize(P[user], "trade:execute")
    assert not d.allowed and d.denial_codes == ["PROHIBITED-ACTION"]


def test_advisor_assigned_client_allowed(engine, P, st, a001_client):
    assert engine.authorize(P["u-advisor"], "client:read", client_res(st, a001_client)).allowed


def test_advisor_unassigned_client_denied(engine, P, st, other_client):
    d = engine.authorize(P["u-advisor"], "client:read", client_res(st, other_client))
    assert not d.allowed and "ABAC-CLIENT-ASSIGNMENT" in d.denial_codes


def test_cross_tenant_denied(engine, P, st, nw_client):
    d = engine.authorize(P["u-advisor"], "client:read", client_res(st, nw_client))
    assert not d.allowed and d.denial_codes == ["TENANT-ISOLATION"]


def test_unknown_client_denied_like_cross_tenant(engine, P, st):
    d = engine.authorize(P["u-advisor"], "client:read", client_res(st, "C-99999"))
    assert d.denial_codes == ["TENANT-ISOLATION"]


def test_external_advisor_no_client_records(engine, P, st, a001_client):
    d = engine.authorize(P["u-external"], "client:read", client_res(st, a001_client))
    assert not d.allowed and d.denial_codes == ["RBAC-DENY-DEFAULT"]
    assert engine.authorize(P["u-external"], "product_research:read").allowed


def test_executive_has_no_identifiable_client_access(engine, P, st, a001_client):
    assert not engine.authorize(P["u-ceo"], "client:read", client_res(st, a001_client)).allowed


def test_compliance_requires_recorded_purpose(engine, P, st, a001_client):
    r = client_res(st, a001_client)
    assert not engine.authorize(P["u-compliance"], "client:read", r).allowed
    assert engine.authorize(P["u-compliance"], "client:read", r, {"purpose": "compliance_review"}).allowed
    assert not engine.authorize(P["u-compliance"], "client:read", r, {"purpose": "curiosity"}).allowed


def test_classification_clearance(engine, P):
    restricted = Resource("document", "D", "t-flo", {"classification": "restricted"})
    assert not engine.authorize(P["u-advisor"], "docs:read", restricted).allowed
    assert engine.authorize(P["u-compliance"], "docs:read", restricted).allowed


def test_missing_classification_fails_closed(engine, P):
    assert not engine.authorize(P["u-advisor"], "docs:read", Resource("document", "D", "t-flo", {})).allowed


def test_approval_obligation(engine, P, st, a001_client):
    d = engine.authorize(P["u-advisor"], "comms:send", client_res(st, a001_client))
    assert d.allowed and "approval_required" in d.obligations


def test_model_residency(engine, P):
    from harness.context import RunContext  # noqa: F401
    svc = P["u-advisor"].__class__(user_id="svc", tenant_id="t-flo", roles=("orchestrator",), clearance="restricted")
    allowed = engine.allowed_regions("CA")
    for prov, cls, ok in [("bedrock-ca-central-1", "confidential", True), ("bedrock-ca-central-1", "restricted", False),
                          ("bedrock-us-east-1", "confidential", False), ("bedrock-us-east-1", "public", False),
                          ("mock-deterministic", "restricted", True)]:
        p = engine.provider(prov)
        res = Resource("model_provider", prov, "t-flo", {"region": p["region"], "allowed_classifications": p["allowed_classifications"],
                                                         "classification": "public"})
        d = engine.authorize(svc, "model:invoke", res, {"allowed_regions": allowed, "data_classification": cls})
        assert d.allowed is ok, (prov, cls, d.reasons)
    assert not engine.authorize(P["u-ceo"], "model:invoke").allowed  # humans cannot invoke models directly


def test_policy_version_is_content_addressed(engine):
    assert "+" in engine.version and len(engine.version.split("+")[1]) == 10
