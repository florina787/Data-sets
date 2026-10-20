"""Investment intelligence workspace and the scenario simulator."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from analytics import service as S
from backend.api.deps import Ctx, authorize, cached, current, require
from governance import resources
from scenarios import engine as E

router = APIRouter(prefix="/api")


@router.get("/investment/portfolios")
def portfolios(request: Request, mandate: str | None = None, risk_profile: str | None = None, ctx: Ctx = Depends(require("investment:read"))):
    out = cached(ctx, request, lambda: S.portfolio_list(ctx.adapters, filters={"mandate": mandate, "risk_profile": risk_profile}))
    # investment oversight roles see portfolios without client identity (data minimization)
    return {**out, "data": {**out["data"], "portfolios": [{**p, "name": f"{p['mandate']} portfolio {p['id']}", "client_id": None}
                                                         for p in out["data"]["portfolios"]]}}


@router.get("/investment/portfolios/{portfolio_id}")
def portfolio(portfolio_id: str, ctx: Ctx = Depends(current)):
    authorize(ctx, "portfolio:read", resources.portfolio(ctx.store, portfolio_id))
    out = S.portfolio_detail(ctx.adapters, portfolio_id)
    if not set(ctx.principal.roles) & {"wealth_advisor"}:
        out["data"]["portfolio"]["client_id"] = None
        out["data"]["metrics"]["client_id"] = None
        out["data"]["portfolio"]["name"] = f"{out['data']['portfolio']['mandate']} portfolio {portfolio_id}"
        out["data"]["metrics"]["name"] = out["data"]["portfolio"]["name"]
    return out


@router.get("/investment/funds")
def funds(request: Request, asset_class: str | None = None, vehicle: str | None = None, ctx: Ctx = Depends(require("product_research:read"))):
    return cached(ctx, request, lambda: S.fund_list(ctx.adapters, {"asset_class": asset_class, "vehicle": vehicle}))


@router.get("/investment/funds/{product_id}")
def fund(product_id: str, ctx: Ctx = Depends(require("product_research:read"))):
    try:
        return S.fund_detail(ctx.adapters, product_id)
    except KeyError:
        raise HTTPException(404, "fund not found") from None


@router.get("/investment/concentration")
def concentration(request: Request, ctx: Ctx = Depends(require("investment:read_aggregate"))):
    return cached(ctx, request, lambda: S.enterprise_concentration(ctx.adapters))


@router.get("/investment/correlation")
def correlation(request: Request, ctx: Ctx = Depends(require("risk:read"))):
    return cached(ctx, request, lambda: S.sector_correlation(ctx.adapters))


@router.get("/investment/risk-return")
def risk_return(request: Request, universe: str = Query("funds", pattern="^(funds|portfolios)$"), ctx: Ctx = Depends(current)):
    authorize(ctx, "product_research:read" if universe == "funds" else "investment:read")
    return cached(ctx, request, lambda: S.risk_return_scatter(ctx.adapters, universe))


@router.get("/investment/market")
def market(request: Request, ctx: Ctx = Depends(require("market:read"))):
    try:
        return S.market_intelligence(ctx.adapters)
    except Exception as e:  # graceful degradation when the provider is down
        raise HTTPException(503, {"code": "UPSTREAM-UNAVAILABLE", "message": f"market data provider unavailable: {e.__class__.__name__}"}) from e


@router.get("/investment/geographic")
def geographic(request: Request, scope: str = Query("portfolios", pattern="^(enterprise|products|portfolios|portfolio)$"),
               portfolio_id: str | None = None, ctx: Ctx = Depends(current)):
    if scope == "portfolio":
        if not portfolio_id:
            raise HTTPException(422, "portfolio_id required")
        authorize(ctx, "portfolio:read", resources.portfolio(ctx.store, portfolio_id))
        return S.geographic_exposure(ctx.adapters, "portfolio", portfolio_id)
    authorize(ctx, "investment:read_aggregate")
    return cached(ctx, request, lambda: S.geographic_exposure(ctx.adapters, scope))


# ------------------------------------------------------------------ scenarios
class ScenarioBody(BaseModel):
    model_config = {"extra": "forbid"}
    preset: str = Field("base", pattern="^(base|bull|bear|severe_stress)$")
    equity_shock: float | None = None
    bond_shock: float | None = None
    rate_shock_bps: float | None = None
    inflation: float | None = None
    net_flows_pct: float | None = None
    stress_redemptions_pct: float | None = None
    fee_compression_bps: float | None = None
    opex_growth: float | None = None
    tech_investment: float | None = None
    expected_equity_return: float | None = None
    expected_bond_return: float | None = None
    horizon_months: int | None = None
    portfolio_id: str | None = None


@router.get("/scenarios/presets")
def presets(ctx: Ctx = Depends(require("scenarios:run"))):
    return {"presets": E.PRESETS, "defaults": asdict(E.ScenarioInput()), "fixed_assumptions": {"duration": E.DURATION}}


@router.post("/scenarios/run")
def run_scenario(body: ScenarioBody, ctx: Ctx = Depends(require("scenarios:run"))):
    s = E.preset(body.preset, **body.model_dump(exclude={"preset", "portfolio_id"}))
    try:
        out = E.run(ctx.adapters, s)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if body.portfolio_id:
        authorize(ctx, "portfolio:read", resources.portfolio(ctx.store, body.portfolio_id))
        out["selected_portfolio"] = E.portfolio_impacts(ctx.adapters, s, [body.portfolio_id], top=1)
    return out


@router.get("/scenarios/compare")
def compare(request: Request, ctx: Ctx = Depends(require("scenarios:run"))):
    return cached(ctx, request, lambda: E.compare(ctx.adapters))


@router.get("/scenarios/sensitivity")
def sensitivity(request: Request, ctx: Ctx = Depends(require("scenarios:run"))):
    return cached(ctx, request, lambda: E.sensitivity(ctx.adapters))
