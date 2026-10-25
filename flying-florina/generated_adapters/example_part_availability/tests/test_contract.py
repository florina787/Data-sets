import json
from pathlib import Path

from fastapi.testclient import TestClient

from adapter.app import app
from adapter.auth import issue_demo_token
from adapter.models import PartAvailability

client = TestClient(app)
TOKEN = {"Authorization": "Bearer " + issue_demo_token("tester", ["inventory.read"])}


def test_get_known_part_matches_contract():
    r = client.get("/v1/parts/P-7731/availability", headers=TOKEN)
    assert r.status_code == 200
    body = PartAvailability.model_validate(r.json())
    assert body.part_number == "P-7731"
    assert body.synthetic is True
    assert all(loc.quantity_on_hand >= 0 for loc in body.locations)


def test_stale_critical_count_is_not_verified():
    body = client.get("/v1/parts/P-7731/availability", headers=TOKEN).json()
    main = [loc for loc in body["locations"] if loc["location"] == "MAIN-HUB"]
    assert main, "seeded MAIN-HUB row expected"
    assert body["total_verified"] == sum(loc["quantity_on_hand"] for loc in body["locations"] if loc["verified"])


def test_unknown_part_returns_404():
    r = client.get("/v1/parts/P-0000/availability", headers=TOKEN)
    assert r.status_code == 404


def test_pagination_caps_limit():
    assert client.get("/v1/parts?limit=500", headers=TOKEN).status_code == 422
    r = client.get("/v1/parts?limit=5&offset=0", headers=TOKEN)
    assert r.status_code == 200 and len(r.json()["items"]) <= 5


def test_openapi_document_matches_generated_file():
    generated = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text())
    live = app.openapi()
    assert set(generated["paths"]) == set(live["paths"])


def test_no_write_routes_exist():
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        assert not (methods & {"POST", "PUT", "PATCH", "DELETE"}), route.path
