"""Production Monitoring Agent: deterministic-threshold anomaly detection."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

from app.governance import audit
from app.harness.core import new_id
from app.telemetry import metrics as tm

# rule id -> (metric, aggregation, threshold, severity, component, synthetic?, investigation)
RULES = [
    ("VERIFICATION_MISCLASSIFICATION", "sim_misclassification_rate", "mean", 0.01, "CRITICAL",
     "availability_verification", True,
     "Compare status mapping of the active build against the specification; inspect failing regression tests."),
    ("UNVERIFIED_AS_CONFIRMED", "sim_unverified_as_confirmed", "sum", 0, "CRITICAL", "recommendation", True,
     "Unverified slots are being presented as confirmed alternatives. Halt rollout and investigate."),
    ("API_FAILURE_SPIKE", "sim_api_failure", "mean", 0.15, "HIGH", "availability_search", True,
     "Check provider integration health and circuit-breaker state."),
    ("REAL_TOOL_FAILURE_RATE", "tool_call", "failure_rate", 0.2, "HIGH", "harness", False,
     "Inspect tool_executions for the failing tool and integration_errors."),
    ("RETRY_RATE", "retries", "count", 25, "MEDIUM", "recovery", False, "Investigate retry storms / rate limits."),
    ("DATA_FRESHNESS", "data_age_hours_median", "last", 6.0, "MEDIUM", "data_quality", False,
     "Median availability record age exceeds the verification freshness limit."),
    ("LATENCY", "workflow_latency_ms", "p95", 3000.0, "MEDIUM", "api", False, "Profile slow agents."),
    ("TOKEN_SPIKE", "llm_tokens", "max", 5000, "MEDIUM", "llm", False, "Check prompt sizes and caching."),
]

_lock = threading.Lock()
_anomalies: list[dict] = []


def _value(metric: str, agg: str, since: float | None, synthetic: bool | None) -> tuple[float | None, int]:
    rows = tm.STORE.series(metric, since, synthetic)
    if not rows:
        return None, 0
    vals = [r[1] for r in rows]
    if agg == "mean":
        return sum(vals) / len(vals), len(vals)
    if agg == "sum":
        return sum(vals), len(vals)
    if agg == "count":
        return float(len(vals)), len(vals)
    if agg == "last":
        return vals[-1], len(vals)
    if agg == "max":
        return max(vals), len(vals)
    if agg == "p95":
        s = sorted(vals)
        return s[min(len(s) - 1, int(0.95 * (len(s) - 1) + 0.5))], len(vals)
    if agg == "failure_rate":
        return 1 - sum(vals) / len(vals), len(vals)
    raise ValueError(agg)


def detect(since: float | None = None, min_samples: int = 5, labels_filter: dict | None = None) -> list[dict]:
    found = []
    for rid, metric, agg, thr, sev, comp, synth, inv in RULES:
        if labels_filter and synth:
            rows = [r for r in tm.STORE.series(metric, since, True)
                    if all(r[2].get(k) == v for k, v in labels_filter.items())]
            vals = [r[1] for r in rows]
            n = len(vals)
            val = (sum(vals) / n if agg == "mean" else sum(vals)) if n else None
        else:
            val, n = _value(metric, agg, since, True if synth else False)
        if val is None or n < min_samples or val <= thr:
            continue
        a = {"id": new_id("ANM"), "rule": rid, "detected_at": datetime.now(UTC).isoformat(),
             "component": comp, "severity": sev, "metric": metric, "aggregation": agg, "value": round(val, 4),
             "threshold": thr, "samples": n, "synthetic_telemetry": synth,
             "evidence": f"{agg}({metric})={val:.4f} over {n} samples exceeds threshold {thr}",
             "recommended_investigation": inv, "resolution_status": "OPEN", "labels": labels_filter or {}}
        found.append(a)
    with _lock:
        _anomalies.extend(found)
    for a in found:
        audit.record("ANOMALY_DETECTED", "sdlc_monitoring", {"rule": a["rule"], "severity": a["severity"],
                                                             "value": a["value"]}, severity="WARNING")
    return found


def resolve(rule: str, note: str) -> int:
    n = 0
    with _lock:
        for a in _anomalies:
            if a["rule"] == rule and a["resolution_status"] == "OPEN":
                a["resolution_status"], a["resolution_note"] = "RESOLVED", note
                n += 1
    return n


def list_anomalies() -> list[dict]:
    with _lock:
        return list(reversed(_anomalies))


def health_snapshot(since: float | None = None) -> dict:
    since = since or time.time() - 3600
    return {
        "measured": {k: tm.STORE.summary(k, since, False) for k in
                     ("workflow_latency_ms", "agent_latency_ms", "agent_success", "tool_call", "retries",
                      "verification_rate", "data_age_hours_median", "llm_tokens", "days_saved", "booking_handoff",
                      "search_request", "http_latency_ms")},
        "synthetic": {k: tm.STORE.summary(k, since, True) for k in
                      ("sim_misclassification_rate", "sim_unverified_as_confirmed", "sim_api_failure",
                       "sim_confirmed_results")},
        "infrastructure": tm.infrastructure_snapshot(),
    }
