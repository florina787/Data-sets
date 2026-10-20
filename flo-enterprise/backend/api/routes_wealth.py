"""Wealth Advisor 360, approvals and the durable client-communication workflow."""
from __future__ import annotations


from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import agents.tools as T
from analytics import service as S
from analytics import wealth as W
from analytics.money import from_cents
from approvals.service import ApprovalError, list_by_status, to_dict
from backend import runtime as R
from backend.api.deps import Ctx, authorize, current, require
from governance import resources

router = APIRouter(prefix="/api")


def _advisor_clients(ctx: Ctx) -> list[dict]:
    if not ctx.principal.advisor_id:
        return []
    return [c for c in ctx.adapters.crm.clients(ctx.principal.advisor_id)]


@router.get("/wealth/home")
def advisor_home(ctx: Ctx = Depends(require("wealth:read"))):
    a = ctx.adapters
    clients = _advisor_clients(ctx)
    as_of = a.market.months()[-1]
    book = a.advisor_analytics.book_summary(ctx.principal.advisor_id) if ctx.principal.advisor_id else {"active_clients": 0, "book_aum_cents": 0}
    rules = R.engine().bundle.suitability
    kyc_due = [c for c in clients if c["status"] == "active" and (as_of - c["kyc_last_review"]).days > rules["kyc_max_age_days"] - 60]
    inter = [i for c in clients for i in a.crm.interactions(c["id"])]
    follow = sorted([i for i in inter if i["follow_up_required"]], key=lambda i: i["ts"], reverse=True)[:10]
    seg: dict[str, int] = {}
    for c in clients:
        if c["status"] == "active":
            seg[c["segment"]] = seg.get(c["segment"], 0) + 1
    return {"advisor_id": ctx.principal.advisor_id, "as_of": as_of.isoformat(), "active_clients": book["active_clients"],
            "book_aum": float(from_cents(book["book_aum_cents"])), "segments": seg,
            "kyc_due": [{"client_id": c["id"], "name": c["full_name"], "kyc_last_review": c["kyc_last_review"].isoformat(),
                         "days": (as_of - c["kyc_last_review"]).days} for c in kyc_due][:15],
            "follow_ups": [{"client_id": i["client_id"], "name": ctx.store.idx["client"][i["client_id"]]["full_name"], "topic": i["topic"],
                            "ts": i["ts"].isoformat(), "channel": i["channel"]} for i in follow],
            "sentiment": {s: sum(1 for i in inter if i["sentiment"] == s) for s in ("positive", "neutral", "negative")}}


@router.get("/wealth/clients")
def client_directory(q: str | None = None, ctx: Ctx = Depends(require("wealth:read"))):
    """Directory of the advisor's assigned clients only (resource-level authorization applied per client)."""
    out = []
    eng = R.engine()
    for c in _advisor_clients(ctx):
        if not eng.authorize(ctx.principal, "client:read", resources.client(ctx.store, c["id"])).allowed:
            continue
        if q and q.lower() not in c["full_name"].lower() and q.upper() not in c["id"]:
            continue
        pos = sum(p["market_value_cents"] for p in ctx.adapters.crm.positions(c["id"]))
        pfs = ctx.adapters.crm.portfolios_for(c["id"])
        mv = pos + sum(ctx.adapters.portfolio.valuations(p["id"])[-1]["mv_close_cents"] for p in pfs)
        out.append({"id": c["id"], "name": c["full_name"], "segment": c["segment"], "risk_profile": c["risk_profile"], "status": c["status"],
                    "language": c["language"], "city": c["city"], "province": c["province"], "assets_with_flo": float(from_cents(mv)),
                    "portfolios": len(pfs), "kyc_last_review": c["kyc_last_review"].isoformat()})
    return {"clients": sorted(out, key=lambda x: -x["assets_with_flo"]), "count": len(out)}


@router.get("/wealth/clients/{client_id}")
def client_360(client_id: str, ctx: Ctx = Depends(current)):
    authorize(ctx, "client:read", resources.client(ctx.store, client_id), audit_allow=True)
    rctx = R.run_context(ctx.store, ctx.principal)

    class A:  # minimal arg object for reuse of tool handlers (authorization already enforced above)
        pass
    a = A()
    a.client_id = client_id
    profile = T._client_profile(rctx, a)
    ports = T._client_portfolios(rctx, a)["portfolios"]
    goals = T._goals(rctx, a)
    inter = T._interactions(rctx, a)["interactions"]
    suit = T._suitability(rctx, a)
    cl = ctx.adapters.crm.client(client_id)
    masked = {"email": cl["email"][0] + "***@" + cl["email"].split("@")[1], "phone": "***-***-" + cl["phone"][-4:],
              "account_number": "*****" + cl["account_number"][-4:], "sin": "*** *** " + cl["sin"][-3:]}
    timeline = sorted(inter, key=lambda x: x["ts"])
    return {"profile": profile, "contact_masked": masked, "portfolios": ports, "goals": goals, "interactions": inter, "timeline": timeline,
            "suitability": suit, "as_of": ctx.adapters.market.months()[-1].isoformat(),
            "note": "Contact identifiers are masked; reveal requires privacy:rehydrate and is audited."}


@router.get("/wealth/clients/{client_id}/retirement")
def retirement(client_id: str, expected_return: float | None = Query(None, ge=-0.05, le=0.15), monthly_contribution: float | None = Query(None, ge=0, le=1e6),
               retirement_age: int = Query(65, ge=40, le=80), retirement_years: int = Query(25, ge=5, le=45), ctx: Ctx = Depends(current)):
    authorize(ctx, "retirement:run", resources.client(ctx.store, client_id))
    rctx = R.run_context(ctx.store, ctx.principal)

    class A:
        pass
    a = A()
    a.client_id = client_id
    base = T._retirement(rctx, a)
    rules = R.engine().bundle.suitability
    cl = ctx.adapters.crm.client(client_id)
    er = expected_return if expected_return is not None else rules["expected_returns"][cl["risk_profile"]]
    mc = Decimal(str(monthly_contribution)) if monthly_contribution is not None else Decimal(str(base["monthly_contribution"]))
    proj = W.retirement_projection(Decimal(str(base["current_savings"])), mc, max(0, retirement_age - base["age"]), er,
                                   rules["inflation_assumption"], retirement_years)
    return T._j({**base, **proj, "inputs": {"expected_return": er, "monthly_contribution": mc, "retirement_age": retirement_age,
                                            "retirement_years": retirement_years, "source": "advisor what-if" if expected_return or monthly_contribution else "approved defaults"}})


@router.get("/wealth/products/compare")
def compare_products(ids: str = Query(..., max_length=200), amount: float = Query(100000, gt=0, le=1e8), years: int = Query(10, ge=1, le=40),
                     ctx: Ctx = Depends(require("product_research:read"))):
    funds = {f["id"]: f for f in S.fund_list(ctx.adapters)["data"]["funds"]}
    out = []
    for pid in ids.split(",")[:6]:
        f = funds.get(pid.strip())
        if not f:
            continue
        from analytics.revenue import fee_impact
        imp = fee_impact(Decimal(str(amount)), Decimal("0.06"), f["fee_bps"], years)
        out.append({**f, "fee_impact": {k: float(v) for k, v in imp.items()}})
    return {"products": out, "assumptions": {"gross_return": 0.06, "amount": amount, "years": years},
            "note": "General product information; not a recommendation for any client."}


# ------------------------------------------------------------------ approvals
class ApprovalIn(BaseModel):
    action: str = Field(pattern="^(comms:send|recommendation:deliver|export:sensitive|board:distribute|records:change|portfolio:modify)$")
    resource_ref: str = Field(max_length=80)
    payload: dict
    evidence: list = []


class DecideIn(BaseModel):
    approve: bool
    payload_hash: str = Field(min_length=64, max_length=64)
    note: str = Field("", max_length=1000)


class ExecuteIn(BaseModel):
    payload: dict


def _approval_error(e: ApprovalError):
    return JSONResponse(status_code=409 if e.code not in ("NOT_FOUND",) else 404, content={"detail": {"code": e.code, "message": str(e)}})


@router.get("/approvals")
def approvals(status: str | None = None, ctx: Ctx = Depends(current)):
    rows = list_by_status(ctx.db, ctx.principal.tenant_id, status)
    roles = set(ctx.principal.roles)
    visible = [a for a in rows if a.requested_by == ctx.principal.user_id or roles & set(a.approver_role.split(","))]
    return {"approvals": [to_dict(a) for a in visible]}


@router.get("/approvals/{approval_id}")
def approval(approval_id: str, ctx: Ctx = Depends(current)):
    svc = R.approval_service(ctx.store)
    try:
        a = svc.get(ctx.db, ctx.principal, approval_id)
    except ApprovalError as e:
        return _approval_error(e)
    if a.requested_by != ctx.principal.user_id and not set(ctx.principal.roles) & set(a.approver_role.split(",")):
        raise HTTPException(404, "not found")
    return to_dict(a)


@router.post("/approvals")
def request_approval(body: ApprovalIn, ctx: Ctx = Depends(current)):
    svc = R.approval_service(ctx.store)
    if body.action == "export:sensitive":
        body.payload = _sensitive_export_payload(ctx, body.resource_ref, body.payload)
    try:
        a = svc.request(ctx.db, ctx.principal, body.action, body.resource_ref, body.payload, body.evidence)
    except ApprovalError as e:
        return _approval_error(e)
    return to_dict(a)


def _sensitive_export_payload(ctx: Ctx, ref: str, payload: dict) -> dict:
    """Server-side construction of the export rows so the approver reviews exactly what will be exported."""
    kind, _, cid = ref.partition(":")
    if kind != "client":
        raise HTTPException(422, "sensitive exports are per client")
    authorize(ctx, "client:read", resources.client(ctx.store, cid))
    c = ctx.adapters.crm.client(cid)
    prods = {p["id"]: p for p in ctx.adapters.accounting.products()}
    rows = [{"client_id": cid, "client_name": c["full_name"], "product": prods[p["product_id"]]["name"],
             "market_value": str(from_cents(p["market_value_cents"]))} for p in ctx.adapters.crm.positions(cid)]
    return {"purpose": payload.get("purpose", "client statement request"), "rows": rows, "fields": ["client_id", "client_name", "product", "market_value"]}


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: str, body: DecideIn, ctx: Ctx = Depends(current)):
    svc = R.approval_service(ctx.store)
    try:
        a = svc.decide(ctx.db, ctx.principal, approval_id, body.approve, body.payload_hash, body.note)
    except ApprovalError as e:
        return _approval_error(e)
    return to_dict(a)


@router.post("/approvals/{approval_id}/execute")
def execute(approval_id: str, body: ExecuteIn, ctx: Ctx = Depends(current)):
    svc = R.approval_service(ctx.store)
    try:
        a = svc.execute(ctx.db, ctx.principal, approval_id, body.payload)
    except ApprovalError as e:
        return _approval_error(e)
    return to_dict(a)


# ------------------------------------------------------------------ durable communication workflow (LangGraph interrupt)
class CommsIn(BaseModel):
    client_id: str = Field(pattern=r"^C-\d{5}$")
    language: str = Field("en", pattern="^(en|fr|es|hi|ta|ko)$")


class ResumeIn(BaseModel):
    payload: dict | None = None


@router.post("/workflows/communication")
def start_comms(body: CommsIn, ctx: Ctx = Depends(current)):
    from agents.graph import start_communication
    from harness.errors import HarnessError
    authorize(ctx, "comms:draft", resources.client(ctx.store, body.client_id))
    try:
        return T._j(start_communication(R.run_context(ctx.store, ctx.principal, "communication"), body.client_id, body.language))
    except HarnessError as e:
        raise HTTPException(403 if "denied" in e.failure_class or "not_allow" in e.failure_class else 422,
                            {"code": e.code, "failure_class": e.failure_class, "message": str(e)}) from e
    except ApprovalError as e:
        return _approval_error(e)


@router.post("/workflows/communication/{thread_id}/resume")
def resume_comms(thread_id: str, body: ResumeIn, ctx: Ctx = Depends(current)):
    from agents.graph import resume_communication
    try:
        return T._j(resume_communication(R.run_context(ctx.store, ctx.principal, "communication"), thread_id, body.payload))
    except PermissionError:
        raise HTTPException(404, "workflow not found") from None


