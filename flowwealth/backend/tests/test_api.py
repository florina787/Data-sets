import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from flowwealth.contracts import utcnow


@pytest.fixture(scope="module")
def client(lake, tmp_path_factory):
    from flowwealth.api import app as mod
    art = tmp_path_factory.mktemp("art")
    (art / "rankings.json").write_text(json.dumps({"items": [], "data_status": "SYNTHETIC"}))
    mod.S.lake, mod.S.version, mod.S.artifacts, mod.S.reports = lake.root, "t1", art, art
    mod._lake_frames.cache_clear()
    return TestClient(mod.app)


def test_status_marks_synthetic_and_not_ready(client):
    r = client.get("/api/status").json()
    assert r["data_status"] == "SYNTHETIC" and r["live_feeds"] == []
    assert not any(v["ready"] for v in r["horizon_readiness"].values())


def test_overview_and_series(client):
    o = client.get("/api/market/overview").json()
    assert o["data_status"] == "SYNTHETIC" and len(o["gainers"]) == 5 and o["sectors"]
    s = client.get("/api/market/series", params={"ticker": "SYN0002", "range": "1M"}).json()
    assert 15 <= len(s["points"]) <= 25
    assert client.get("/api/market/series", params={"ticker": "NOPE"}).status_code == 404
    assert client.get("/api/market/series", params={"ticker": "SYN0002", "range": "10Y"}).status_code == 422


def test_missing_artifacts_404_and_rankings_disclaimer(client):
    assert client.get("/api/risk/crash").status_code == 404
    assert "not investment advice" in client.get("/api/rankings").json()["disclaimer"]


def test_risk_check_endpoint_rejects_synthetic(client):
    body = {"profile": {"user_id": "u", "horizon": "swing", "appetite": "aggressive", "capital": 1e5},
            "order": {"ticker": "A", "side": "buy", "qty": 10, "price": 10, "stop_price": 9, "sector": "T",
                      "adv_shares": 1e6, "daily_vol": 0.02, "data_status": "SYNTHETIC",
                      "data_timestamp": (utcnow() - timedelta(minutes=1)).isoformat(), "horizon": "swing"},
            "equity": 1e5, "peak_equity": 1e5, "day_start_equity": 1e5}
    r = client.post("/api/risk/check", json=body).json()
    assert r["verdict"] == "REJECT"
    body["order"]["data_status"] = "DELAYED"
    assert client.post("/api/risk/check", json=body).json()["verdict"] == "APPROVE"


def test_nan_is_serialised_as_null(client, tmp_path):
    from flowwealth.api import app as mod
    (mod.S.reports / "x.json").write_text('{"experiment": "x", "holdout": {"zero": {"ic": NaN}}}')
    r = client.get("/api/experiments")
    x = next(e for e in r.json()["experiments"] if e["experiment"] == "x")
    assert r.status_code == 200 and x["holdout"]["zero"]["ic"] is None
    s = client.get("/api/search", params={"q": "SYN000"})
    assert s.status_code == 200 and s.json()["results"]
