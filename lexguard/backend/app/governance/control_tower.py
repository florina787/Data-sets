"""Legal AI Control Tower metrics (synthetic history + live runs + live audit)."""

from __future__ import annotations

from collections import Counter

from app.audit import service as audit
from app.services.data_store import DataStore
from app.valueiq.service import _live_runs, aggregate


def metrics(store: DataStore) -> dict:
    runs = list(store.usage_runs) + _live_runs()
    clients = store.clients
    enabled = [m for m in store.matters.values() if clients[m.client_id].ai_policy.ai_allowed]
    restricted = [m for m in store.matters.values()
                  if not clients[m.client_id].ai_policy.ai_allowed or not clients[m.client_id].ai_policy.external_ai_allowed]
    completed = [r for r in runs if r["outcome"] != "BLOCKED"]
    assured = [r for r in completed if r.get("assurance") in ("PASS", "REVIEW", "FAIL", "REVIEW_REQUIRED")]
    agg = aggregate(completed)
    recent_security = audit.recent_events(limit=500)
    sec_types = Counter(e["event_type"] for e in recent_security if e["severity"] in ("WARNING", "CRITICAL"))
    return {
        "label": "Synthetic history (Apr-Sep 2026) combined with live demo activity.",
        "ai_enabled_matters": len(enabled), "ai_restricted_matters": len(restricted), "total_matters": len(store.matters),
        "active_ai_workflows": sum(1 for w in store.workflows.values() if w.status in ("PRODUCTION", "PILOT")),
        "provider_usage": dict(Counter(store.providers[r["provider_id"]].name if r.get("provider_id") in store.providers
                                       else "Deterministic workflow (no AI provider)" for r in completed)),
        "practice_adoption": {store.practices.get(k, "Unassigned"): v for k, v in Counter(r["practice_id"] for r in completed).items()},
        "assurance_pass_rate": round(sum(r["assurance"] == "PASS" for r in assured) / (len(assured) or 1), 3),
        "citation_failure_rate": round(sum(1 for r in completed if r.get("citation_failures", 0) > 0) / (len(completed) or 1), 3),
        "playbook_deviations": sum(r.get("playbook_deviations", 0) for r in completed),
        "policy_violations_blocked": sum(r.get("policy_violations_blocked", 0) for r in runs),
        "human_review_rate": round(sum(1 for r in completed if r.get("human_reviewed")) / (len(completed) or 1), 3),
        "estimated_hours_saved": agg["net_hours_saved"], "rework_hours": agg["rework_hours"],
        "high_risk_events": sum(1 for r in runs if r.get("high_risk")) + sum(sec_types.values()),
        "live_security_events": dict(sec_types),
        "matters": [{"matter_id": m.matter_id, "name": m.name, "client": clients[m.client_id].name,
                     "practice": store.practices[m.practice_id], "risk": m.risk_level,
                     "ai_status": ("AI PROHIBITED" if not clients[m.client_id].ai_policy.ai_allowed else
                                   "INTERNAL AI ONLY" if not clients[m.client_id].ai_policy.external_ai_allowed else
                                   "PERMITTED WITH CONTROLS")} for m in store.matters.values()],
    }
