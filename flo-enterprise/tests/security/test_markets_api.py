"""Market REST endpoints: authentication, deny-by-default authorization (audited) and input validation."""
import pytest
from fastapi.testclient import TestClient

from markets import service as S


@pytest.fixture(scope="module")
def client(st):
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def H(client):
    return lambda u: {"Authorization": "Bearer " + client.post("/api/auth/login", json={"user_id": u}).json()["access_token"]}


def test_requires_authentication(client):
    assert client.get("/api/markets/status").status_code == 401


def test_market_read_is_denied_without_permission(client, H):
    r = client.get("/api/markets/status", headers=H("u-compliance"))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "POLICY-DENIED"


def test_model_research_needs_quant_read(client, H):
    assert client.get("/api/markets/research", headers=H("u-prospect")).status_code == 403
    assert client.get("/api/markets/predictions", headers=H("u-external")).status_code == 403


def test_status_reports_feed_disabled_and_profiles(client, H):
    d = client.get("/api/markets/status", headers=H("u-prospect")).json()
    assert d["current_feed"]["scheduler_enabled"] is False and d["profiles"]["speeds"]["swift"]["supported"] is False


def test_invalid_inputs_rejected(client, H):
    h = H("u-cio")
    assert client.get("/api/markets/security/drop%20table", headers=h).status_code == 422
    assert client.get("/api/markets/compare?tickers=AAPL", headers=h).status_code == 422
    assert client.get("/api/markets/risk/AAPL?speed=hft", headers=h).status_code == 422


@pytest.mark.skipif(not S.available(), reason="real Kaggle market lake not built here")
def test_real_data_endpoints(client, H):
    h = H("u-cio")
    d = client.get("/api/markets/security/AAPL", headers=h).json()
    assert d["data_status"] == "historical" and d["as_of"] == "2017-11-10" and d["series"]
    assert client.get("/api/markets/research", headers=h).json()["verdict"] == "NO VALIDATED TRADING EDGE"
    assert client.get("/api/markets/risk/NVDA?speed=intraday", headers=h).json()["status"] == "unsupported_mode"
