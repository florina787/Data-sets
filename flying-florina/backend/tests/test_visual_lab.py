"""Airspace Safety Lab: capability honesty, evaluation, upload handling, boundaries."""

import io

from PIL import Image

from app.engineering import change_impact
from app.visual import lab
from tests.conftest import login


def test_capabilities_report_no_vision_model_and_baseline_is_not_ai(client):
    h = login(client, "planner.marco")
    caps = client.get("/api/visual/capabilities", headers=h).json()["data"]
    assert caps["vision_model"]["found"] is False
    assert caps["default_method"] == "classical_baseline"
    assert "No local vision model" in caps["statement"]
    assert any("no tracking" in b.lower() for b in caps["boundaries"])


def test_evaluation_reports_errors_honestly():
    ev = lab.evaluate()
    assert ev["is_ai"] is False and ev["n"] == 58
    assert ev["tp"] + ev["fn"] == sum(1 for f in ev["frames"] if f["label"] == "drone")
    assert 0 <= ev["precision"] <= 1 and ev["errors"]  # the baseline makes mistakes and they are listed


def test_upload_analysis_stores_hash_not_pixels(client):
    h = login(client, "planner.marco")
    img = Image.new("RGB", (320, 200), (150, 190, 240))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = client.post("/api/visual/upload", files={"file": ("sky.png", buf.getvalue(), "image/png")}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["method"] == "classical_baseline" and d["frames_flagged"] == 0
    from app.core import db

    row = db.query_one("SELECT * FROM visual_analyses WHERE id = ?", (d["analysis_id"],))
    assert len(row["sha256"]) == 64 and "thumbnail" not in row["result_json"]


def test_unsupported_upload_rejected(client):
    h = login(client, "planner.marco")
    r = client.post("/api/visual/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=h)
    assert r.status_code == 422


def test_guest_cannot_analyze_media(client):
    g = login(client, "guest")
    assert client.post("/api/visual/analyze-demo", json={"item_id": "IMG-01"}, headers=g).status_code == 403


def test_change_impact_on_real_repository():
    r = change_impact.analyze("app.global_intel.forecast")
    assert "app.api.routes_global" in {m["module"] for m in r["affected_modules"]}
    assert any(t["test"] == "tests/test_global_forecast.py" for t in r["recommended_tests"])
    tr = change_impact.traceability()
    assert tr["summary"]["missing_verification"] >= 2  # REQ-SIM-001 and REQ-RPT-001 deliberately lack tests
