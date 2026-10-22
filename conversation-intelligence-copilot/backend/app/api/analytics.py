"""Direct access to registered analytical operations (used by dashboards) and dataset metadata."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

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
