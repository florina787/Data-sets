"""Construction of per-request runtime objects (adapters, run context, services)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from approvals.service import ApprovalService
from governance import resources
from governance.identity import MockIdentityProvider, Principal
from governance.policy import PolicyEngine, get_policy_engine
from harness.context import RunContext
from harness.models import ModelAdapter, default_model
from harness.tools import ToolGateway
from integrations.mock.adapters import Adapters
from integrations.mock.store import SyntheticStore, get_store
from privacy.detect import register_names
from privacy.service import PrivacyService

_gateway = ToolGateway()
_registered_version: str | None = None


def engine() -> PolicyEngine:
    from backend.config import get_settings
    s = get_settings()
    if s.opa_url:
        return _opa(s.opa_url)
    return get_policy_engine()


_opa_engine = None


def _opa(url):
    global _opa_engine
    if _opa_engine is None:
        from governance.opa import OpaPolicyEngine
        _opa_engine = OpaPolicyEngine(url)
    return _opa_engine


def store(s: Session) -> SyntheticStore:
    global _registered_version
    st = get_store(s)
    if _registered_version != st.version:
        from collections import Counter
        counts = Counter(c["full_name"] for c in st.tables["clients"])
        # ambiguous names (shared by several clients) are never linked to a client id
        register_names([c["full_name"] for c in st.tables["clients"]] + [a["name"] for a in st.tables["advisors"]],
                       {c["full_name"]: c["id"] for c in st.tables["clients"] if counts[c["full_name"]] == 1})
        _registered_version = st.version
    return st


def identity_provider(st: SyntheticStore) -> MockIdentityProvider:
    return MockIdentityProvider(st.idx["user"])


def run_context(st: SyntheticStore, principal: Principal, workflow_type: str = "ask", model: ModelAdapter | None = None,
                purpose: str | None = None) -> RunContext:
    ctx = RunContext(principal=principal, adapters=Adapters(st, principal.tenant_id), engine=engine(), model=model or default_model(),
                     workflow_type=workflow_type, purpose=purpose)
    ctx.gateway = _gateway
    return ctx


def approval_service(st: SyntheticStore) -> ApprovalService:
    return ApprovalService(engine(), lambda tid, ref: resources.from_ref(st, tid, ref))


def privacy_service(st: SyntheticStore) -> PrivacyService:
    def resolve(cid):
        c = st.idx["client"].get(cid)
        return {"advisor_id": c["advisor_id"], "tenant_id": c["tenant_id"]} if c else None
    return PrivacyService(engine(), resolve)


def principal_for(st: SyntheticStore, user_id: str) -> Principal:
    u = st.idx["user"][user_id]
    return Principal(user_id=u["id"], tenant_id=u["tenant_id"], roles=tuple(u["roles"]), display_name=u["display_name"], title=u["title"],
                     advisor_id=u["advisor_id"], clearance=u["clearance"], business_unit=u["business_unit"], region=u["region"])
