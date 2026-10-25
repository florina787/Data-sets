from fastapi.testclient import TestClient

from adapter.app import app
from adapter.auth import issue_demo_token

client = TestClient(app)


def test_missing_token_rejected():
    assert client.get("/v1/parts/P-7731/availability").status_code == 401


def test_wrong_audience_rejected():
    tok = issue_demo_token("tester", ["inventory.read"], aud="some-other-api")
    r = client.get("/v1/parts/P-7731/availability", headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 401 and r.json()["code"] == "wrong_audience"


def test_missing_scope_forbidden():
    tok = issue_demo_token("tester", ["workorder.write"])
    assert client.get("/v1/parts/P-7731/availability", headers={"Authorization": "Bearer " + tok}).status_code == 403


def test_tampered_token_rejected():
    tok = issue_demo_token("tester", ["inventory.read"])
    assert client.get("/v1/parts/P-7731/availability", headers={"Authorization": "Bearer " + tok[:-2] + "xx"}).status_code == 401


def test_injection_like_input_rejected():
    tok = {"Authorization": "Bearer " + issue_demo_token("tester", ["inventory.read"])}
    for bad in ["P-7731' OR '1'='1", "P-7731;DROP", "../etc/passwd"]:
        assert client.get(f"/v1/parts/{bad}/availability", headers=tok).status_code in (404, 422)


def test_write_methods_not_allowed():
    tok = {"Authorization": "Bearer " + issue_demo_token("tester", ["inventory.read"])}
    assert client.post("/v1/parts/P-7731/availability", headers=tok).status_code == 405
