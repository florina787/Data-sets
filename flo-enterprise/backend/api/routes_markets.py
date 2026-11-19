"""FLOW WEALTH market research endpoints (public historical market data and research results).

Every endpoint authenticates, then authorizes the action against a public ``market_dataset`` resource (deny by default,
denials audited). Nothing here touches client or firm records, and there are no order or trading endpoints.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import Ctx, authorize, current
from governance.policy import Resource
from markets import catalog, current as feed, ledger_view, risk, service as S

router = APIRouter(prefix="/api/markets")
TICKER = re.compile(r"^[A-Z]{1,5}(-[A-Z])?$")
DAY = r"^\d{4}-\d{2}-\d{2}$"


def _auth(ctx: Ctx, action: str) -> None:
    authorize(ctx, action, Resource("market_dataset", catalog.PRIMARY, ctx.principal.tenant_id, {"classification": "public"}))


def _guard(fn):
    try:
        return fn()
    except S.MarketDataUnavailable as e:
        raise HTTPException(503, {"code": "MARKET-DATA-UNAVAILABLE", "message": str(e)}) from e


def _ticker(t: str) -> str:
    t = t.upper()
    if not TICKER.match(t):
        raise HTTPException(422, "invalid ticker")
    return t


@router.get("/status")
def status(ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return {"lake_available": S.available(), "last_session": str(S.last_session()) if S.available() else None, "data_status": S.DATA_STATUS,
            "current_feed": feed.status(), "profiles": risk.profiles()}


@router.get("/datasets")
def datasets(ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return _guard(S.datasets)


@router.get("/overview")
def overview(ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return _guard(S.overview)


@router.get("/regime")
def regime(ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return _guard(S.regime)


@router.get("/security/{ticker}")
def security(ticker: str, start: str | None = Query(None, pattern=DAY), end: str | None = Query(None, pattern=DAY), ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return _guard(lambda: S.security(_ticker(ticker), start, end))


@router.get("/compare")
def compare(tickers: str = Query(..., max_length=40), start: str | None = Query(None, pattern=DAY), end: str | None = Query(None, pattern=DAY),
            ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    ts = [_ticker(t.strip()) for t in tickers.split(",") if t.strip()][:4]
    if len(ts) < 2:
        raise HTTPException(422, "need at least two tickers")
    return _guard(lambda: S.compare(ts, start, end))


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=40), ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return {"tickers": S.resolve_tickers(q, names=True)}


@router.get("/news/{ticker}")
def news(ticker: str, ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")
    return _guard(lambda: S.news(_ticker(ticker), k=15))


@router.get("/research")
def research(ctx: Ctx = Depends(current)):
    _auth(ctx, "quant:read")
    return _guard(S.model_report)


@router.get("/predictions")
def predictions(ticker: str | None = None, limit: int = Query(100, ge=1, le=500), ctx: Ctx = Depends(current)):
    _auth(ctx, "quant:read")
    return ledger_view.summary(recent=limit, ticker=_ticker(ticker) if ticker else None)


@router.get("/risk/{ticker}")
def risk_check(ticker: str, speed: str = Query("swing", pattern="^(long_term|position|swing|intraday|swift)$"),
               appetite: str = Query("moderate", pattern="^(conservative|moderate|aggressive)$"), ctx: Ctx = Depends(current)):
    _auth(ctx, "market:read")

    def run():
        ev = S.evidence_pack(_ticker(ticker))
        vol = ev["features"].get("vol_20")
        return risk.assess(ticker=ev["ticker"], volatility_annual=None if vol is None else vol * 252 ** 0.5,
                           drawdown_1y=ev["features"].get("dd_252"), adv_usd=None, data_status=S.DATA_STATUS, speed=speed, appetite=appetite)
    return _guard(run)
