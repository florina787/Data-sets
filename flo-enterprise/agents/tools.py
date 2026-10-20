"""Tool catalog. Each tool declares the permission it needs and how to resolve the protected resource; the gateway
enforces both for the human principal on every call. Handlers call deterministic services only."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from analytics import data_quality, decisions, service as fin, wealth
from analytics.money import from_cents
from governance import resources
from governance.policy import Resource
from harness.tools import TOOLS, ToolSpec
from scenarios import engine as scen

ID_CLIENT = r"^C-\d{5}$"
ID_PORT = r"^PF-\d{4}$"


def _j(x):
    """JSON-safe conversion (Decimal -> str, date -> iso)."""
    return json.loads(json.dumps(x, default=lambda o: str(o) if isinstance(o, Decimal) else o.isoformat()))


class NoArgs(BaseModel):
    model_config = {"extra": "forbid"}


class Window(BaseModel):
    model_config = {"extra": "forbid"}
    months: int = Field(12, ge=1, le=24)


class ClientArg(BaseModel):
    model_config = {"extra": "forbid"}
    client_id: str = Field(pattern=ID_CLIENT)


class PortfolioArg(BaseModel):
    model_config = {"extra": "forbid"}
    portfolio_id: str = Field(pattern=ID_PORT)


class ProductArg(BaseModel):
    model_config = {"extra": "forbid"}
    product_id: str = Field(pattern=r"^P-\d{3}$")


class ScenarioArgs(BaseModel):
    model_config = {"extra": "forbid"}
    preset: Literal["base", "bull", "bear", "severe_stress"] = "base"
    equity_shock: float | None = Field(None, ge=-0.8, le=0.8)
    rate_shock_bps: float | None = Field(None, ge=-500, le=500)
    net_flows_pct: float | None = Field(None, ge=-0.5, le=0.5)
    fee_compression_bps: float | None = Field(None, ge=0, le=100)
    horizon_months: int | None = Field(None, ge=1, le=60)
    portfolio_ids: list[str] | None = None


class SearchArgs(BaseModel):
    model_config = {"extra": "forbid"}
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(5, ge=1, le=10)
    doc_types: list[str] | None = None


class CompareDocs(BaseModel):
    model_config = {"extra": "forbid"}
    old_id: str
    new_id: str


class DraftArgs(BaseModel):
    model_config = {"extra": "forbid"}
    client_id: str = Field(pattern=ID_CLIENT)
    purpose: Literal["portfolio_review", "meeting_follow_up", "market_update"] = "portfolio_review"
    language: Literal["en", "fr", "es", "hi", "ta", "ko"] = "en"


class ApprovalArgs(BaseModel):
    model_config = {"extra": "forbid"}
    action: Literal["comms:send", "recommendation:deliver", "export:sensitive", "board:distribute"]
    resource_ref: str = Field(max_length=80)
    payload: dict
    evidence: list = []


class ExportArgs(BaseModel):
    model_config = {"extra": "allow"}


class TradeArgs(BaseModel):
    model_config = {"extra": "allow"}


def _client_res(ctx, a):
    return resources.client(ctx.adapters.store, a.client_id)


def _port_res(ctx, a):
    return resources.portfolio(ctx.adapters.store, a.portfolio_id)


def _firm(kind, classification="confidential"):
    return lambda ctx, a: Resource(kind, "enterprise", ctx.principal.tenant_id, {"classification": classification})


def reg(name, desc, perm, model, handler, resource=None, upstream="analytics", side_effect=False, cls="internal", timeout=8.0):
    TOOLS.register(ToolSpec(name, desc, perm, model, handler, resource, upstream, timeout, 600, side_effect, cls))


# ---------------------------------------------------------------- executive / finance
reg("finance.kpis", "Enterprise KPIs for a trailing window", "exec:read", Window, lambda c, a: fin.executive_kpis(c.adapters, a.months), _firm("finance"))
reg("finance.aum_waterfall", "AUM roll-forward with reconciliation", "finance:read", Window, lambda c, a: _j(fin.aum_waterfall(c.adapters, a.months)), _firm("finance"))
reg("finance.revenue_attribution", "Revenue change split into volume, mix and fee effects", "finance:read", Window,
    lambda c, a: fin.revenue_attribution(c.adapters, a.months), _firm("finance"))
reg("finance.margin_trend", "Operating margin and revenue yield by month", "finance:read", Window, lambda c, a: fin.margin_trend(c.adapters, 24), _firm("finance"))
reg("finance.revenue_expenses", "Revenue and expenses by month", "finance:read", Window, lambda c, a: fin.revenue_expenses(c.adapters, 24), _firm("finance"))
reg("finance.net_flows", "Net flows by vehicle", "finance:read", Window, lambda c, a: fin.net_flows(c.adapters, a.months), _firm("finance"))
reg("finance.product_profitability", "Product contribution", "finance:read", Window, lambda c, a: fin.product_profitability(c.adapters, a.months), _firm("finance"))
reg("finance.actual_vs_budget", "Actual vs budget", "finance:read", Window, lambda c, a: fin.actual_vs_budget(c.adapters, a.months), _firm("finance"))
reg("strategy.decisions", "Decision memory summary", "decisions:read", NoArgs,
    lambda c, a: _j(decisions.summary(c.adapters, c.adapters.market.months()[-1])), _firm("strategy"))
reg("strategy.decision_list", "All decisions with outcomes", "decisions:read", NoArgs,
    lambda c, a: _j({"decisions": decisions.decisions_view(c.adapters, c.adapters.market.months()[-1])}), _firm("strategy"))
reg("strategy.initiatives", "Strategic initiative scorecard", "decisions:read", NoArgs, lambda c, a: fin.initiative_scorecard(c.adapters), _firm("strategy"))

# ---------------------------------------------------------------- investment
reg("investment.enterprise_concentration", "Aggregate issuer and sector concentration across portfolios", "investment:read_aggregate", NoArgs,
    lambda c, a: fin.enterprise_concentration(c.adapters), _firm("investment"))
reg("investment.portfolio_list", "Metrics for all managed portfolios", "investment:read", NoArgs, lambda c, a: fin.portfolio_list(c.adapters), _firm("investment"))
reg("investment.portfolio_detail", "Performance, risk, allocation and holdings for one portfolio", "portfolio:read", PortfolioArg,
    lambda c, a: fin.portfolio_detail(c.adapters, a.portfolio_id), _port_res)
reg("investment.fund_list", "Fund range metrics", "product_research:read", NoArgs, lambda c, a: fin.fund_list(c.adapters), _firm("product", "public"))
reg("investment.fund_detail", "One fund's history and holdings", "product_research:read", ProductArg, lambda c, a: fin.fund_detail(c.adapters, a.product_id), _firm("product", "public"))
reg("investment.correlation", "Sector correlation matrix", "risk:read", NoArgs, lambda c, a: fin.sector_correlation(c.adapters), _firm("risk"))
reg("risk.heatmap", "Enterprise risk register heatmap", "risk:read_aggregate", NoArgs, lambda c, a: fin.risk_heatmap(c.adapters), _firm("risk"))
reg("market.intelligence", "Benchmark and sector returns from the market data provider", "market:read", NoArgs,
    lambda c, a: fin.market_intelligence(c.adapters), _firm("market"), upstream="market_data", timeout=3.0)
reg("scenario.run", "Run a deterministic scenario", "scenarios:run", ScenarioArgs,
    lambda c, a: _j(scen.run(c.adapters, scen.preset(a.preset, equity_shock=a.equity_shock, rate_shock_bps=a.rate_shock_bps,
                                                     net_flows_pct=a.net_flows_pct, fee_compression_bps=a.fee_compression_bps,
                                                     horizon_months=a.horizon_months))), _firm("scenario"))
reg("scenario.compare", "Compare base/bull/bear/severe scenarios", "scenarios:run", NoArgs, lambda c, a: _j(scen.compare(c.adapters)), _firm("scenario"))
reg("scenario.sensitivity", "One-at-a-time sensitivity (tornado)", "scenarios:run", NoArgs, lambda c, a: _j(scen.sensitivity(c.adapters)), _firm("scenario"))


# ---------------------------------------------------------------- wealth (client-scoped; ABAC assignment enforced)
def _client_profile(c, a):
    cl = c.adapters.crm.client(a.client_id)
    keep = ("id", "full_name", "segment", "risk_profile", "risk_score", "time_horizon_years", "language", "status", "province", "advisor_id")
    out = {k: cl[k] for k in keep}
    out["investable_assets"] = float(from_cents(cl["investable_assets_cents"]))
    out["age"] = c.adapters.market.months()[-1].year - cl["dob"].year
    out["kyc_last_review"] = cl["kyc_last_review"].isoformat()
    pos = c.adapters.crm.positions(a.client_id)
    prods = {p["id"]: p for p in c.adapters.accounting.products()}
    out["fund_positions"] = [{"product_id": p["product_id"], "name": prods[p["product_id"]]["name"], "market_value": float(from_cents(p["market_value_cents"])),
                              "fee_bps": prods[p["product_id"]]["mgmt_fee_bps"]} for p in pos]
    out["portfolio_ids"] = [p["id"] for p in c.adapters.crm.portfolios_for(a.client_id)]
    return out


def _client_portfolios(c, a):
    rf = c.adapters.market.benchmark_returns("B-MM")
    return {"portfolios": [fin.portfolio_metrics(c.adapters, p["id"], rf) for p in c.adapters.crm.portfolios_for(a.client_id)]}


def _goals(c, a):
    rules = c.engine.bundle.suitability
    cl = c.adapters.crm.client(a.client_id)
    er = rules["expected_returns"][cl["risk_profile"]]
    return {"goals": _j([wealth.goal_progress(g, er, c.adapters.market.months()[-1]) for g in c.adapters.crm.goals(a.client_id)]),
            "expected_return_assumption": er}


def _interactions(c, a):
    rows = sorted(c.adapters.crm.interactions(a.client_id), key=lambda r: r["ts"], reverse=True)[:12]
    return {"interactions": [{"id": r["id"], "ts": r["ts"].isoformat(), "channel": r["channel"], "type": r["interaction_type"], "topic": r["topic"],
                              "sentiment": r["sentiment"], "follow_up_required": r["follow_up_required"], "notes": r["notes"]} for r in rows]}


def _suitability(c, a):
    cl = c.adapters.crm.client(a.client_id)
    pms = _client_portfolios(c, a)["portfolios"]
    return wealth.suitability_check(cl, pms, c.engine.bundle.suitability, c.adapters.market.months()[-1])


def _retirement(c, a):
    cl = c.adapters.crm.client(a.client_id)
    rules = c.engine.bundle.suitability
    goals = [g for g in c.adapters.crm.goals(a.client_id) if g["goal_type"] == "retirement"]
    age = c.adapters.market.months()[-1].year - cl["dob"].year
    savings = sum((from_cents(p["market_value_cents"]) for p in c.adapters.crm.positions(a.client_id)), Decimal(0))
    savings += sum((from_cents(c.adapters.portfolio.valuations(p["id"])[-1]["mv_close_cents"]) for p in c.adapters.crm.portfolios_for(a.client_id)), Decimal(0))
    monthly = from_cents(goals[0]["monthly_contribution_cents"]) if goals else Decimal(0)
    proj = wealth.retirement_projection(savings, monthly, max(0, 65 - age), rules["expected_returns"][cl["risk_profile"]], rules["inflation_assumption"])
    tx = [t for p in c.adapters.crm.portfolios_for(a.client_id) for t in c.adapters.portfolio.transactions(p["id"])]
    return _j({"age": age, "current_savings": savings, "monthly_contribution": monthly, **proj,
               "cash_flow_forecast": wealth.cash_flow_forecast(c.adapters.crm.goals(a.client_id), tx),
               "retirement_goal": goals[0] if goals else None})


reg("client.profile", "Client profile and fund positions (assigned clients only)", "client:read", ClientArg, _client_profile, _client_res, upstream="crm", cls="confidential")
reg("client.portfolios", "Metrics for a client's managed portfolios", "client:read", ClientArg, _client_portfolios, _client_res, cls="confidential")
reg("client.goals", "Goal progress", "client:read", ClientArg, _goals, _client_res, upstream="crm", cls="confidential")
reg("client.interactions", "Recent service interactions", "client:read", ClientArg, _interactions, _client_res, upstream="crm", cls="confidential")
reg("client.suitability", "Rule-based suitability screen", "client:read", ClientArg, _suitability, _client_res, cls="confidential")
reg("client.retirement", "Retirement projection and cash-flow forecast", "retirement:run", ClientArg, _retirement, _client_res, cls="confidential")


def _draft(c, a):
    from agents.comms import draft_communication
    return draft_communication(c, a.client_id, a.purpose, a.language)


reg("comms.draft", "Draft a client communication (no side effects)", "comms:draft", DraftArgs, _draft, _client_res, cls="confidential")


def _request_approval(c, a):
    from approvals.service import ApprovalService, to_dict
    from backend.db.session import session_scope
    svc = ApprovalService(c.engine, lambda tid, ref: resources.from_ref(c.adapters.store, tid, ref))
    with session_scope() as s:
        apr = svc.request(s, c.principal, a.action, a.resource_ref, a.payload, a.evidence, thread_id=c.workflow_id)
        out = to_dict(apr)
    c.approvals.append({"id": out["id"], "status": out["status"], "action": a.action})
    return out


reg("approval.request", "Create a durable approval request for an approval-gated action", "ask:use", ApprovalArgs, _request_approval, side_effect=True)


# ---------------------------------------------------------------- knowledge & compliance
def _search(c, a):
    from backend.db.session import session_scope
    from retrieval.search import search
    with session_scope() as s:
        r = search(s, c.engine, c.principal, a.query, a.k, today=date.today(), doc_types=a.doc_types)
    for x in r["results"]:
        c.citations.append({"agent": c.agent.name, "document_id": x["document_id"], "title": x["title"], "version": x["version"],
                            "section": x["section"], "chunk_id": x["chunk_id"]})
    return r


def _compare(c, a):
    from backend.db.session import session_scope
    from retrieval.search import compare_documents
    with session_scope() as s:
        return compare_documents(s, c.engine, c.principal, a.old_id, a.new_id)


reg("docs.search", "Permission-aware hybrid document search with citations", "docs:read", SearchArgs, _search, upstream="documents")
reg("docs.compare", "Compare two policy/regulatory document versions", "compliance:read", CompareDocs, _compare, upstream="documents")
reg("compliance.events", "Compliance exceptions", "compliance:read", NoArgs,
    lambda c, a: _j({"events": c.adapters.warehouse.table("compliance_events")}), _firm("compliance"))
reg("compliance.controls", "Control catalogue", "compliance:read", NoArgs, lambda c, a: _j({"controls": c.adapters.warehouse.table("controls")}), _firm("compliance"))


# ---------------------------------------------------------------- AI operations
def _traces(c, a):
    from sqlalchemy import select
    from backend.db import models as m
    from backend.db.session import session_scope
    with session_scope() as s:
        rows = list(s.scalars(select(m.AgentTrace).where(m.AgentTrace.tenant_id == c.principal.tenant_id)))
    agg: dict = {}
    for r in rows:
        g = agg.setdefault(r.agent_id, {"runs": 0, "failures": 0, "latency": [], "classes": {}, "cost": 0.0, "retries": 0})
        g["runs"] += 1
        g["failures"] += r.status == "failed"
        g["latency"].append(r.latency_ms)
        g["cost"] += r.cost_usd
        g["retries"] += r.retry_count
        if r.failure_class:
            g["classes"][r.failure_class] = g["classes"].get(r.failure_class, 0) + 1
    out = []
    for k, g in agg.items():
        lat = sorted(g["latency"])
        out.append({"agent": k, "runs": g["runs"], "failures": g["failures"], "failure_rate": round(g["failures"] / g["runs"], 4),
                    "p95_latency_ms": lat[int(0.95 * (len(lat) - 1))], "failure_classes": g["classes"], "cost_usd": round(g["cost"], 4),
                    "retries": g["retries"]})
    out.sort(key=lambda x: -x["failure_rate"])
    fails = [r for r in rows if r.agent_id == out[0]["agent"] and r.status == "failed"] if out else []
    days = {}
    for r in fails:
        days[r.started_at.date().isoformat()] = days.get(r.started_at.date().isoformat(), 0) + 1
    return {"agents": out, "worst_agent_failures_by_day": dict(sorted(days.items())), "total_traces": len(rows)}


def _breakers(c, a):
    from harness.resilience import all_breakers
    return {"breakers": all_breakers()}


reg("aiops.traces", "Agent trace statistics (redacted)", "aiops:read", NoArgs, _traces, _firm("aiops", "internal"), upstream="observability")
reg("aiops.breakers", "Circuit breaker states", "aiops:read", NoArgs, _breakers, _firm("aiops", "internal"))
reg("data_quality.run", "Run data quality checks", "aiops:read", NoArgs, lambda c, a: data_quality.run_checks(c.adapters), _firm("aiops", "internal"))

# ---------------------------------------------------------------- deliberately dangerous tools (always blocked by policy)
reg("crm.export_client_data", "Bulk client export (approval-gated; not allowlisted for any agent)", "export:sensitive", ExportArgs,
    lambda c, a: {"error": "unreachable"}, lambda c, a: Resource("client", "*", c.principal.tenant_id, {"classification": "restricted"}),
    side_effect=True, cls="restricted")
reg("comms.send_email", "Send an e-mail to a client (approval-gated; execution only via approval workflow)", "comms:send", DraftArgs,
    lambda c, a: {"error": "unreachable"}, _client_res, side_effect=True)
reg("trading.execute_trade", "Execute a securities trade (prohibited in this deployment)", "trade:execute", TradeArgs,
    lambda c, a: {"error": "unreachable"}, side_effect=True, cls="restricted")
