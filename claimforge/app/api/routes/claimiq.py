"""ClaimIQ endpoints: production metrics, anomaly detection, investigation, defects, traceability."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import AnomalyIn, InvestigateIn
from app.services.platform import get_platform
from app.utils.serialize import to_jsonable

router = APIRouter(tags=["claimiq"])


@router.get("/claimiq/metrics")
def claimiq_metrics(since_release: bool = True) -> dict:
    return to_jsonable(get_platform().claimiq_metrics(since_release))


@router.post("/claimiq/detect-anomaly")
def detect_anomaly(body: AnomalyIn) -> dict:
    return to_jsonable(get_platform().detect_anomaly(body.relative_threshold, body.z_threshold, body.baseline_mode))


@router.post("/claimiq/investigate")
def investigate(body: InvestigateIn) -> dict:
    st = get_platform().investigate(body.max_agent_iterations, body.persona)
    keys = ["request_id", "status", "anomaly", "root_cause", "root_cause_stop_reason", "release_correlation",
            "remediation", "regression", "defect", "feedback", "observability"]
    out = {k: st.get(k) for k in keys if st.get(k) is not None}
    if "anomaly" in out:
        out["anomaly"] = {**out["anomaly"], "anomalies": out["anomaly"]["anomalies"][:8]}
    return to_jsonable(out)


@router.post("/defects/generate")
def defects_generate() -> dict:
    p = get_platform()
    if not p.defects:
        p.investigate()
    if not p.defects:
        raise HTTPException(status_code=409, detail="No concluded investigation; no defect generated (nothing fabricated).")
    return to_jsonable({"defects": list(p.defects.values()), "status": "MOCKED tracker (in-memory)"})


@router.get("/traceability/{node_id}")
def traceability(node_id: str) -> dict:
    if len(node_id) > 64:
        raise HTTPException(status_code=400, detail="invalid id")
    return to_jsonable(get_platform().traceability(node_id))
