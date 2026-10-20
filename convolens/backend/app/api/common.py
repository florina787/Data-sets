from __future__ import annotations

import json

from fastapi import Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Dataset
from app.models.schemas import Filters


def parse_filters(filters: str | None = Query(default=None, description="JSON-encoded Filters object")) -> Filters:
    if not filters:
        return Filters()
    try:
        return Filters(**json.loads(filters))
    except (ValueError, ValidationError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid filters: {exc}") from exc


def ready_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if ds.status != "ready":
        raise HTTPException(status_code=409, detail=f"Dataset is {ds.status}")
    return ds


def dataset_info(ds: Dataset) -> dict:
    m = ds.manifest or {}
    return {"id": ds.id, "name": ds.name, "kind": ds.kind, "synthetic": ds.synthetic, "status": ds.status,
            "source": ds.source, "active_analysis": ds.active_analysis,
            "imported_at": ds.imported_at.isoformat() if ds.imported_at else None,
            "conversations": (m.get("sampling") or {}).get("selected"),
            "eligible": (m.get("sampling") or {}).get("eligible"),
            "requested": (m.get("sampling") or {}).get("requested"),
            "time_range": None}
