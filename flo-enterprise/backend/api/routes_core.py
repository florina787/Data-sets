"""Authentication (mock IdP), role-aware navigation, governance, data catalog, audit and privacy endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from analytics.semantic import METRICS, SEMANTIC_LAYER_VERSION
from backend import runtime as R
from backend.api.deps import Ctx, authorize, current, get_store_dep, require
from backend.config import get_settings
from backend.db import models as m
from backend.db.session import get_db
from data.products import catalog
from governance import audit
from governance.audit import audit_session, verify_chain
from governance.policy import Resource
from harness.models import model_status
from observability.telemetry import get_telemetry
from privacy.detect import detect, mask_value, presidio_available

router = APIRouter()

NAV = [("executive", "Executive Command Center", ["exec:read"]), ("investment", "Investment Intelligence", ["investment:read", "investment:read_aggregate"]),
       ("scenarios", "Scenario Simulator", ["scenarios:run"]), ("wealth", "Wealth Advisor 360", ["wealth:read"]),
       ("products", "Product Research", ["product_research:read"]), ("compliance", "Regulatory & Risk", ["compliance:read"]),
       ("approvals", "Approvals", ["approvals:decide", "comms:send", "board:distribute", "export:sensitive"]),
       ("decisions", "Decision Memory", ["decisions:read"]), ("knowledge", "Knowledge Search", ["docs:read"]),
       ("aiops", "AI Operations", ["aiops:read"]), ("governance", "Governance & Audit", ["audit:read"]),
       ("privacy", "Privacy Console", ["privacy:admin", "privacy:rehydrate"]), ("data", "Data Products", [])]


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    seeded = db.get(m.SeedManifest, "dataset") is not None
    if not seeded:
        raise HTTPException(503, "database not seeded")
    return {"status": "ready", "seeded": True}


@router.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ------------------------------------------------------------------ auth (MOCK identity provider)
@router.get("/api/auth/users")
def demo_users(st=Depends(get_store_dep)):
    if get_settings().is_production:
        raise HTTPException(404)
    return {"mode": "mock-idp", "users": [{"id": u["id"], "display_name": u["display_name"], "title": u["title"], "roles": u["roles"],
                                            "tenant_id": u["tenant_id"]} for u in st.tables["users"]]}


class LoginIn(BaseModel):
    user_id: str = Field(max_length=32)


@router.post("/api/auth/login")
def login(body: LoginIn, st=Depends(get_store_dep)):
    if get_settings().is_production:
        raise HTTPException(404, "mock login disabled in production; use the enterprise IdP")
    from governance.identity import AuthError
    try:
        token, exp = R.identity_provider(st).issue(body.user_id)
    except AuthError:
        raise HTTPException(401, {"code": "AUTHN-INVALID", "message": "unknown user"}) from None
    u = st.idx["user"][body.user_id]
    audit.record(tenant_id=u["tenant_id"], actor=u["id"], action="auth.login", resource_type="session", resource_id=u["id"], decision="allow",
                 details={"idp": "mock"})
    return {"access_token": token, "token_type": "bearer", "expires_at": exp}


@router.get("/api/me")
def me(ctx: Ctx = Depends(current)):
    eng = R.engine()
    perms = sorted(eng.permissions(ctx.principal))
    nav = [{"id": i, "label": label} for i, label, need in NAV if not need or any(eng.authorize(ctx.principal, n).allowed for n in need)]
    p = ctx.principal
    return {"user_id": p.user_id, "display_name": p.display_name, "title": p.title, "tenant_id": p.tenant_id, "roles": list(p.roles),
            "advisor_id": p.advisor_id, "clearance": p.clearance, "business_unit": p.business_unit, "permissions": perms, "navigation": nav,
            "data_as_of": ctx.store.idx["months"][-1].isoformat(), "dataset_version": ctx.store.version}


# ------------------------------------------------------------------ governance
@router.get("/api/governance/status")
def gov_status(ctx: Ctx = Depends(current)):
    s = get_settings()
    eng = R.engine()
    return {"policy_version": eng.version, "pdp": "opa" if s.opa_url else "embedded (OPA-parity tested)", "deny_by_default": True,
            "observability": get_telemetry().mode, "model_provider": s.model_provider if s.model_provider != "mock" else "mock-deterministic (in-process)",
            "model": model_status(),
            "identity_provider": "mock-idp (synthetic users)", "integrations": "mock-synthetic adapters (not connected to any production system)",
            "audit_chain": verify_chain() if "audit:read" in eng.permissions(ctx.principal) else "requires audit:read",
            "presidio": presidio_available(), "trading": "prohibited", "data": "synthetic"}


@router.get("/api/governance/policies")
def policies(ctx: Ctx = Depends(current)):
    b = R.engine().bundle
    return {"version": b.version, "rbac": b.rbac, "abac": b.abac, "approvals": b.approvals, "providers": b.providers, "suitability": b.suitability,
            "retention": b.retention}


class CheckIn(BaseModel):
    action: str = Field(max_length=60)
    resource_ref: str | None = Field(None, max_length=80)
    purpose: str | None = None


@router.post("/api/governance/check")
def check(body: CheckIn, ctx: Ctx = Depends(current)):
    """Explain an authorization decision for the CURRENT user (cannot be used to evaluate other identities)."""
    from governance import resources
    res = resources.from_ref(ctx.store, ctx.principal.tenant_id, body.resource_ref) if body.resource_ref else None
    return R.engine().authorize(ctx.principal, body.action, res, {"purpose": body.purpose}).as_dict()


# ------------------------------------------------------------------ data catalog
@router.get("/api/data/products")
def data_products(ctx: Ctx = Depends(current)):
    return catalog(ctx.store)


@router.get("/api/data/metrics")
def semantic_metrics(ctx: Ctx = Depends(current)):
    return {"version": SEMANTIC_LAYER_VERSION, "metrics": [vars(x) for x in METRICS.values()]}


@router.get("/api/integrations")
def integrations(ctx: Ctx = Depends(current)):
    return {"adapters": ctx.adapters.catalog(), "statement": "All adapters are mock implementations backed by synthetic data."}


# ------------------------------------------------------------------ audit
@router.get("/api/audit/events")
def audit_events(action: str | None = None, decision: str | None = None, actor: str | None = None, limit: int = Query(200, le=1000),
                 ctx: Ctx = Depends(require("audit:read"))):
    with audit_session() as s:
        q = select(m.AuditEvent).where(m.AuditEvent.tenant_id == ctx.principal.tenant_id)
        if action:
            q = q.where(m.AuditEvent.action.like(f"{action}%"))
        if decision:
            q = q.where(m.AuditEvent.decision == decision)
        if actor:
            q = q.where(m.AuditEvent.actor == actor)
        rows = list(s.scalars(q.order_by(m.AuditEvent.seq.desc()).limit(limit)))
        return {"events": [{"seq": e.seq, "id": e.id, "ts": e.ts.isoformat(), "actor": e.actor, "action": e.action, "resource_type": e.resource_type,
                            "resource_id": e.resource_id, "decision": e.decision, "reasons": e.reasons, "policy_version": e.policy_version,
                            "details": e.details, "hash": e.hash[:16]} for e in rows]}


@router.get("/api/audit/verify")
def audit_verify(ctx: Ctx = Depends(require("audit:read"))):
    return verify_chain()


# ------------------------------------------------------------------ privacy
class TextIn(BaseModel):
    text: str = Field(max_length=20000)
    scope: str | None = Field(None, max_length=60)
    purpose: str | None = Field(None, max_length=40)


@router.post("/api/privacy/scan")
def privacy_scan(body: TextIn, ctx: Ctx = Depends(require("ask:use"))):
    f = detect(body.text)
    return {"findings": [{"type": x.type, "start": x.start, "end": x.end, "masked": mask_value(x.type, x.text), "recognizer": x.recognizer,
                          "score": x.score} for x in f], "presidio": presidio_available()}


@router.post("/api/privacy/tokenize")
def privacy_tokenize(body: TextIn, ctx: Ctx = Depends(require("ask:use"))):
    scope = body.scope or f"user:{ctx.principal.user_id}"
    if not scope.startswith(f"user:{ctx.principal.user_id}") and not scope.startswith("WF-"):
        raise HTTPException(403, "scope not owned by caller")
    out = R.privacy_service(ctx.store).tokenize(ctx.db, body.text, ctx.principal.tenant_id, scope, purpose="user_request", mask_amounts=False)
    return {"text": out.text, "scope": scope, "entities": out.entity_counts}


@router.post("/api/privacy/rehydrate")
def privacy_rehydrate(body: TextIn, ctx: Ctx = Depends(current)):
    authorize(ctx, "privacy:rehydrate")
    if not body.scope:
        raise HTTPException(422, "scope required")
    return R.privacy_service(ctx.store).rehydrate(ctx.db, body.text, ctx.principal, body.scope, body.purpose)


@router.get("/api/privacy/reveal/{client_id}/{field}")
def reveal(client_id: str, field: str, purpose: str | None = None, ctx: Ctx = Depends(current)):
    """Reveal one masked contact identifier for an authorized principal (audited)."""
    from governance import resources
    if field not in ("email", "phone", "account_number"):
        raise HTTPException(422, "field not revealable")
    authorize(ctx, "privacy:rehydrate", resources.client(ctx.store, client_id), {"purpose": purpose}, audit_allow=True)
    return {"client_id": client_id, "field": field, "value": ctx.store.idx["client"][client_id][field]}


class EraseIn(BaseModel):
    entity_type: str = Field(pattern="^(PERSON|EMAIL|PHONE|SIN|ACCOUNT|CLIENT_ID|DOB|ADDRESS|POSTAL_CODE)$")
    value: str = Field(max_length=200)


@router.post("/api/privacy/erase")
def privacy_erase(body: EraseIn, ctx: Ctx = Depends(require("privacy:admin"))):
    n = R.privacy_service(ctx.store).vault.erase_subject(ctx.db, ctx.principal.tenant_id, body.entity_type, body.value)
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="privacy.erase", resource_type="token_vault",
                 resource_id=body.entity_type, decision="allow", details={"mappings_erased": n})
    return {"mappings_erased": n}


@router.post("/api/privacy/purge-expired")
def privacy_purge(ctx: Ctx = Depends(require("privacy:admin"))):
    n = R.privacy_service(ctx.store).vault.purge_expired(ctx.db)
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="privacy.purge", resource_type="token_vault",
                 resource_id="expired", decision="allow", details={"purged": n})
    return {"purged": n}


_ = Resource
