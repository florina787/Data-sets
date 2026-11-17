"""FLOW WEALTH v4 research API.

Serves artefacts produced by the pipeline/experiment/replay jobs plus live
calls into the risk engine. Every response carries ``data_status``. There are
no order-routing or brokerage endpoints.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from flowwealth.contracts import DataStatus, Horizon
from flowwealth.data.lake import DataLake
from flowwealth.memory.store import PredictionMemory
from flowwealth.profiles.profile import APPETITE_DEFAULTS, HARD_LIMITS, HORIZON_DATA_REQUIREMENTS, Appetite, TraderProfile
from flowwealth.risk.engine import OrderIntent, PortfolioState, Position, assess

DISCLAIMER = ("Research and educational analytics, not investment advice. Forecasts are uncertain; "
              "nothing here guarantees returns.")


class Settings:
    lake = Path(os.environ.get("FLOWWEALTH_LAKE", "lake"))
    version = os.environ.get("FLOWWEALTH_DATASET", "syn-v1")
    artifacts = Path(os.environ.get("FLOWWEALTH_ARTIFACTS", "artifacts"))
    reports = Path(os.environ.get("FLOWWEALTH_REPORTS", "reports"))
    cors = os.environ.get("FLOWWEALTH_CORS", "http://localhost:5173").split(",")


def _clean(o):
    """NaN/NaT/inf -> null, numpy scalars -> python. Missing is shown as missing, never as 0."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if o is pd.NaT or (not isinstance(o, (str, bytes)) and pd.api.types.is_scalar(o) and pd.isna(o)):
        return None
    return o


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(_clean(content), default=str, allow_nan=False).encode()


S = Settings()
app = FastAPI(title="FLOW WEALTH v4 research API", version="4.0.0a1", default_response_class=SafeJSONResponse)
app.add_middleware(CORSMiddleware, allow_origins=S.cors, allow_methods=["GET", "POST"], allow_headers=["*"])


def _artifact(name: str) -> dict:
    p = S.artifacts / name
    if not p.exists():
        raise HTTPException(404, f"{name} not built yet; run the replay job")
    return json.loads(p.read_text())


@lru_cache(maxsize=1)
def _lake_frames():
    lake = DataLake(S.lake)
    man = lake.manifest(S.version)
    con = lake.connect(S.version)
    bars = con.execute("SELECT ticker, exchange, ts, adj_close, volume, quality_flag FROM bars ORDER BY ticker, ts").fetchdf()
    sec = con.execute("SELECT * FROM securities").fetchdf()
    return man, bars, sec


def _status() -> str:
    man, _, _ = _lake_frames()
    return next(iter(man["status_counts"]))


@app.get("/api/health")
def health():
    return {"ok": True, "disclaimer": DISCLAIMER}


@app.get("/api/status")
def status():
    man, _, _ = _lake_frames()
    return {"dataset": {k: man[k] for k in ("version", "rows", "tickers", "start", "end", "status_counts", "quality", "content_sha256")},
            "data_status": _status(), "live_feeds": [], "brokerage": "none (paper trading only)",
            "horizon_readiness": {h.value: {"ready": _status() in r["status"] and _status() != "SYNTHETIC", **r}
                                  for h, r in HORIZON_DATA_REQUIREMENTS.items()},
            "disclaimer": DISCLAIMER}


@app.get("/api/market/overview")
def overview():
    man, bars, sec = _lake_frames()
    df = bars[bars.quality_flag == "ok"].merge(sec[["ticker", "sector", "country"]], on="ticker")
    df["r"] = np.log(df.adj_close).groupby(df.ticker).diff()
    df["d"] = df.ts.dt.normalize()

    def tile(g, name):
        idx = np.exp(g.groupby("d").r.mean().fillna(0).cumsum()) * 100
        return {"name": name, "value": round(float(idx.iloc[-1]), 2), "change_1d": float(idx.iloc[-1] / idx.iloc[-2] - 1),
                "spark": [round(float(v), 3) for v in idx.iloc[-30:]], "as_of": str(idx.index[-1].date())}

    sectors = [tile(g, s) for s, g in df.groupby("sector")]
    countries = [tile(g, c) for c, g in df.groupby("country")]
    last = df[df.d == df.d.max()].dropna(subset=["r"])
    movers = last.sort_values("r")
    fmt = lambda x: [{"ticker": r.ticker, "sector": r.sector, "close": round(float(r.adj_close), 2), "change": float(np.expm1(r.r))} for r in x.itertuples()]
    return {"data_status": _status(), "as_of": str(df.ts.max()), "composite": tile(df, "FW Composite (equal-weight)"),
            "sectors": sectors, "countries": countries, "gainers": fmt(movers.tail(5)[::-1]), "losers": fmt(movers.head(5)),
            "breadth_up": float((last.r > 0).mean())}


@app.get("/api/market/series")
def series(ticker: str, range: str = Query("1Y", pattern="^(1W|1M|3M|1Y|2Y|MAX)$")):
    _, bars, sec = _lake_frames()
    s = bars[bars.ticker == ticker.upper()]
    if s.empty:
        raise HTTPException(404, "unknown ticker")
    days = {"1W": 7, "1M": 31, "3M": 92, "1Y": 366, "2Y": 731, "MAX": 100000}[range]
    s = s[s.ts >= s.ts.max() - pd.Timedelta(days=days)]
    meta = sec[sec.ticker == ticker.upper()].iloc[0]
    return {"ticker": ticker.upper(), "exchange": meta.exchange, "sector": meta.sector, "data_status": _status(),
            "delisted": None if pd.isna(meta.delisted) else str(meta.delisted.date()),
            "points": [{"t": str(t), "c": round(float(c), 4), "flag": f} for t, c, f in zip(s.ts, s.adj_close, s.quality_flag)]}


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=20)):
    _, _, sec = _lake_frames()
    m = sec[sec.ticker.str.contains(q.upper(), regex=False) | sec.sector.str.upper().str.contains(q.upper(), regex=False)]
    cols = ["ticker", "exchange", "country", "sector", "listed", "delisted"]
    return {"data_status": _status(), "results": m.head(10)[cols].to_dict("records")}


@app.get("/api/rankings")
def rankings():
    r = _artifact("rankings.json")
    return {**r, "disclaimer": DISCLAIMER}


@app.get("/api/risk/crash")
def crash():
    return _artifact("crash_risk.json")


@app.get("/api/memory")
def memory(limit: int = Query(50, le=500)):
    p = S.artifacts / "prediction_memory.db"
    if not p.exists():
        raise HTTPException(404, "prediction memory not built")
    mem = PredictionMemory(p)
    rows = mem.joined()
    ok, bad = mem.verify_chain()
    return {"summary": _artifact("memory_summary.json"), "chain_verified": ok, "first_bad_seq": bad,
            "recent": [{**{k: r[k] for k in ("prediction_id", "created_at", "ticker", "horizon", "target_time",
                                              "actual_return", "benchmark_return", "direction_correct")},
                        "forecast_return": r["payload"]["forecast_return"], "regime": r["payload"]["regime"],
                        "strategy_id": r["payload"]["strategy_id"], "data_status": r["payload"]["data_status"]}
                       for r in rows[-limit:][::-1]]}


@app.get("/api/experiments")
def experiments():
    out = []
    for p in sorted(S.reports.glob("*.json")):
        r = json.loads(p.read_text())
        out.append({k: r.get(k) for k in ("experiment", "dataset_version", "data_status", "rows_modelled", "horizon_bars",
                                           "split", "walk_forward_summary", "holdout", "caveat")})
    return {"experiments": out}


@app.get("/api/profiles/limits")
def limits():
    return {"hard_limits": HARD_LIMITS.model_dump(),
            "appetite_defaults": {a.value: l.model_dump() for a, l in APPETITE_DEFAULTS.items()},
            "horizon_data_requirements": {h.value: r for h, r in HORIZON_DATA_REQUIREMENTS.items()}}


class RiskCheckIn(BaseModel):
    profile: TraderProfile
    order: dict
    equity: float
    peak_equity: float
    day_start_equity: float
    positions: list[dict] = []


@app.post("/api/risk/check")
def risk_check(body: RiskCheckIn):
    o = dict(body.order)
    o["data_status"] = DataStatus(o["data_status"])
    o["horizon"] = Horizon(o["horizon"])
    o["data_timestamp"] = pd.Timestamp(o["data_timestamp"]).to_pydatetime()
    try:
        order = OrderIntent(**o)
    except TypeError as e:
        raise HTTPException(422, str(e))
    pf = PortfolioState(body.equity, body.peak_equity, body.day_start_equity, [Position(**p) for p in body.positions])
    d = assess(order, pf, body.profile)
    return {"verdict": d.verdict.value, "approved_qty": d.approved_qty, "reasons": d.reasons, "checks": d.checks,
            "effective_limits": body.profile.effective_limits().model_dump()}
