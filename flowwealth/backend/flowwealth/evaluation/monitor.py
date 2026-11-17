"""Outcome evaluation and drift detection over Prediction Memory."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from flowwealth.research.metrics import brier, calibration


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population stability index; >0.25 is conventionally a significant shift."""
    reference, current = np.asarray(reference)[~np.isnan(reference)], np.asarray(current)[~np.isnan(current)]
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(reference, edges)[0] / len(reference)
    c = np.histogram(current, edges)[0] / len(current)
    r, c = np.clip(r, 1e-6, None), np.clip(c, 1e-6, None)
    return float(np.sum((c - r) * np.log(c / r)))


def evaluate_records(records: list[dict]) -> dict:
    rows = [r for r in records if r.get("actual_return") is not None]
    if not rows:
        return {"n_resolved": 0, "n_pending": len(records)}
    df = pd.DataFrame([{"actual": r["actual_return"], "fr": r["payload"].get("forecast_return"),
                        "pu": r["payload"].get("prob_up"), "calibrated": r["payload"].get("calibrated"),
                        "correct": r["direction_correct"], "regime": r["payload"].get("regime"),
                        "bench": r["benchmark_return"]} for r in rows])
    out: dict = {"n_resolved": len(df), "n_pending": len(records) - len(df),
                 "directional_accuracy": float(df.correct.dropna().mean()) if df.correct.notna().any() else None}
    if df.fr.notna().any():
        m = df.fr.notna()
        out["mae"] = float((df.fr[m] - df.actual[m]).abs().mean())
        out["rank_ic"] = float(df.fr[m].rank().corr(df.actual[m].rank())) if m.sum() > 5 else None
    if df.pu.notna().any():
        m = df.pu.notna()
        y = (df.actual[m] > 0).astype(float)
        out["brier"] = brier(df.pu[m], y)
        out["brier_climatology"] = brier(np.full(m.sum(), y.mean()), y)
        out["calibration"] = calibration(df.pu[m].to_numpy(), y.to_numpy())
    if df.bench.notna().any():
        ex = df.actual - df.bench
        out["mean_excess_vs_benchmark"] = float(ex.mean())
        m = df.fr.notna() & df.bench.notna()
        if m.sum() > 5:  # for excess-return forecasts, compare against excess outcomes
            out["rank_ic_vs_excess"] = float(df.fr[m].rank().corr(ex[m].rank()))
            out["directional_accuracy_vs_excess"] = float((np.sign(df.fr[m]) == np.sign(ex[m])).mean())
    out["by_regime"] = df.groupby("regime").correct.agg(["mean", "count"]).reset_index().to_dict("records")
    return out


@dataclass
class DegradationRule:
    metric: str = "rank_ic"
    window: int = 60           # recent resolved predictions
    min_n: int = 30
    floor: float = 0.0         # recent metric below floor ...
    drop_vs_reference: float = 0.5  # ... or below 50% of reference


def check_degradation(reference: float | None, recent: float | None, n_recent: int, rule: DegradationRule) -> dict:
    if recent is None or n_recent < rule.min_n:
        return {"status": "insufficient_data", "n": n_recent}
    flags = []
    if recent < rule.floor:
        flags.append(f"{rule.metric} {recent:.4f} below floor {rule.floor}")
    if reference and reference > 0 and recent < reference * rule.drop_vs_reference:
        flags.append(f"{rule.metric} {recent:.4f} < {rule.drop_vs_reference:.0%} of reference {reference:.4f}")
    return {"status": "degraded" if flags else "ok", "flags": flags, "n": n_recent,
            "action": "flag retraining candidate; challenger evaluation required (no auto-retrain)" if flags else None}
