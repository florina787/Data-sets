"""Performance smoke tests. Thresholds are generous regression guards measured on this
machine, not capacity claims. See docs/deployment/capacity-planning.md and the load script."""

import time
from datetime import UTC, datetime

import pytest

from app.sdlc_engine import simulation
from app.services.workflows import SearchParams, start_search

pytestmark = pytest.mark.performance


def test_workflow_latency_budget():
    now = datetime(2026, 10, 16, 14, 0, tzinfo=UTC)
    durs = []
    for _ in range(5):
        t0 = time.perf_counter()
        r = start_search(SearchParams(service="MRI", location="Toronto", requisition_status="HAS_REQUISITION"),
                         "usr-patient-demo", "patient", now=now)
        durs.append(time.perf_counter() - t0)
        assert r["workflow_status"] == "COMPLETED"
    assert sorted(durs)[len(durs) // 2] < 2.0, durs


def test_simulation_throughput():
    t0 = time.perf_counter()
    res = simulation.simulate(200, "1.4.0", emit_telemetry=False)
    assert res["searches"] == 200 and time.perf_counter() - t0 < 30
