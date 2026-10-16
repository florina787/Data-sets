"""Synthetic patient-search simulation with deterministic ground truth.

Each simulated search runs the real pipeline under the build being evaluated and
again under the correct (ground-truth) mapping. Accuracy compares the two.
Telemetry emitted here is flagged ``synthetic=True`` everywhere it is displayed.
"""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime

from app.governance import builds
from app.schemas.domain import IMAGING, LAB, RequisitionStatus, ServiceType
from app.services import eligibility as elig
from app.services.gazetteer import CITY_CENTROIDS, FSA_CENTROIDS
from app.services.search_engine import PipelineInput, run_pipeline
from app.services.synthetic import generate_dataset
from app.telemetry import metrics as tm

SERVICES = [ServiceType.MRI, ServiceType.CT, ServiceType.ULTRASOUND, ServiceType.XRAY, ServiceType.BLOOD_TEST,
            ServiceType.SPECIALIST, ServiceType.FAMILY_PHYSICIAN]
LOCATIONS = list(CITY_CENTROIDS.values())[:18] + list(FSA_CENTROIDS.values())[:10]


def simulate(volume: int = 200, build_version: str | None = None, env: str = builds.PATIENT_ENV, seed: int = 7,
             outage_rate: float = 0.05, now: datetime | None = None, emit_telemetry: bool = True,
             sample_limit: int = 15) -> dict:
    volume = max(1, min(int(volume), 5000))
    b = builds.BUILDS[build_version] if build_version else builds.active_build(env)
    now = now or datetime.now(UTC)
    ds = generate_dataset(now.replace(minute=0, second=0, microsecond=0))
    rng = random.Random(seed)
    stats = {"searches": 0, "with_eligible_alternative": 0, "total_days_saved": 0, "verification_failures": 0,
             "api_failures": 0, "source_calls": 0, "recommendations": 0, "misclassified": 0,
             "top_choice_matches": 0, "unverified_presented_as_confirmed": 0}
    samples: list[dict] = []
    t0 = time.perf_counter()
    for i in range(volume):
        svc = rng.choice(SERVICES)
        lat, lon = rng.choice(LOCATIONS)
        req = rng.choices([RequisitionStatus.HAS_REQUISITION, RequisitionStatus.UNKNOWN,
                           RequisitionStatus.NO_REQUISITION], [0.7, 0.2, 0.1])[0]
        if svc not in IMAGING and svc not in LAB and svc != ServiceType.SPECIALIST:
            req = RequisitionStatus.UNKNOWN
        inp = PipelineInput(service=svc, latitude=lat, longitude=lon, radius_km=rng.choice([5, 10, 25, 25, 50]),
                            existing_days=rng.randint(20, 120),
                            criteria=elig.PatientCriteria(requisition_status=req,
                                                          include_private_pay=rng.random() < 0.15))
        fail = {"INT-SYN-NORTH"} if rng.random() < outage_rate else set()
        out = run_pipeline(inp, ds, now, b.status_mapping, fail_sources=fail)
        truth = run_pipeline(inp, ds, now, "correct", fail_sources=fail)
        truth_status = {v.slot_id: v.verification_status for v in truth.verified}
        stats["searches"] += 1
        stats["source_calls"] += 1 + len(out.failed_sources)
        stats["api_failures"] += len(out.failed_sources)
        stats["recommendations"] += len(out.recommendations)
        mis = [r for r in out.recommendations if r.verification_status != truth_status.get(r.slot_id)]
        bad_conf = [r for r in out.recommendations if r.tier == "CONFIRMED_ALTERNATIVE"
                    and truth_status.get(r.slot_id) != "VERIFIED_AVAILABLE"]
        stats["misclassified"] += len(mis)
        stats["unverified_presented_as_confirmed"] += len(bad_conf)
        stats["verification_failures"] += sum(1 for v in out.verified if v.verification_status.value in
                                              ("UNKNOWN", "ADVERTISED_UNVERIFIED"))
        top = next((r.slot_id for r in out.recommendations if r.tier == "CONFIRMED_ALTERNATIVE"), None)
        top_truth = next((r.slot_id for r in truth.recommendations if r.tier == "CONFIRMED_ALTERNATIVE"), None)
        stats["top_choice_matches"] += int(top == top_truth)
        if out.wait_summary["confirmed_count"]:
            stats["with_eligible_alternative"] += 1
            stats["total_days_saved"] += out.wait_summary["potential_days_saved"] or 0
        if emit_telemetry:
            tm.STORE.add("sim_misclassification_rate", len(mis) / max(1, len(out.recommendations)),
                         {"build": b.version, "env": env}, synthetic=True)
            tm.STORE.add("sim_unverified_as_confirmed", len(bad_conf), {"build": b.version, "env": env}, synthetic=True)
            tm.STORE.add("sim_api_failure", 1 if out.failed_sources else 0, {"build": b.version}, synthetic=True)
            tm.STORE.add("sim_confirmed_results", out.wait_summary["confirmed_count"], {"build": b.version},
                         synthetic=True)
        if bad_conf and len(samples) < sample_limit:
            r = bad_conf[0]
            v = next(x for x in out.verified if x.slot_id == r.slot_id)
            samples.append({"trace_ref": f"SIM-{seed}-{i:04d}", "slot_id": r.slot_id, "facility_id": r.facility_id,
                            "source_status": v.source_status.value, "reported_status": r.verification_status.value,
                            "expected_status": truth_status[r.slot_id].value, "build": b.version,
                            "verification_reasons": v.verification_reasons})
    n = stats["searches"]
    recs = max(1, stats["recommendations"])
    return {
        "synthetic": True, "build_version": b.version, "environment": env, "volume": n, "seed": seed,
        "outage_rate": outage_rate, "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        "searches": n, "searches_with_eligible_alternative": stats["with_eligible_alternative"],
        "avg_potential_days_saved": round(stats["total_days_saved"] / max(1, stats["with_eligible_alternative"]), 2),
        "verification_failures": stats["verification_failures"], "api_failures": stats["api_failures"],
        "api_failure_rate": round(stats["api_failures"] / max(1, stats["source_calls"]), 4),
        "recommendations": stats["recommendations"],
        "misclassified_recommendations": stats["misclassified"],
        "unverified_presented_as_confirmed": stats["unverified_presented_as_confirmed"],
        "recommendation_accuracy": round(1 - stats["misclassified"] / recs, 4),
        "top_choice_accuracy": round(stats["top_choice_matches"] / n, 4),
        "ground_truth": "Same pipeline with the specification status mapping (build 1.4.0 rules).",
        "samples": samples,
    }
