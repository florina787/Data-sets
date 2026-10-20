"""Request dependencies: authentication, authorization (deny by default, audited) and permission-aware caching."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend import runtime as R
from backend.db.session import get_db
from governance import audit
from governance.identity import AuthError, Principal
from governance.policy import Resource
from harness.resilience import TTLCache
from integrations.mock.adapters import Adapters
from integrations.mock.store import SyntheticStore

response_cache = TTLCache(ttl_s=120, max_items=5000)


@dataclass
class Ctx:
    principal: Principal
    store: SyntheticStore
    db: Session

    @property
    def adapters(self) -> Adapters:
        return Adapters(self.store, self.principal.tenant_id)


def get_store_dep(db: Session = Depends(get_db)) -> SyntheticStore:
    return R.store(db)


def current(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Ctx:
    st = R.store(db)
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, {"code": "AUTHN-REQUIRED", "message": "missing bearer token"})
    try:
        p = R.identity_provider(st).authenticate(authorization[7:])
    except AuthError as e:
        raise HTTPException(401, {"code": "AUTHN-INVALID", "message": str(e)}) from e
    return Ctx(p, st, db)


def authorize(ctx: Ctx, action: str, resource: Resource | None = None, context: dict | None = None, audit_allow: bool = False):
    d = R.engine().authorize(ctx.principal, action, resource, context)
    if not d.allowed:
        audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action=action,
                     resource_type=resource.type if resource else "-", resource_id=resource.id if resource else "-", decision="deny",
                     reasons=d.reasons, policy_version=d.policy_version, details={"context": context or {}})
        raise HTTPException(403, {"code": "POLICY-DENIED", "action": action, "denials": d.denial_codes, "policy_version": d.policy_version})
    if audit_allow:
        audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action=action,
                     resource_type=resource.type if resource else "-", resource_id=resource.id if resource else "-", decision="allow",
                     reasons=d.reasons[-1:], policy_version=d.policy_version)
    return d


def require(action: str):
    def dep(ctx: Ctx = Depends(current)) -> Ctx:
        authorize(ctx, action)
        return ctx
    return dep


def cached(ctx: Ctx, request: Request, fn):
    """Cache keyed by tenant + data version + path + query. Authorization is always evaluated BEFORE this lookup, and
    only tenant-wide aggregate endpoints (no per-user record filtering) use it."""
    key = hashlib.sha256(json.dumps([ctx.principal.tenant_id, ctx.store.version, request.url.path, sorted(request.query_params.multi_items())]).encode()).hexdigest()
    hit = response_cache.get(key)
    if hit is not None:
        return hit
    val = fn()
    response_cache.put(key, val)
    return val
