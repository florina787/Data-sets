"""Anomaly detection (STATISTICAL / DETERMINISTIC — never an LLM).

Two baselines are supported:
* RELEASE_PROJECTION (default): the same post-release claims shadow-adjudicated with the
  APPROVED specification. Excess denials are tested with a Poisson z-score
  ``(observed - expected) / sqrt(expected)``. This separates *intended* behaviour changes
  (e.g. new authorization rule) from defects.
* HISTORICAL: post-release vs the equally long pre-release window, tested with a
  two-proportion z-test.

An anomaly is DETECTED when relative change >= threshold AND z >= z_threshold AND the
segment has at least ``min_volume`` claims.
"""

from __future__ import annotations

import hashlib
import math
from datetime import timedelta

import pandas as pd

from app.models.domain import Anomaly
from app.monitoring.production import ProductionContext

METRICS = {"denial_rate": lambda g: g.status == "DENIED",
           "auth_denial_rate": lambda g: g.reason_code == "AUTH_REQUIRED"}


def relative_change(baseline: float, observed: float) -> float:
    if baseline == 0:
        return math.inf if observed > 0 else 0.0
    return (observed - baseline) / baseline


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> float:
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (p2 - p1) / se


def poisson_excess_z(observed: int, expected: float) -> float:
    if expected <= 0:
        return math.inf if observed > 0 else 0.0
    return (observed - expected) / math.sqrt(expected)


def evaluate(metric: str, segment: dict, baseline_mode: str, x_base: int, n_base: int, x_obs: int, n_obs: int,
             rel_threshold: float, z_threshold: float, min_volume: int = 100) -> Anomaly:
    base_rate = x_base / n_base if n_base else 0.0
    obs_rate = x_obs / n_obs if n_obs else 0.0
    rel = relative_change(base_rate, obs_rate)
    z = poisson_excess_z(x_obs, x_base * (n_obs / n_base) if n_base else 0) if baseline_mode == "RELEASE_PROJECTION" \
        else two_proportion_z(x_base, n_base, x_obs, n_obs)
    detected = (n_obs >= min_volume and rel >= rel_threshold and z >= z_threshold)
    seg_txt = ", ".join(f"{k}={v}" for k, v in segment.items())
    aid = "ANOM-" + hashlib.sha256(f"{metric}|{seg_txt}|{baseline_mode}".encode()).hexdigest()[:8].upper()
    rel_txt = "∞" if math.isinf(rel) else f"{rel:+.1%}"
    return Anomaly(
        anomaly_id=aid, metric=metric, segment=segment, baseline_mode=baseline_mode,
        baseline_value=round(base_rate, 4), observed_value=round(obs_rate, 4),
        relative_change=round(rel, 4) if not math.isinf(rel) else 999.0,
        z_score=round(z, 2) if not math.isinf(z) else 999.0, baseline_volume=n_base, observed_volume=n_obs,
        detected=detected,
        summary=f"{metric} [{seg_txt}] {base_rate:.2%} → {obs_rate:.2%} ({rel_txt}, z={z:.1f}) "
                f"vs {baseline_mode.replace('_', ' ').lower()}" + (" — ANOMALY DETECTED" if detected else ""),
    )


def detect_anomalies(ctx: ProductionContext, *, rel_threshold: float = 0.15, z_threshold: float = 3.0,
                     baseline_mode: str = "RELEASE_PROJECTION", min_volume: int = 100) -> list[Anomaly]:
    post = ctx.post
    if baseline_mode == "RELEASE_PROJECTION":
        base = ctx.expected[ctx.expected.service_date >= ctx.release_date]
    elif baseline_mode == "HISTORICAL":
        span = (post.service_date.max() - ctx.release_date).days if len(post) else 0
        start = ctx.release_date - timedelta(days=span + 1)
        base = ctx.pre[ctx.pre.service_date >= start]
    else:
        raise ValueError("baseline_mode must be RELEASE_PROJECTION or HISTORICAL")
    results: list[Anomaly] = []
    segments: list[tuple[dict, pd.Series, pd.Series]] = [({"benefit_type": "ALL"}, pd.Series(True, index=base.index),
                                                           pd.Series(True, index=post.index))]
    for bt in sorted(post.benefit_type.unique()):
        segments.append(({"benefit_type": bt}, base.benefit_type == bt, post.benefit_type == bt))
    for seg, bmask, pmask in segments:
        b, o = base[bmask], post[pmask]
        for metric, fn in METRICS.items():
            results.append(evaluate(metric, seg, baseline_mode, int(fn(b).sum()), len(b), int(fn(o).sum()), len(o),
                                    rel_threshold, z_threshold, min_volume))
    results.sort(key=lambda a: (not a.detected, -a.z_score))
    return results


def primary_anomaly(anomalies: list[Anomaly]) -> Anomaly | None:
    """Most significant detected anomaly in a specific benefit segment (prefer specific over ALL)."""
    detected = [a for a in anomalies if a.detected]
    specific = [a for a in detected if a.segment.get("benefit_type") != "ALL"]
    pool = specific or detected
    return max(pool, key=lambda a: a.z_score) if pool else None
