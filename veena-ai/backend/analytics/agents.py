"""Agent scorecard: aggregates the per-turn spine traces into the numbers the Agents page shows."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from ..agents import spine
from ..memory.store import Store


def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 4) if xs else None


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _success(outcomes: Counter[str]) -> float | None:
    # Cancelled turns were stopped by the user, so they count neither way.
    decided = sum(n for o, n in outcomes.items() if o != "cancelled")
    return _rate(outcomes.get("resolved", 0), decided)


def scorecard(store: Store, days: int = 30, recent: int = 20) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)
    traces = list(reversed(store.traces(since=since)))  # oldest first
    outcomes: Counter[str] = Counter()
    trans: Counter[tuple[str, str]] = Counter()
    ont: Counter[str] = Counter()
    per_agent: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"turns": 0, "outcomes": Counter(), "support": [], "util": [], "cite": [], "adherent": 0, "ms": []}
    )
    daily: dict[str, dict[str, Any]] = defaultdict(lambda: {"outcomes": Counter(), "support": []})
    support, util, cite, ctx_nodes = [], [], [], []
    adherent = claims = unsupported_figs = 0
    latest_context = None
    for t in traces:
        m = json.loads(t.measures_json or "{}")
        k, c = m.get("knowledge", {}), m.get("context", {})
        outcomes[t.outcome] += 1
        a = per_agent[t.agent]
        a["turns"] += 1
        a["outcomes"][t.outcome] += 1
        a["adherent"] += int(t.adherent)
        adherent += int(t.adherent)
        if t.total_ms is not None:
            a["ms"].append(t.total_ms)
        for val, agg, own in (
            (t.support_rate, support, a["support"]),
            (t.utilization, util, a["util"]),
            (t.citation_rate, cite, a["cite"]),
        ):
            if val is not None:
                agg.append(val)
                own.append(val)
        claims += k.get("claims", 0)
        unsupported_figs += k.get("unsupported_figures", 0)
        ont.update({kind: n for kind, n in k.get("ontology", {}).items()})
        if c.get("nodes") is not None:
            ctx_nodes.append(c["nodes"])
        if c.get("graph", {}).get("nodes"):
            latest_context = {"graph": c["graph"], "sources": c.get("sources", []), "agent": t.agent, "at": t.created_at.isoformat()}
        for x, y in spine.transitions(json.loads(t.path_json or "[]"), t.outcome):
            trans[(x, y)] += 1
        day = daily[t.created_at.strftime("%Y-%m-%d")]
        day["outcomes"][t.outcome] += 1
        if t.support_rate is not None:
            day["support"].append(t.support_rate)

    def recent_row(t) -> dict[str, Any]:
        m = json.loads(t.measures_json or "{}")
        return {
            "id": t.id,
            "session_id": t.session_id,
            "agent": t.agent,
            "mode": t.mode,
            "outcome": t.outcome,
            "adherent": t.adherent,
            "path": json.loads(t.path_json or "[]"),
            "support_rate": t.support_rate,
            "utilization": t.utilization,
            "citation_rate": t.citation_rate,
            "unsupported": m.get("knowledge", {}).get("unsupported", []),
            "total_ms": t.total_ms,
            "at": t.created_at.isoformat(),
        }

    n = len(traces)
    return {
        "days": days,
        "turns": n,
        "outcomes": {o: outcomes.get(o, 0) for o in spine.OUTCOMES},
        "success_rate": _success(outcomes),
        "ontology": {kind: ont.get(kind, 0) for kind in spine.ENTITY_TYPES},
        "knowledge": {
            "support_rate": _mean(support),
            "measured_turns": len(support),
            "claims": claims,
            "unsupported_figures": unsupported_figs,
        },
        "context": {"utilization": _mean(util), "citation_rate": _mean(cite), "mean_nodes": _mean(ctx_nodes), "latest": latest_context},
        "procedure": {
            "adherence": _rate(adherent, n),
            "graph": spine.PROCEDURE,
            "labels": spine.STEP_LABELS,
            "transitions": [{"from": a, "to": b, "count": c} for (a, b), c in trans.most_common()],
        },
        "agents": [
            {
                "agent": name,
                "turns": a["turns"],
                "outcomes": dict(a["outcomes"]),
                "success_rate": _success(a["outcomes"]),
                "support_rate": _mean(a["support"]),
                "utilization": _mean(a["util"]),
                "citation_rate": _mean(a["cite"]),
                "adherence": _rate(a["adherent"], a["turns"]),
                "p50_ms": round(statistics.median(a["ms"]), 1) if a["ms"] else None,
            }
            for name, a in sorted(per_agent.items(), key=lambda kv: -kv[1]["turns"])
        ],
        "daily": [
            {"day": d, "turns": sum(v["outcomes"].values()), "success_rate": _success(v["outcomes"]), "support_rate": _mean(v["support"])}
            for d, v in sorted(daily.items())
        ],
        "recent": [recent_row(t) for t in store.traces(since=since, limit=recent)],
    }
