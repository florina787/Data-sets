"""Direct access to registered analytical operations (used by dashboards) and dataset metadata."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.analytics.db import get_db
from app.analytics.query_registry import OperationError, catalog, run_operation
from app.analytics.time_windows import available_months, resolve_window
from app.config import get_settings
from app.labeling.taxonomy import PRODUCT_DOMAINS, TAXONOMY_VERSION, TOPICS
from app.schemas.analysis import Scope
from app.schemas.api_response import AnalyticsQuery

router = APIRouter(tags=["analytics"])


@router.post("/api/analytics/query")
def query(q: AnalyticsQuery) -> dict:
    s = get_settings()
    if q.dataset_mode != "original" and not s.enable_synthetic_demo:
        raise HTTPException(403, "Synthetic/combined dataset modes are disabled (ENABLE_SYNTHETIC_DEMO=false)")
    db = get_db()
    try:
        window = resolve_window(db, q.dataset_mode, q.window)
        scope = Scope(dataset_mode=q.dataset_mode, window=window, topics=q.topics, products=q.products, domains=q.domains,
                      agents=q.agents, sentiments=q.sentiments)
        return run_operation(db, q.operation, scope, q.params).model_dump()
    except (OperationError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/analytics/operations")
def operations() -> list[dict]:
    return catalog()


@router.get("/api/analytics/taxonomy")
def taxonomy() -> dict:
    db = get_db()
    months = available_months(db, "original")
    return {"version": TAXONOMY_VERSION, "topics": [{"id": t.id, "label": t.label, "description": t.description} for t in TOPICS.values()],
            "products": [{"product": p, "domain": d} for p, d in sorted(PRODUCT_DOMAINS.items())],
            "domains": sorted(set(PRODUCT_DOMAINS.values())), "months": months["month"].tolist()}


@router.get("/api/dataset/profile")
def dataset_profile() -> dict:
    s = get_settings()
    out = {}
    for name in ("data_profile", "data_quality_report", "dataset_manifest", "labelling_coverage"):
        f = s.manifests_dir / f"{name}.json"
        out[name] = json.loads(f.read_text()) if f.exists() else None
    return out


@router.get("/api/dataset/status")
def dataset_status() -> dict:
    db = get_db()
    meta = db.metadata()
    counts = db.query("SELECT dataset_source, COUNT(*) AS conversations, SUM(message_count) AS messages, "
                      "SUM((processing_status='labelled')::INT) AS labelled FROM conversations GROUP BY 1").to_dict("records")
    return {"built_at": meta["built_at"], "pipeline_version": meta["pipeline_version"], "taxonomy_version": meta["taxonomy_version"],
            "label_coverage": meta["label_coverage"], "sources": counts, "dataset_mode_default": get_settings().dataset_mode,
            "synthetic_enabled": get_settings().enable_synthetic_demo}


DASHBOARDS: dict[str, list[tuple[str, dict]]] = {
    "leadership": [("leadership_priorities", {"top_n": 5}), ("sentiment_trend", {}), ("resolution_quality", {}), ("sentiment_distribution", {})],
    "sentiment": [("rank_negative_topics", {"top_n": 8}), ("sentiment_distribution", {"group_by": "topic"}), ("sentiment_trend", {}),
                  ("topic_frequency", {"dimension": "domain"})],
    "coaching": [("agent_coaching_review", {"top_n": 12}), ("resolution_quality", {})],
}


class DashboardQuery(BaseModel):
    window: dict | None = None
    dataset_mode: Literal["original", "synthetic", "combined"] = "original"
    topics: list[str] = []


@router.post("/api/dashboards/{name}")
def dashboard(name: str, q: DashboardQuery) -> dict:
    """Run a fixed set of registered operations and return validated chart specs (same planner as chat)."""
    from app.visualization.planner import plan_charts

    if name not in DASHBOARDS:
        raise HTTPException(404, f"Unknown dashboard {name}")
    if q.dataset_mode != "original" and not get_settings().enable_synthetic_demo:
        raise HTTPException(403, "Synthetic/combined dataset modes are disabled")
    db = get_db()
    window = resolve_window(db, q.dataset_mode, q.window)
    scope = Scope(dataset_mode=q.dataset_mode, window=window, topics=q.topics)
    results = {op: run_operation(db, op, scope, params).model_dump() for op, params in DASHBOARDS[name]}
    charts, graphs = plan_charts(results, [], f"dash-{name}")
    return {"name": name, "scope": scope.model_dump(), "results": results, "charts": [c.model_dump() for c in charts],
            "graphs": [g.model_dump() for g in graphs]}
