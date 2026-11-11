"""Global supply-chain maps: configurable synthetic scenario, provenance, filtering, traceability,
per-user isolation of real records, risk simulation and the OriginTrace copilot intent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, geo
from app.copilot import engine, router
from app.vision import service as vision

from conftest import user

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(platform):
    from app.main import app

    return TestClient(app)


def test_scenario_footprint_and_revenue_are_configurable_and_exact(platform, tmp_path):
    net = geo.network()
    sc = net["scenario"]
    assert sc["countries"] == 161 and len(net["countries"]) == 161
    assert sum(c["revenue"] for c in net["countries"]) == sc["annual_revenue"]  # exact split, no rounding drift
    assert net["countries"][0]["id"] == "124"  # the home country (Canada) leads with its configured share
    custom = json.loads((ROOT / "fixtures" / "geo" / "scenario.json").read_text())
    custom.update(countries=40, annual_revenue=5_000_000, currency="EUR")
    path = tmp_path / "small.json"
    path.write_text(json.dumps(custom))
    default = config.get_settings().geo_scenario_path
    config.configure(geo_scenario_path=str(path))
    try:
        small = geo.network()
        assert len(small["countries"]) == 40 and small["scenario"]["currency"] == "EUR"
        assert sum(c["revenue"] for c in small["countries"]) == 5_000_000
        custom["countries"] = 999
        path.write_text(json.dumps(custom))
        with pytest.raises(ValueError, match="countries must be between"):
            geo.network()
    finally:
        config.configure(geo_scenario_path=default)


def test_every_item_carries_provenance_and_nothing_claims_to_be_verified(platform):
    net = geo.network()
    for item in (*net["nodes"], *net["edges"], *net["incidents"], *net["countries"]):
        assert item["provenance"] in geo.PROVENANCE
    assert net["provenance"]["verified"]["count"] == 0
    assert all(n["name"].startswith("Synthetic ") for n in net["nodes"])
    assert net["tracking"]["events"] == 0 and "SIMULATED" in net["tracking"]["note"]
    assert "not verified" in net["scenario"]["disclaimer"]
    assert geo.simulate()["provenance"] == "modeled"


def test_geographic_filter_keeps_only_the_country_and_its_direct_links(platform, client):
    country = geo.network()["nodes"][0]["country"]
    body = client.get(f"/api/geo/network?country={country}").json()
    own = {n["id"] for n in body["nodes"] if n["country"] == country}
    assert own and all(e["from"] in own or e["to"] in own for e in body["edges"])
    assert all(i["country"] == country for i in body["incidents"])
    assert [c["id"] for c in body["countries"]] == [country]
    assert client.get("/api/geo/network?tier=volcano").status_code == 400
    farms = client.get("/api/geo/network?tier=farm").json()["nodes"]
    assert farms and {n["tier"] for n in farms} == {"farm"}


def test_trace_reaches_farms_and_revenue_flows_upstream(platform, client):
    net = geo.network()
    market = next(n for n in net["nodes"] if n["tier"] == "market")
    t = geo.trace(market["id"])
    assert t["upstream_paths"] and all(p[0]["id"] == market["id"] and p[-1]["tier"] == "farm"
                                       for p in t["upstream_paths"])
    assert [x["tier"] for x in t["upstream_paths"][0]] == list(reversed(geo.TIERS))
    every_farm_feeds_something = all(geo.trace(n["id"])["downstream"] for n in net["nodes"] if n["tier"] == "farm")
    assert every_farm_feeds_something
    detail = client.get(f"/api/geo/node/{market['id']}").json()
    assert detail["financial"]["revenue_dependent"] == market["revenue_dependent"]
    assert [h["days"] for h in detail["risk"]] == [30, 90, 180]
    assert client.get("/api/geo/node/GEO-NOPE-01").status_code == 404


def test_risk_bands_are_ordered_deterministic_and_widen_with_the_horizon(platform):
    a, b = geo.simulate(), geo.simulate()
    assert a == b  # seeded: the same scenario gives the same simulation
    widths = []
    for h in a["horizons"]:
        for k in ("incidents", "exposure"):
            assert h[k]["p10"] <= h[k]["p50"] <= h[k]["p90"]
        widths.append(h["exposure"]["p90"] - h["exposure"]["p10"])
    assert widths == sorted(widths) and widths[0] < widths[-1]


def test_real_inspections_join_the_map_only_for_their_owner(platform, client):
    supplier = geo.supplier_names()[0]
    batch = vision.create_batch("val.viewer", "Located batch", supplier=supplier, lot_code="LOT-REAL-1")
    vision.add_image(batch["id"], "val.viewer", (ROOT / "e2e" / "fixtures" / "synthetic-potatoes.jpg").read_bytes())
    mine = geo.network("val.viewer")
    located = [i for i in mine["incidents"] if i["provenance"] == "operational_record"]
    assert len(located) == 1 and located[0]["batch"] == "LOT-REAL-1"
    assert mine["provenance"]["operational_record"]["count"] == 1
    # another user, and a signed-out visitor, never see it
    assert not [i for i in geo.network("maya.marketing")["incidents"] if i["provenance"] == "operational_record"]
    anon = client.get("/api/geo/network").json()
    assert anon["provenance"]["operational_record"]["count"] == 0
    from app import auth

    token = auth.login("val.viewer", auth.DEMO_PASSWORD)[0]
    signed = client.get("/api/geo/network", headers={"Authorization": f"Bearer {token}"}).json()
    assert signed["provenance"]["operational_record"]["count"] == 1


def test_origin_trace_intent_answers_with_citations(platform):
    net = geo.network()
    node = next(n for n in net["nodes"] if n["tier"] == "supplier")
    assert router.parse(f"Trace {node['id']} back to the farm").intents == ["origin_trace"]
    assert router.parse("How did our sales do in the last 4 weeks?").intents == ["sales"]  # unchanged
    answer = engine.ask(f"OriginTrace: trace {node['id']} back to the farm", user("val.viewer"))
    assert "OriginTrace for" in answer["answer"] and "Modelled risk" in answer["answer"]
    assert any("Synthetic global supply-chain scenario" in s["label"] for s in answer["sources"])
    country = net["countries"][2]
    answer = engine.ask(f"What is the supply chain exposure in {country['name']}?", user("val.viewer"))
    assert country["name"] in answer["answer"] and "[S1]" in answer["answer"]
    inc = net["incidents"][0]
    answer = engine.ask(f"OriginTrace: trace {inc['id']} back to the farm", user("val.viewer"))
    assert inc["node_id"] in answer["answer"]
