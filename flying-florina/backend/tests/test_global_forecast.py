"""Flying Florina 3.0 forecasting, map, twin, supply-chain and resilience tests."""

import pytest

from app.global_intel import dataset as ds
from app.global_intel import simulate as sim
from app.global_intel.forecast import HORIZONS_DAYS, TEST_WEEKS, engine
from tests.conftest import login


@pytest.fixture(scope="module")
def e():
    return engine()


def test_dataset_is_reproducible_and_referentially_consistent(e):
    from app.core import db

    assert db.query_one("SELECT value FROM meta WHERE key='global_dataset'")["value"] == f"{ds.DATASET_VERSION}:{ds.GLOBAL_SEED}"
    orphans = db.query_one("SELECT COUNT(*) n FROM g_units u LEFT JOIN g_facilities f ON f.id = u.facility_id WHERE f.id IS NULL")
    assert orphans["n"] == 0
    bad_links = db.query_one("SELECT COUNT(*) n FROM g_supply_links l LEFT JOIN g_categories c ON c.id = l.category_id WHERE c.id IS NULL")
    assert bad_links["n"] == 0
    assert db.query_one("SELECT COUNT(*) n FROM g_unit_weeks WHERE health IS NULL")["n"] > 0  # missing-data scenario present
    assert len(e.fac) == 12 and len(e.sup) == 8 and len(e.cat) == 20


def test_demand_split_is_temporal_and_beats_moving_average_at_long_horizons(e):
    m = e.metrics["demand"]["by_horizon"]
    for d in HORIZONS_DAYS:
        r = m[f"{d}d"]
        assert r["train_rows"] > 0 and r["test_rows"] > 0 and r["calibration_rows"] > 0
        assert 0 <= r["coverage_80"] <= 1
    assert m["90d"]["mae"] < m["90d"]["baseline_moving_average"]["mae"]
    assert str(ds.N_WEEKS - TEST_WEEKS) in e.metrics["demand"]["split"]


def test_forecast_quantiles_are_ordered_and_cumulative(e):
    for fc in e.demand_fc.values():
        prev = 0.0
        for d in HORIZONS_DAYS:
            lo, mid, hi = fc[d]
            assert 0 <= lo <= mid <= hi
            assert mid >= prev - 1e-6
            prev = mid


def test_models_are_reproducible(e):
    from app.global_intel.forecast import Engine

    again = Engine().build()
    assert again.metrics["demand"]["by_horizon"]["30d"]["mae"] == e.metrics["demand"]["by_horizon"]["30d"]["mae"]
    k = next(iter(e.inventory))
    assert again.inventory[k] == e.inventory[k]


def test_classifier_and_anomaly_metrics_are_reported_with_baselines(e):
    r = e.metrics["failure_risk_30d"]
    assert {"precision", "recall", "f1"} <= set(r["model_at_0.5"]) and "ece" in r["calibration"]
    assert "baseline_health_below_0.35" in r
    a = e.metrics["anomaly"]
    assert "baseline_zscore_gt3" in a and "isolation_forest" in a
    assert e.metrics["rul"]["units_scored"] > 20


def test_supplier_delay_raises_stockout_risk_and_transfer_mitigates(e):
    base = sim.delay_impact(e, "S1", 0, 60)
    late = sim.delay_impact(e, "S1", 14, 60)
    b = {s["scenario"]: s for s in base["scenarios"]}
    t = {s["scenario"]: s for s in late["scenarios"]}
    assert t["delay"]["deferred_maintenance_hours"] > b["delay"]["deferred_maintenance_hours"]
    assert t["transfer"]["deferred_maintenance_hours"] <= t["delay"]["deferred_maintenance_hours"]
    assert {r["category_id"] for r in late["rows"]} <= {lk["category_id"] for lk in e.links if lk["supplier_id"] == "S1"}


def test_resilience_baseline_disruption_recovery(e):
    r = sim.resilience(e, "facility_outage", {"facility_id": "F01", "capacity_cut": 0.6})
    res = r["results"]
    assert res["disruption"]["peak_backlog_hours"] > res["baseline"]["peak_backlog_hours"]
    assert res["recovery"]["peak_backlog_hours"] <= res["disruption"]["peak_backlog_hours"]
    assert r["assumptions"]


def test_global_api_map_timeline_twin_and_report(client):
    h = login(client, "planner.marco")
    m = client.get("/api/global/map?horizon=60", headers=h).json()["data"]
    assert m["horizon_days"] == 60 and len(m["facilities"]) == 12 and m["freshness"]["synthetic"] is True
    tl = client.get("/api/global/timeline", headers=h).json()["data"]
    assert set(tl) == {"0", "7", "14", "30", "60", "90"}
    hyd = client.get("/api/forecast/components?horizon=60&category=hydraulic_pump&region=Europe", headers=h).json()["data"]
    assert hyd["rows"][0]["category_id"] == "hydraulic_pump"
    units = client.get("/api/twin/units", headers=h).json()["data"]
    t = client.get(f"/api/twin/{units[0]['id']}", headers=h).json()["data"]
    assert t["telemetry"] and "Advisory only" in " ".join(t["assumptions"])
    rep = client.get("/api/global/report?horizon=30", headers=h)
    assert rep.status_code == 200 and "SYNTHETIC" in rep.text
    assert client.get("/api/global/search?q=hamburg", headers=h).json()["data"][0]["id"] == "F01"


def test_guest_cannot_run_simulations(client):
    g = login(client, "guest")
    r = client.post("/api/resilience/simulate", json={"scenario": "facility_outage"}, headers=g)
    assert r.status_code == 403
