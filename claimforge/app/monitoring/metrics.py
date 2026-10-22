"""ClaimIQ production metrics (DETERMINISTIC aggregation)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.monitoring.production import ProductionContext

SEGMENTS = {"benefit": "benefit_type", "provider": "provider_id", "plan": "plan_id",
            "rule_version": "ruleset_id", "release": "release_version"}


def _rates(g: pd.DataFrame) -> dict:
    n = len(g)
    if n == 0:
        return {"claims": 0, "approval_rate": 0.0, "denial_rate": 0.0, "auth_denial_rate": 0.0,
                "avg_reimbursement": 0.0, "auth_failures": 0, "rule_exceptions": 0}
    denied = g.status == "DENIED"
    approved = ~denied
    return {
        "claims": int(n),
        "approval_rate": round(float(approved.mean()), 4),
        "denial_rate": round(float(denied.mean()), 4),
        "auth_denial_rate": round(float((g.reason_code == "AUTH_REQUIRED").mean()), 4),
        "avg_reimbursement": round(float(g.loc[approved, "reimbursement_amount"].mean()) if approved.any() else 0.0, 2),
        "auth_failures": int((g.reason_code == "AUTH_REQUIRED").sum()),
        "rule_exceptions": int(g.rule_exception.sum()),
        "latency_p50_ms": round(float(g.latency_ms.quantile(0.5)), 1),
        "latency_p95_ms": round(float(g.latency_ms.quantile(0.95)), 1),
    }


def kpis(ctx: ProductionContext, since_release: bool = True) -> dict:
    df = ctx.post if since_release else ctx.actual
    out = _rates(df)
    out.update({
        "current_release": ctx.release_version,
        "deployed_ruleset": ctx.deployed_ruleset.ruleset_id,
        "release_date": ctx.release_date.isoformat(),
        "window": "since release" if since_release else "full monitoring window",
        "label": ctx.meta["label"],
    })
    return out


def weekly(ctx: ProductionContext, benefit: str | None = None, expected: bool = False) -> pd.DataFrame:
    df = ctx.expected if expected else ctx.actual
    if benefit:
        df = df[df.benefit_type == benefit]
    rows = []
    for wk, g in df.groupby("week"):
        r = _rates(g)
        r["week"] = wk
        rows.append(r)
    return pd.DataFrame(rows).sort_values("week").reset_index(drop=True)


def rolling_zscore(series: pd.Series, window: int = 6) -> pd.Series:
    """z-score of each point vs the trailing window (excluding the point itself)."""
    mean = series.shift(1).rolling(window, min_periods=3).mean()
    std = series.shift(1).rolling(window, min_periods=3).std().replace(0, np.nan)
    return ((series - mean) / std).round(2)


def denial_trend(ctx: ProductionContext, benefit: str = "PHYSIOTHERAPY") -> pd.DataFrame:
    act = weekly(ctx, benefit)
    exp = weekly(ctx, benefit, expected=True)[["week", "denial_rate", "auth_denial_rate"]].rename(
        columns={"denial_rate": "expected_denial_rate", "auth_denial_rate": "expected_auth_denial_rate"})
    out = act.merge(exp, on="week", how="left")
    out["rolling_z"] = rolling_zscore(out.denial_rate)
    out["post_release"] = out.week >= ctx.release_date
    return out


def top_denial_reasons(ctx: ProductionContext, since_release: bool = True, top: int = 8) -> list[dict]:
    df = ctx.post if since_release else ctx.actual
    d = df[df.status == "DENIED"].reason_code.value_counts().head(top)
    return [{"reason_code": k, "count": int(v), "share": round(v / max(1, d.sum()), 4)} for k, v in d.items()]


def segment(ctx: ProductionContext, by: str, since_release: bool = True, top: int = 15) -> list[dict]:
    col = SEGMENTS.get(by)
    if not col:
        raise ValueError(f"segment must be one of {sorted(SEGMENTS)}")
    df = ctx.post if since_release else ctx.actual
    rows = []
    for key, g in df.groupby(col):
        r = _rates(g)
        r[by] = key
        rows.append(r)
    rows.sort(key=lambda r: -r["claims"])
    return rows[:top]
