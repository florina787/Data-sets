"""FLO Bank - Sherin AI 3.0 API."""
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app import catalog as C
from app import models as M
from app.agents import harness as H
from app.agents import llm
from app.approvals import service as approvals
from app.audit import audit
from app.config import get_settings
from app.copilot import service as copilot
from app.db import create_all, get_session, session_scope
from app.finance import engine as E
from app.guardian import engine as G
from app.observability import telemetry as OT

log = logging.getLogger("sherin.api")
OT.setup_logging()
tracer = OT.setup_tracing()

@asynccontextmanager
async def lifespan(_app):
    _startup()
    yield


app = FastAPI(title="FLO Bank - Sherin AI 3.0", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])

ALLOWED_UPLOAD_EXT = (".py", ".yml", ".yaml", ".log", ".txt", ".json", ".bicep", ".tf", ".csv", ".md")
MAX_UPLOAD_BYTES = 200_000


@app.middleware("http")
async def telemetry_mw(request: Request, call_next):
    t0 = time.perf_counter()
    route = request.url.path
    with tracer.start_as_current_span(f"{request.method} {route}") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", route)
        try:
            resp = await call_next(request)
        except Exception:
            OT.STORE.add_request(route, request.method, 500, (time.perf_counter() - t0) * 1000)
            raise
        ms = (time.perf_counter() - t0) * 1000
        span.set_attribute("http.status_code", resp.status_code)
        OT.STORE.add_request(route, request.method, resp.status_code, ms)
        if route.startswith("/api"):
            log.info("request", extra={"route": route, "status": resp.status_code, "duration_ms": round(ms, 1)})
        return resp


def _startup():
    create_all()
    with session_scope() as db:
        if get_settings().app_mode == "demo" and not db.scalar(select(func.count()).select_from(M.LedgerLine)):
            from app.data.seed import seed
            log.info("seeding synthetic demo data")
            seed()


@app.exception_handler(approvals.ApprovalError)
async def _approval_err(_, exc: approvals.ApprovalError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def _value_err(_, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------------------------- identity (demo)
class Identity(BaseModel):
    user: str
    role: str


def identity(x_user: str = Header("exec.demo"), x_role: str = Header("SHERIN_MANAGER")) -> Identity:
    """Demo identity from headers. Replace with Entra ID (OIDC) in production; see docs/STATUS.md."""
    if x_role not in approvals.ROLES:
        raise HTTPException(403, f"Unknown role {x_role}")
    return Identity(user=x_user, role=x_role)


def require(*roles):
    def dep(me: Identity = Depends(identity)) -> Identity:
        if me.role not in roles:
            raise HTTPException(403, f"Role {me.role} cannot perform this action (requires {', '.join(roles)})")
        return me
    return dep


# ---------------------------------------------------------------------------------------------- common params
class Q:
    def __init__(self, period: str = Query("month"), value: str | None = Query(None), start: str | None = None, end: str | None = None,
                 currency: str = Query("USD"), dc: str = Query("synthetic")):
        if dc not in ("synthetic", "measured"):
            raise HTTPException(400, "dc must be 'synthetic' or 'measured'")
        self.p = E.resolve_period(period, value, start, end, default_month=get_settings().demo_end_month)
        self.currency, self.dc = currency, dc


def fx(db: Session, q: Q) -> E.Fx:
    return E.fx_for(db, q.currency)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/meta")
def meta(db: Session = Depends(get_session)):
    s = get_settings()
    return {"app": "FLO Bank - Sherin AI 3.0", "mode": s.app_mode, "default_month": s.demo_end_month,
            "bounds": {"synthetic": E.data_bounds(db, "synthetic"), "measured": E.data_bounds(db, "measured")},
            "currencies": list(E.SUPPORTED_CURRENCIES), "roles": approvals.ROLES, "llm": llm.status(),
            "agents": [{"id": k, "label": v["label"], "workflow": v["workflow"], "tools": v["tools"]} for k, v in C.AGENTS.items()],
            "departments": C.DEPARTMENTS, "ai_cost_categories": C.AI_COST_CATEGORIES, "definitions": E.DEFINITIONS,
            "suggestions": copilot.SUGGESTIONS, "database": "postgresql" if s.database_url.startswith("postgres") else "sqlite"}


# ---------------------------------------------------------------------------------------------- finance
@app.get("/api/finance/kpis")
def kpis(q: Q = Depends(), db: Session = Depends(get_session)):
    return E.kpis(db, q.p, fx(db, q), q.dc)


@app.get("/api/finance/kpis/{key}")
def kpi_drill(key: str, q: Q = Depends(), db: Session = Depends(get_session)):
    try:
        return E.kpi_drilldown(db, key, q.p, fx(db, q), q.dc)
    except KeyError:
        raise HTTPException(404, f"Unknown KPI {key}")


@app.get("/api/finance/revenue-expenditure")
def rev_exp(granularity: str = "month", q: Q = Depends(), db: Session = Depends(get_session)):
    return E.revenue_vs_expenditure(db, q.p, granularity, fx(db, q), q.dc)


@app.get("/api/finance/contribution")
def contribution(q: Q = Depends(), db: Session = Depends(get_session)):
    return E.contribution(db, q.p, fx(db, q), q.dc)


@app.get("/api/finance/human-vs-ai")
def human_vs_ai(q: Q = Depends(), db: Session = Depends(get_session)):
    return E.human_vs_ai(db, q.p, fx(db, q), q.dc)


@app.get("/api/finance/ai-costs")
def ai_costs(q: Q = Depends(), db: Session = Depends(get_session)):
    return E.ai_cost_breakdown(db, q.p, fx(db, q), q.dc)


@app.get("/api/finance/ai-costs/{category}/records")
def ai_cost_records(category: str, limit: int = Query(100, le=500), offset: int = 0, q: Q = Depends(), db: Session = Depends(get_session)):
    try:
        return E.cost_records(db, q.p, category, fx(db, q), q.dc, limit, offset)
    except KeyError:
        raise HTTPException(404, f"Unknown category {category}")


@app.get("/api/finance/tokens")
def tokens(granularity: str = "day", q: Q = Depends(), db: Session = Depends(get_session)):
    return E.token_analytics(db, q.p, granularity, fx(db, q), q.dc)


@app.get("/api/finance/forecast")
def forecast(horizon: int = Query(12, ge=3, le=24), q: Q = Depends(), db: Session = Depends(get_session)):
    return E.forecast(db, q.p.end.strftime("%Y-%m"), fx(db, q), q.dc, horizon=horizon)


@app.get("/api/finance/agents")
def agents_econ(q: Q = Depends(), db: Session = Depends(get_session)):
    return E.agent_productivity(db, q.p, fx(db, q), q.dc)


@app.get("/api/finance/departments")
def departments(q: Q = Depends(), db: Session = Depends(get_session)):
    return E.department_value(db, q.p, fx(db, q), q.dc)


@app.get("/api/finance/cost-drivers")
def cost_drivers(baseline_start: str | None = None, baseline_end: str | None = None, q: Q = Depends(), db: Session = Depends(get_session)):
    base = E.Period(dt.date.fromisoformat(baseline_start), dt.date.fromisoformat(baseline_end), "custom", "baseline") if baseline_start and baseline_end else E.prior_period(q.p)
    return E.cost_drivers(db, q.p, base, fx(db, q), q.dc)


@app.get("/api/finance/reconciliation")
def reconciliation(q: Q = Depends(), db: Session = Depends(get_session)):
    """Accounting identity checks, shown in the UI so anyone can see the books tie out."""
    e = E.economics(db, q.p, q.dc)
    t = M.TokenUsage
    tok_cost = E.q(db.scalar(select(func.sum(t.api_cost_usd + t.local_compute_usd + t.local_energy_usd)).where(E._between(t.ts, q.p), t.data_class == q.dc)))
    linked_llm = E.q(db.scalar(select(func.sum(M.AiCostRecord.amount_usd)).where(M.AiCostRecord.category == "llm_inference", M.AiCostRecord.task_id.is_not(None),
                                                                              E._between(M.AiCostRecord.date, q.p), M.AiCostRecord.data_class == q.dc)))
    tk = e["tasks"]
    checks = [
        ("Net benefit identity", "incremental profit + value of verified work - total AI cost == net benefit",
         e["attribution"]["incremental_profit"] + e["value_verified"] - e["ai"]["total"], e["net_benefit"]),
        ("Workflow cost reconciles to cost ledger", "sum(task workflow costs) == sum(task-linked AI cost records)", tk.get("wf_cost_all", E.ZERO), e["ai"]["workflow_linked"]),
        ("Token cost reconciles to LLM cost", "sum(token-row costs) == task-linked LLM inference records", tok_cost, linked_llm),
        ("AI cash cost is inside bank opex", "ledger 'Technology - Sherin AI' == AI cost excluding human review", e["bank"]["ai_cash_opex"], e["ai"]["cash"]),
        ("Attributed revenue within fee income", "attributed revenue <= fees and commissions", e["attribution"]["attributed_revenue"],
         min(e["attribution"]["attributed_revenue"], e["bank"]["revenue_by_category"].get("fees_commissions", E.ZERO))),
        ("Realized savings within cost avoidance", "realized savings <= cost avoidance", e["realized_savings"], min(e["realized_savings"], e["cost_avoidance"])),
    ]
    return {"period": q.p.as_dict(), "data_class": q.dc, "checks": [{"name": n, "rule": r, "left_usd": float(a), "right_usd": float(b), "ok": E.q(a) == E.q(b)} for n, r, a, b in checks]}


# ---------------------------------------------------------------------------------------------- FX + baselines
class FxIn(BaseModel):
    quote: str
    rate: float = Field(gt=0)
    source: str = Field(min_length=3)


@app.get("/api/fx/rates")
def fx_rates(db: Session = Depends(get_session)):
    rows = db.scalars(select(M.FxRate).order_by(M.FxRate.quote, M.FxRate.as_of.desc(), M.FxRate.id.desc())).all()
    current = {}
    for r in rows:
        current.setdefault(r.quote, r)
    fmt = lambda r: {"id": r.id, "base": r.base, "quote": r.quote, "rate": float(r.rate), "source": r.source, "as_of": r.as_of.isoformat(timespec="seconds"),
                     "data_class": r.data_class, "created_by": r.created_by}
    return {"base": "USD", "current": [fmt(r) for r in current.values()], "history": [fmt(r) for r in rows]}


@app.post("/api/fx/rates")
def fx_add(body: FxIn, me: Identity = Depends(require("SHERIN_MANAGER")), db: Session = Depends(get_session)):
    if body.quote.upper() not in ("INR", "CAD"):
        raise HTTPException(400, "quote must be INR or CAD")
    r = M.FxRate(base="USD", quote=body.quote.upper(), rate=Decimal(str(body.rate)), source=body.source, as_of=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
                 data_class="measured" if "synthetic" not in body.source.lower() else "synthetic", created_by=me.user)
    db.add(r)
    audit(db, me.user, me.role, "fx.rate_set", "fx_rate", body.quote, rate=body.rate, source=body.source)
    db.flush()
    return {"id": r.id}


class BaselineIn(BaseModel):
    hours_per_task: float = Field(gt=0, le=200)
    hourly_rate_usd: float = Field(gt=0, le=2000)
    source: str = Field(min_length=3)


@app.get("/api/baselines")
def baselines(db: Session = Depends(get_session)):
    return [{"workflow_type": b.workflow_type, "department": b.department, "label": b.label, "hours_per_task": float(b.hours_per_task),
             "hourly_rate_usd": float(b.hourly_rate_usd), "source": b.source, "data_class": b.data_class, "configured_by": b.configured_by,
             "updated_at": b.updated_at.isoformat(timespec="seconds")} for b in db.scalars(select(M.HumanBaseline).order_by(M.HumanBaseline.workflow_type))]


@app.put("/api/baselines/{wf}")
def baseline_set(wf: str, body: BaselineIn, me: Identity = Depends(require("SHERIN_MANAGER")), db: Session = Depends(get_session)):
    b = db.get(M.HumanBaseline, wf)
    if not b:
        raise HTTPException(404, wf)
    old = (float(b.hours_per_task), float(b.hourly_rate_usd))
    b.hours_per_task, b.hourly_rate_usd, b.source = Decimal(str(body.hours_per_task)), Decimal(str(body.hourly_rate_usd)), body.source
    b.configured_by, b.updated_at = me.user, dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    audit(db, me.user, me.role, "baseline.updated", "human_baseline", wf, old=old, new=(body.hours_per_task, body.hourly_rate_usd))
    return {"ok": True, "note": "Applies to tasks completed after this change; historical tasks keep their baseline snapshot."}


# ---------------------------------------------------------------------------------------------- portfolios + guardian
@app.get("/api/portfolios")
def portfolios(db: Session = Depends(get_session)):
    out = []
    for p in db.scalars(select(M.Portfolio).order_by(M.Portfolio.id)):
        pos = db.scalars(select(M.Position).where(M.Position.portfolio_id == p.id)).all()
        nav = sum(float(x.market_value_usd) for x in pos)
        out.append({"id": p.id, "name": p.name, "manager": p.manager, "mandate": p.mandate, "nav_usd": round(nav, 2), "positions": len(pos), "data_class": p.data_class,
                    "note": "Assets under management are client/portfolio assets and are never counted as bank revenue."})
    return out


@app.get("/api/portfolios/{pid}")
def portfolio(pid: str, db: Session = Depends(get_session)):
    p = db.get(M.Portfolio, pid)
    if not p:
        raise HTTPException(404, pid)
    pos = db.scalars(select(M.Position).where(M.Position.portfolio_id == pid).order_by(M.Position.market_value_usd.desc())).all()
    nav = sum(float(x.market_value_usd) for x in pos)
    tx = db.scalars(select(M.PortfolioTransaction).where(M.PortfolioTransaction.portfolio_id == pid).order_by(M.PortfolioTransaction.date.desc()).limit(25)).all()
    return {"id": p.id, "name": p.name, "mandate": p.mandate, "nav_usd": round(nav, 2), "data_class": p.data_class,
            "positions": [{"issuer": x.issuer, "sector": x.sector, "asset_class": x.asset_class, "country": x.country, "market_value_usd": float(x.market_value_usd),
                           "weight_pct": round(float(x.market_value_usd) / nav * 100, 2) if nav else 0, "esg_score": float(x.esg_score) if x.esg_score is not None else None,
                           "liquidity_days": float(x.liquidity_days) if x.liquidity_days is not None else None, "rating": x.rating, "volatility": float(x.volatility)} for x in pos],
            "transactions": [{"date": t.date.isoformat(), "issuer": t.issuer, "side": t.side, "notional_usd": float(t.notional_usd)} for t in tx]}


@app.get("/api/guardian/graph")
def investment_graph(db: Session = Depends(get_session)):
    """Nodes/edges for the investment web graph: portfolios -> sectors -> issuers, plus pending proposals."""
    nodes, edges = [], []
    for p in db.scalars(select(M.Portfolio)):
        nodes.append({"id": p.id, "type": "portfolio", "label": p.name})
        sectors = {}
        for x in db.scalars(select(M.Position).where(M.Position.portfolio_id == p.id)):
            sectors[x.sector] = sectors.get(x.sector, 0) + float(x.market_value_usd)
        for s, v in sectors.items():
            sid = f"sector:{s}"
            if not any(n["id"] == sid for n in nodes):
                nodes.append({"id": sid, "type": "sector", "label": s})
            edges.append({"source": p.id, "target": sid, "value": round(v, 2)})
    for t in db.scalars(select(M.TradeProposal)):
        tid = f"proposal:{t.id}"
        nodes.append({"id": tid, "type": "proposal", "label": f"{t.id} {t.side} {t.issuer}", "decision": t.decision})
        edges.append({"source": tid, "target": t.portfolio_id, "value": float(t.notional_usd)})
        edges.append({"source": tid, "target": f"sector:{t.sector}", "value": float(t.notional_usd)})
        if not any(n["id"] == f"sector:{t.sector}" for n in nodes):
            nodes.append({"id": f"sector:{t.sector}", "type": "sector", "label": t.sector})
    return {"nodes": nodes, "edges": edges}


@app.get("/api/guardian/proposals")
def proposals(db: Session = Depends(get_session)):
    out = []
    for t in db.scalars(select(M.TradeProposal).order_by(M.TradeProposal.id)):
        r = G.evaluate(db, t)
        out.append({"id": t.id, "portfolio_id": t.portfolio_id, "issuer": t.issuer, "sector": t.sector, "asset_class": t.asset_class, "side": t.side,
                    "notional_usd": float(t.notional_usd), "rationale": t.rationale, "evidence": t.evidence, "proposed_by": t.proposed_by,
                    "decision": r["decision"], "material": r["material"], "data_class": t.data_class})
    return out


class AdvisoryIn(BaseModel):
    advisory: list[dict] = []


@app.post("/api/guardian/proposals/{pid}/evaluate")
def evaluate(pid: str, body: AdvisoryIn | None = None, me: Identity = Depends(identity), db: Session = Depends(get_session)):
    t = db.get(M.TradeProposal, pid)
    if not t:
        raise HTTPException(404, pid)
    r = G.evaluate(db, t, advisory=(body.advisory if body else None))
    t.decision, t.guardian_result = r["decision"], r
    audit(db, me.user, me.role, "guardian.evaluated", "trade_proposal", pid, decision=r["decision"])
    return r


class ProposalIn(BaseModel):
    portfolio_id: str
    issuer: str
    sector: str
    asset_class: str
    country: str = "US"
    side: str = Field(pattern="^(BUY|SELL)$")
    notional_usd: float = Field(gt=0)
    esg_score: float | None = None
    liquidity_days: float | None = None
    rating: str | None = None
    volatility: float | None = None
    rationale: str = Field(min_length=5)
    evidence: list[str] = []


@app.post("/api/guardian/proposals")
def proposal_create(body: ProposalIn, me: Identity = Depends(require("PORTFOLIO_MANAGER", "SHERIN_MANAGER")), db: Session = Depends(get_session)):
    if not db.get(M.Portfolio, body.portfolio_id):
        raise HTTPException(404, body.portfolio_id)
    pid = f"TP-{uuid.uuid4().hex[:6].upper()}"
    t = M.TradeProposal(id=pid, portfolio_id=body.portfolio_id, issuer=body.issuer, sector=body.sector, asset_class=body.asset_class, country=body.country,
                        side=body.side, notional_usd=Decimal(str(body.notional_usd)), esg_score=body.esg_score, liquidity_days=body.liquidity_days,
                        rating=body.rating, volatility=body.volatility, rationale=body.rationale, evidence=body.evidence, proposed_by=me.user, data_class="measured")
    db.add(t)
    db.flush()
    r = G.evaluate(db, t)
    t.decision, t.guardian_result = r["decision"], r
    audit(db, me.user, me.role, "proposal.created", "trade_proposal", pid, decision=r["decision"])
    return {"id": pid, "guardian": r}


@app.post("/api/guardian/proposals/{pid}/request-approval")
def proposal_request_approval(pid: str, me: Identity = Depends(require("PORTFOLIO_MANAGER", "SHERIN_MANAGER")), db: Session = Depends(get_session)):
    t = db.get(M.TradeProposal, pid)
    if not t:
        raise HTTPException(404, pid)
    r = G.evaluate(db, t)
    t.decision, t.guardian_result = r["decision"], r
    a = approvals.for_guardian(db, t, r, requested_by=me.user)
    db.flush()
    return approvals.to_dict(a)


# ---------------------------------------------------------------------------------------------- approvals
class DecisionIn(BaseModel):
    decision: str
    comment: str = ""


@app.get("/api/approvals")
def approval_list(status: str | None = None, db: Session = Depends(get_session)):
    return approvals.inbox(db, status)


@app.get("/api/approvals/{aid}")
def approval_get(aid: str, db: Session = Depends(get_session)):
    a = db.get(M.Approval, aid)
    if not a:
        raise HTTPException(404, aid)
    d = approvals.to_dict(a)
    if a.related_proposal_id:
        t = db.get(M.TradeProposal, a.related_proposal_id)
        d["guardian"] = t.guardian_result if t else None
    if a.related_run_id:
        run = db.get(M.HarnessRun, a.related_run_id)
        d["run"] = H.run_to_dict(run) if run else None
    d["audit"] = [{"ts": x.ts.isoformat(timespec="seconds"), "actor": x.actor, "role": x.role, "action": x.action, "detail": x.detail}
                  for x in db.scalars(select(M.AuditLog).where(M.AuditLog.entity_id == aid).order_by(M.AuditLog.ts))]
    return d


@app.post("/api/approvals/{aid}/decision")
def approval_decide(aid: str, body: DecisionIn, me: Identity = Depends(identity), db: Session = Depends(get_session)):
    try:
        a = approvals.decide(db, aid, actor=me.user, role=me.role, decision=body.decision, comment=body.comment)
    except KeyError:
        raise HTTPException(404, aid)
    except approvals.ApprovalError:
        db.commit()  # keep the audit record of the refused attempt
        raise
    db.flush()
    db.commit()
    H.on_approval_decided(db, a)
    return approvals.to_dict(a)


# ---------------------------------------------------------------------------------------------- harness
class Attachment(BaseModel):
    name: str
    content: str


class RunIn(BaseModel):
    request: str = Field(min_length=3, max_length=4000)
    attachments: list[Attachment] = []
    context: dict = {}


def _check_attachments(atts: list[Attachment]):
    for a in atts:
        if not a.name.lower().endswith(ALLOWED_UPLOAD_EXT):
            raise HTTPException(415, f"{a.name}: only {', '.join(ALLOWED_UPLOAD_EXT)} files are accepted")
        if len(a.content.encode()) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{a.name}: larger than {MAX_UPLOAD_BYTES // 1000} KB")


@app.get("/api/harness/graph")
def harness_graph():
    return {"nodes": H.NODES, "edges": [{"source": a, "target": b, "label": l} for a, b, l in H.EDGES],
            "agents": [{"id": k, "label": v["label"], "tools": v["tools"]} for k, v in C.AGENTS.items()]}


@app.post("/api/harness/runs")
def harness_start(body: RunIn, me: Identity = Depends(require("ENGINEER", "PORTFOLIO_MANAGER", "SHERIN_MANAGER")), db: Session = Depends(get_session)):
    _check_attachments(body.attachments)
    run_id = H.get_harness().start(body.request, me.user, [a.model_dump() for a in body.attachments], body.context)
    return {"run_id": run_id}


@app.get("/api/harness/runs")
def harness_runs(db: Session = Depends(get_session)):
    return H.list_runs(db)


@app.get("/api/harness/runs/{rid}")
def harness_run(rid: str, db: Session = Depends(get_session)):
    r = db.get(M.HarnessRun, rid)
    if not r:
        raise HTTPException(404, rid)
    return H.run_to_dict(r)


def _run_events(run: M.HarnessRun, after: int) -> list[dict]:
    out = []
    for i, t in enumerate(run.trace or []):
        if i >= after and t.get("event"):
            out.append({"seq": i, "run_id": run.id, "synthetic": False, **t})
    return out


@app.get("/api/harness/runs/{rid}/events")
def harness_events(rid: str, after: int = 0, db: Session = Depends(get_session)):
    """Typed execution events for a run (polling form)."""
    r = db.get(M.HarnessRun, rid)
    if not r:
        raise HTTPException(404, rid)
    ev = _run_events(r, after)
    return {"run_id": rid, "status": r.status, "events": ev, "next": len(r.trace or []),
            "terminal": any(e["event"] in H.TERMINAL_EVENTS for e in _run_events(r, 0))}


@app.get("/api/harness/runs/{rid}/stream")
async def harness_stream(rid: str, after: int = 0, timeout_s: float = 600):
    """Server-sent events: one `harness` event per typed execution event, then `end` once the run is terminal."""
    with session_scope() as db:
        if not db.get(M.HarnessRun, rid):
            raise HTTPException(404, rid)

    async def gen():
        seq, t0 = after, time.monotonic()
        while time.monotonic() - t0 < timeout_s:
            with session_scope() as db:
                run = db.get(M.HarnessRun, rid)
                events, nxt, status = _run_events(run, seq), len(run.trace or []), run.status
            for e in events:
                yield f"event: harness\ndata: {json.dumps(e, default=str)}\n\n"
                if e["event"] in H.TERMINAL_EVENTS:
                    yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                    return
            seq = nxt
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.3)
        yield "event: end\ndata: {\"status\": \"timeout\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/harness/agents")
def harness_agents(q: Q = Depends(), db: Session = Depends(get_session)):
    """Live agent cards: current task, status, time, tokens, cost, quality, verified work, economic contribution."""
    f = fx(db, q)
    econ = {r["agent"]: r for r in E.agent_productivity(db, q.p, f, q.dc)["rows"]}
    tok = {r["agent"]: r for r in E.token_analytics(db, q.p, "month", f, q.dc)["per_agent"]}
    running = {}
    for run in db.scalars(select(M.HarnessRun).where(M.HarnessRun.status.in_(["queued", "running", "awaiting_approval"]))):
        done = {s["step"] for s in (run.result or {}).get("steps", [])}
        for st in run.plan or []:
            if st["step"] not in done:
                running.setdefault(st["agent"], {"run_id": run.id, "objective": st["objective"], "status": "waiting" if run.status == "awaiting_approval" else "running"})
                break
    last = {}
    t = M.AgentTask
    for row in db.execute(select(t.agent, t.title, t.created_at, t.status, t.verified).where(t.data_class == q.dc, E._between(t.created_at, q.p))
                          .order_by(t.created_at.desc()).limit(400)).all():
        last.setdefault(row.agent, row)
    out = []
    for k, v in C.AGENTS.items():
        e, tk, lt = econ.get(k, {}), tok.get(k, {}), last.get(k)
        out.append({"id": k, "label": v["label"], "status": running.get(k, {}).get("status", "idle"),
                    "current_task": running.get(k, {}).get("objective") or (lt.title if lt else None), "current_run": running.get(k, {}).get("run_id"),
                    "time_hours": e.get("ai_execution_hours", 0), "tokens": tk.get("tokens", 0), "compute_cost": tk.get("cost", 0),
                    "quality_pass_rate": e.get("quality_pass_rate"), "verified_tasks": e.get("completed", 0 if k != "verification" else None),
                    "economic_contribution": e.get("net_estimated_savings"), "tools": v["tools"]})
    return {"period": q.p.as_dict(), "fx": f.as_dict(), "data_class": q.dc, "agents": out}


# ---------------------------------------------------------------------------------------------- engineering
@app.get("/api/engineering/workflows")
def eng_workflows(department: str = "azure_devops", limit: int = Query(25, le=100), q: Q = Depends(), db: Session = Depends(get_session)):
    f = fx(db, q)
    t = M.AgentTask
    rows = db.scalars(select(t).where(t.department == department, t.data_class == q.dc, E._between(t.created_at, q.p)).order_by(t.created_at.desc()).limit(limit)).all()
    out = []
    for r in rows:
        tooling = Decimal(r.cost_model) + Decimal(r.cost_compute) + Decimal(r.cost_infra) + Decimal(r.cost_tooling)
        total = tooling + Decimal(r.cost_human_review) + Decimal(r.cost_rework)
        base = Decimal(r.baseline_hours) * Decimal(r.baseline_rate_usd)
        out.append({"id": r.id, "title": r.title, "agent": C.AGENTS[r.agent]["label"], "created_at": r.created_at.isoformat(timespec="minutes"),
                    "status": r.status, "verified": r.verified, "agent_minutes": round(r.duration_s / 60, 1), "review_minutes": float(r.human_review_min),
                    "rework_minutes": float(r.rework_min), "compute_tooling_cost": f.conv(tooling), "total_cost": f.conv(total), "human_baseline": f.conv(base),
                    "data_class": r.data_class,
                    "sentence": f"{r.title}: {r.duration_s / 60:.0f} minutes of agent execution, {float(r.human_review_min + r.rework_min):.0f} minutes of human review and rework, "
                                f"and {f.currency} {f.conv(tooling):,.2f} of allocated compute and tooling cost (total {f.currency} {f.conv(total):,.2f}) vs a configured human "
                                f"baseline of {float(r.baseline_hours):g} h ({f.currency} {f.conv(base):,.2f})."})
    return {"department": department, "fx": f.as_dict(), "data_class": q.dc, "workflows": out}


@app.get("/api/engineering/incidents")
def incidents(db: Session = Depends(get_session)):
    from app.agents.tools import incidents_summary
    return incidents_summary(db, limit=25)


@app.get("/api/compliance/events")
def compliance(db: Session = Depends(get_session)):
    rows = db.scalars(select(M.ComplianceEvent).order_by(M.ComplianceEvent.date.desc()).limit(60)).all()
    from app.agents.tools import compliance_summary
    return {"summary": compliance_summary(db), "events": [{"date": r.date.isoformat(), "type": r.type, "severity": r.severity, "status": r.status,
                                                           "description": r.description, "data_class": r.data_class} for r in rows]}


# ---------------------------------------------------------------------------------------------- metrics
@app.get("/api/metrics/live")
def metrics_live():
    return OT.live_metrics()


@app.get("/api/metrics/history")
def metrics_history(q: Q = Depends(), db: Session = Depends(get_session)):
    return OT.history(db, q.p, q.dc)


@app.get("/api/metrics/alerts")
def metrics_alerts(currency: str = "USD", dc: str = "synthetic", db: Session = Depends(get_session)):
    return OT.alerts(db, get_settings().demo_end_month, E.fx_for(db, currency), dc)


@app.get("/api/audit")
def audit_log(limit: int = Query(100, le=500), db: Session = Depends(get_session)):
    return [{"ts": a.ts.isoformat(timespec="seconds"), "actor": a.actor, "role": a.role, "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
             "detail": a.detail} for a in db.scalars(select(M.AuditLog).order_by(M.AuditLog.ts.desc(), M.AuditLog.id.desc()).limit(limit))]


# ---------------------------------------------------------------------------------------------- chat
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    currency: str = "USD"
    dc: str = "synthetic"
    attachments: list[Attachment] = []


def _conv(db: Session, cid: str | None, first: str) -> M.Conversation:
    if cid:
        c = db.get(M.Conversation, cid)
        if c:
            return c
    c = M.Conversation(id=f"C-{uuid.uuid4().hex[:10]}", title=first[:80])
    db.add(c)
    db.flush()
    return c


def _chat(db: Session, body: ChatIn, me: Identity) -> tuple[M.Conversation, dict]:
    _check_attachments(body.attachments)
    conv = _conv(db, body.conversation_id, body.message)
    db.add(M.Message(conversation_id=conv.id, role="user", content=body.message,
                     payload={"attachments": [a.name for a in body.attachments]} if body.attachments else {}))
    with tracer.start_as_current_span("copilot.answer") as span:
        res = copilot.answer(db, body.message, body.currency, body.dc)
        span.set_attribute("copilot.intent", res["intent"])
    if body.attachments or res.pop("start_run", False):
        if me.role == "VIEWER":
            res["text"] = "Your role (VIEWER) cannot start agent runs."
        else:
            db.commit()  # release the write lock before the harness opens its own sessions
            rid = H.get_harness().start(body.message, me.user, [a.model_dump() for a in body.attachments])
            res["run_id"] = rid
            res["intent"] = "harness"
            res["text"] = (f"I've started agent run **{rid}** for this request"
                           + (f" with {len(body.attachments)} attachment(s)" if body.attachments else "")
                           + ". Watch the agents work in the execution graph; any state-changing action will come back here as an approval card.")
            res["links"] = [{"label": "Open Agent Harness", "route": f"/harness?run={rid}"}]
    conv.updated_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    msg = M.Message(conversation_id=conv.id, role="assistant", content=res["text"], payload={k: v for k, v in res.items() if k != "text"})
    db.add(msg)
    db.flush()
    res["conversation_id"] = conv.id
    res["message_id"] = msg.id
    return conv, res


@app.post("/api/chat")
def chat(body: ChatIn, me: Identity = Depends(identity), db: Session = Depends(get_session)):
    _, res = _chat(db, body, me)
    return res


@app.post("/api/chat/stream")
async def chat_stream(body: ChatIn, me: Identity = Depends(identity)):
    """Server-sent events: activity steps, then text deltas, then the full structured payload."""
    with session_scope() as db:
        _, res = _chat(db, body, me)

    async def gen():
        for a in res.get("activity", []):
            yield f"event: activity\ndata: {json.dumps(a)}\n\n"
            await asyncio.sleep(0.04)
        text = res["text"]
        for i in range(0, len(text), 24):
            yield f"event: delta\ndata: {json.dumps(text[i:i + 24])}\n\n"
            await asyncio.sleep(0.008)
        yield f"event: final\ndata: {json.dumps(res, default=str)}\n\n"
        yield "event: done\ndata: {}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/conversations")
def conversations(q: str | None = None, db: Session = Depends(get_session)):
    stmt = select(M.Conversation).order_by(M.Conversation.updated_at.desc()).limit(100)
    if q:
        ids = select(M.Message.conversation_id).where(M.Message.content.ilike(f"%{q}%"))
        stmt = stmt.where(or_(M.Conversation.title.ilike(f"%{q}%"), M.Conversation.id.in_(ids)))
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat(timespec="seconds")} for c in db.scalars(stmt)]


@app.get("/api/conversations/{cid}")
def conversation(cid: str, db: Session = Depends(get_session)):
    c = db.get(M.Conversation, cid)
    if not c:
        raise HTTPException(404, cid)
    msgs = db.scalars(select(M.Message).where(M.Message.conversation_id == cid).order_by(M.Message.id)).all()
    return {"id": c.id, "title": c.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "payload": m.payload,
                                                        "created_at": m.created_at.isoformat(timespec="seconds")} for m in msgs]}


@app.delete("/api/conversations/{cid}")
def conversation_delete(cid: str, db: Session = Depends(get_session)):
    c = db.get(M.Conversation, cid)
    if not c:
        raise HTTPException(404, cid)
    db.execute(delete(M.Message).where(M.Message.conversation_id == cid))
    db.delete(c)
    return {"ok": True}


# ---------------------------------------------------------------------------------------------- reports
@app.get("/api/reports/executive")
def report(format: str = Query("md", pattern="^(md|csv)$"), q: Q = Depends(), db: Session = Depends(get_session)):
    f = fx(db, q)
    k = E.kpis(db, q.p, f, q.dc)
    c = E.contribution(db, q.p, f, q.dc)
    rec = reconciliation(q, db)
    name = f"sherin-executive-{q.p.start.isoformat()}_{q.p.end.isoformat()}-{f.currency}"
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["metric", "value", "currency_or_unit", "prior", "change_pct", "budget", "basis", "data_class", "definition"])
        for card in k["cards"]:
            w.writerow([card["label"], card["value"], f.currency if card["unit"] == "currency" else card["unit"], card["prior"], card["mom_pct"], card["budget"],
                        card["basis"], card["data_class"], card["definition"]])
        for wline in c["waterfall"]:
            w.writerow([f"Waterfall: {wline['label']}", wline["value"], f.currency, "", "", "", "estimated", q.dc, ""])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    sym = f.currency
    lines = [f"# FLO Bank - Sherin AI executive report", "", f"**Period:** {q.p.label}  ", f"**Currency:** {sym} (rate {f.rate} from {f.source})  ",
             f"**Data class:** {q.dc.upper()}" + ("  \n> All figures are synthetic demonstration data, not actual business performance." if q.dc == "synthetic" else ""), "",
             "## Headline metrics", "", "| Metric | Value | vs prior | vs budget | Basis |", "|---|---:|---:|---:|---|"]
    for card in k["cards"]:
        v = card["value"]
        vs = f"{sym} {v:,.2f}" if card["unit"] == "currency" else (f"{v}%" if card["unit"] == "pct" else f"{v:,.0f}")
        lines.append(f"| {card['label']} | {vs} | {card['mom_pct'] if card['mom_pct'] is not None else '-'}% | "
                     f"{card['budget_variance_pct'] if card['budget_variance_pct'] is not None else '-'}% | {card['basis']} |")
    lines += ["", "## Net AI economic benefit", "", "| Component | Value |", "|---|---:|"] + [f"| {w['label']} | {sym} {w['value']:,.2f} |" for w in c["waterfall"]]
    lines += ["", "## Reconciliation checks", ""] + [f"- {'PASS' if x['ok'] else 'FAIL'} - {x['name']}: {x['rule']}" for x in rec["checks"]]
    lines += ["", "## Definitions", ""] + [f"- **{k_}**: {v}" for k_, v in E.DEFINITIONS.items()]
    lines += ["", "_Forecasts are not guarantees. Cost avoidance is an estimate, not cash or revenue._"]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{name}.md"'})
