"""ValueIQ - deterministic business-value estimates. ALL FIGURES ARE SYNTHETIC ESTIMATES."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.models.db import WorkflowRunRow, session
from app.services.data_store import DataStore

BLENDED_RATE_USD = 450.0  # synthetic blended hourly rate
HOURS_PER_UNIT = {"WF-DD-COC": 0.25, "WF-CONTRACT-SUMMARY": 0.75, "WF-PLAYBOOK-CHECK": 0.4, "WF-RESEARCH-INT": 2.0,
                  "WF-KNOWLEDGE-QA": 0.5}
LABEL = "Synthetic estimate - illustrative only, not actual time-recording data."


def estimate_run(workflow_id: str | None, units: int, review_items: int = 0, deviations: int = 0) -> dict:
    """Per-request estimate used by the Copilot (deterministic)."""
    per_unit = HOURS_PER_UNIT.get(workflow_id or "", 0.5)
    traditional = round(units * per_unit, 2)
    ai_proc = round(min(traditional, 0.002 * units + 0.05), 2) if units else 0.0
    review = round(0.1 * review_items + 0.25 * deviations, 2)
    rework = 0.0
    net = round(max(0.0, traditional - ai_proc - review - rework), 2)
    return {"traditional_hours": traditional, "ai_processing_hours": ai_proc, "lawyer_review_hours": review,
            "rework_hours": rework, "net_hours_saved": net, "estimated_value_usd": round(net * BLENDED_RATE_USD, 2),
            "label": LABEL}


def _live_runs() -> list[dict]:
    with session() as s:
        rows = s.execute(select(WorkflowRunRow)).scalars().all()
    out = []
    for r in rows:
        v = (r.metrics or {}).get("value") or {}
        if not v:
            continue
        out.append({"run_id": r.run_id, "workflow_id": r.workflow_id, "matter_id": r.matter_id, "practice_id": r.practice_id,
                    "provider_id": r.provider_id, "traditional_hours": v.get("traditional_hours", 0),
                    "ai_processing_hours": v.get("ai_processing_hours", 0), "lawyer_review_hours": v.get("lawyer_review_hours", 0),
                    "rework_hours": v.get("rework_hours", 0), "outcome": "COMPLETED" if r.status != "BLOCKED" else "BLOCKED",
                    "assurance": (r.metrics or {}).get("assurance_status", "N/A"), "est_cost_usd": r.est_cost_usd,
                    "citation_failures": (r.metrics or {}).get("citation_issues", 0),
                    "playbook_deviations": (r.metrics or {}).get("playbook_deviations", 0),
                    "policy_violations_blocked": 1 if r.status in ("BLOCKED", "ACCESS_DENIED") else 0,
                    "human_reviewed": True, "high_risk": r.status in ("BLOCKED", "ACCESS_DENIED"), "live": True})
    return out


def aggregate(runs: list[dict]) -> dict:
    n = len(runs) or 1
    trad = sum(r["traditional_hours"] for r in runs)
    ai = sum(r["ai_processing_hours"] for r in runs)
    review = sum(r["lawyer_review_hours"] for r in runs)
    rework = sum(r["rework_hours"] for r in runs)
    net = trad - ai - review - rework
    assured = [r for r in runs if r.get("assurance") not in (None, "N/A")]
    return {
        "runs": len(runs),
        "traditional_hours": round(trad, 1), "ai_processing_hours": round(ai, 1), "lawyer_review_hours": round(review, 1),
        "rework_hours": round(rework, 1), "net_hours_saved": round(net, 1),
        "estimated_workflow_cost_usd": round(sum(r.get("est_cost_usd", 0) for r in runs), 2),
        "estimated_value_usd": round(net * BLENDED_RATE_USD, 0),
        "productivity_improvement_pct": round(100 * net / trad, 1) if trad else 0.0,
        "completion_rate": round(sum(r["outcome"] == "COMPLETED" for r in runs) / n, 3),
        "abandonment_rate": round(sum(r["outcome"] == "ABANDONED" for r in runs) / n, 3),
        "human_override_rate": round(sum(r["outcome"] == "OVERRIDDEN" for r in runs) / n, 3),
        "assurance_failure_rate": round(sum(r.get("assurance") == "FAIL" for r in assured) / (len(assured) or 1), 3),
    }


def metrics(store: DataStore, include_live: bool = True) -> dict:
    runs = [r for r in store.usage_runs if r["outcome"] != "BLOCKED"]
    if include_live:
        runs += [r for r in _live_runs() if r["outcome"] != "BLOCKED"]
    groups: dict[str, dict[str, list]] = {k: defaultdict(list) for k in ("matter", "practice", "workflow", "provider")}
    for r in runs:
        groups["matter"][r["matter_id"]].append(r)
        groups["practice"][r["practice_id"]].append(r)
        groups["workflow"][r["workflow_id"]].append(r)
        groups["provider"][r["provider_id"] or "NONE"].append(r)

    def named(kind: str, key: str) -> str:
        if kind == "matter":
            return store.matters[key].name if key in store.matters else key
        if kind == "practice":
            return store.practices.get(key, key)
        if kind == "workflow":
            return store.workflows[key].name if key in store.workflows else key
        return store.providers[key].name if key in store.providers else "Deterministic workflow (no AI provider)"

    return {
        "label": LABEL, "blended_rate_usd": BLENDED_RATE_USD,
        "totals": aggregate(runs),
        "by": {kind: sorted([{"id": k, "name": named(kind, k), **aggregate(v)} for k, v in g.items()],
                            key=lambda x: -x["net_hours_saved"]) for kind, g in groups.items()},
        "formula": "net_hours_saved = traditional_hours - ai_processing_hours - lawyer_review_hours - rework_hours; "
                   "estimated_value = net_hours_saved x blended_rate",
    }
