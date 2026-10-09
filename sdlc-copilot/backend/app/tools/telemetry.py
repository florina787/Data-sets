"""Telemetry ingestion and deterministic queries over storefront JSONL events."""

from __future__ import annotations

import json
import math

from app.config import get_settings
from app.db import kv_get, kv_set, rows, session

OFFSET_KEY = "telemetry.offset"
FIELDS = ("event_id", "ts", "kind", "revision", "release_id", "route", "method", "status", "error",
          "dependency", "operation", "outcome", "latency_ms")


def ingest() -> int:
    """Copy new JSONL lines into SQLite. Returns the number of events ingested."""
    path = get_settings().telemetry_file
    if not path.exists():
        return 0
    offset = kv_get(OFFSET_KEY, 0)
    if path.stat().st_size < offset:
        offset = 0  # file was reset
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read()
    complete = data[: data.rfind(b"\n") + 1]
    events = []
    for line in complete.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(tuple(event.get(f) for f in FIELDS))
    if events:
        with session() as conn:
            conn.executemany(
                f"INSERT OR IGNORE INTO telemetry_events ({', '.join(FIELDS)})"
                f" VALUES ({', '.join('?' * len(FIELDS))})",
                events,
            )
    kv_set(OFFSET_KEY, offset + len(complete))
    return len(events)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(p / 100 * len(ordered)) - 1)
    return round(ordered[index], 1)


def summary(since: str | None = None, revision: str | None = None) -> dict:
    """Request and dependency statistics computed from recorded events only."""
    ingest()
    clauses, params = ["1 = 1"], []
    if since:
        clauses.append("ts >= ?")
        params.append(since)
    if revision:
        clauses.append("revision = ?")
        params.append(revision)
    where = " AND ".join(clauses)
    requests = rows(f"SELECT * FROM telemetry_events WHERE kind = 'request' AND {where}", tuple(params))
    deps = rows(f"SELECT * FROM telemetry_events WHERE kind = 'dependency' AND {where}", tuple(params))
    checkout = [r for r in requests if r["route"] and r["route"].endswith("/checkout")]
    by_route: dict[str, dict] = {}
    for r in requests:
        bucket = by_route.setdefault(r["route"] or "?", {"count": 0, "errors_5xx": 0, "latencies": []})
        bucket["count"] += 1
        bucket["errors_5xx"] += int((r["status"] or 0) >= 500)
        bucket["latencies"].append(r["latency_ms"] or 0)
    routes = [
        {"route": k, "count": v["count"], "errors_5xx": v["errors_5xx"],
         "p95_ms": percentile(v["latencies"], 95)}
        for k, v in sorted(by_route.items())
    ]
    dep_ops: dict[str, dict] = {}
    for d in deps:
        key = f"{d['dependency']}.{d['operation']}"
        bucket = dep_ops.setdefault(key, {"count": 0, "errors": 0, "latencies": [], "error_types": {}})
        bucket["count"] += 1
        if d["outcome"] != "ok":
            bucket["errors"] += 1
            bucket["error_types"][d["error"]] = bucket["error_types"].get(d["error"], 0) + 1
        bucket["latencies"].append(d["latency_ms"] or 0)
    dependencies = [
        {"operation": k, "count": v["count"], "errors": v["errors"], "error_types": v["error_types"],
         "p95_ms": percentile(v["latencies"], 95), "max_ms": max(v["latencies"]) if v["latencies"] else None}
        for k, v in sorted(dep_ops.items())
    ]
    checkout_5xx = sum(1 for r in checkout if (r["status"] or 0) >= 500)
    return {
        "requests": len(requests),
        "checkout_requests": len(checkout),
        "checkout_5xx": checkout_5xx,
        "checkout_503": sum(1 for r in checkout if r["status"] == 503),
        "checkout_error_rate": round(checkout_5xx / len(checkout), 3) if checkout else None,
        "checkout_p95_ms": percentile([r["latency_ms"] or 0 for r in checkout], 95),
        "routes": routes,
        "dependencies": dependencies,
    }


def timeline(limit: int = 200, since: str | None = None) -> list[dict]:
    ingest()
    if since:
        return rows("SELECT * FROM telemetry_events WHERE ts >= ? ORDER BY ts DESC LIMIT ?", (since, limit))
    return rows("SELECT * FROM telemetry_events ORDER BY ts DESC LIMIT ?", (limit,))
