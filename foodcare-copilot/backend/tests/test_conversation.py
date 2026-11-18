"""Jerry 3.0 conversations: typed visuals, safe UI actions, multi-turn focus, commands."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from test_command import pdf_text
from test_privacy import assert_clean

from app import auth, visuals
from app.enterprise import data


@pytest.fixture()
def client(platform):
    data.seed()
    from app.main import app

    return TestClient(app)


def headers(username: str) -> dict:
    return {"Authorization": f"Bearer {auth.login(username, auth.DEMO_PASSWORD)[0]}"}


class Chat:
    def __init__(self, client, username="eli.engineer"):
        self.client, self.h, self.conv = client, headers(username), None

    def ask(self, q: str) -> dict:
        body = {"question": q, "conversation_id": self.conv}
        a = self.client.post("/api/copilot/ask", headers=self.h, json=body).json()
        self.conv = a["conversation_id"]
        assert a["visual_schema"] == "1.0"
        assert_clean(json.dumps(a), q)
        return a


def kinds(a: dict) -> list[str]:
    return [v["kind"] for v in a["visuals"]]


def actions(a: dict, t: str) -> list[dict]:
    return [x for x in a["ui_actions"] if x["type"] == t]


def test_greeting_has_no_charts(client):
    a = Chat(client).ask("Hi")
    assert a["visuals"] == [] and a["ui_actions"] == []


def test_continuous_supplier_investigation(client):
    chat = Chat(client)
    a = chat.ask("Jerry, show me our highest-risk suppliers")
    assert "bar" in kinds(a) and a["data_status"] == "synthetic" and a["limitations"]
    ranked = actions(a, "open_globe")[0]["sites"]
    assert len(ranked) == 8

    a = chat.ask("Show them on the globe")
    act = actions(a, "open_globe")[0]
    assert act["sites"] == ranked and act["geo"]["node"] == ranked[0]

    a = chat.ask("Only the European ones")
    eu = actions(a, "open_globe")[0]["sites"] if actions(a, "open_globe") else []
    assert set(eu) <= set(ranked)
    assert "approximate latitude/longitude" in a["answer"] or "None of the sites" in a["answer"]

    chat.ask("Jerry, show me our highest-risk suppliers")  # reset focus to the full ranking
    a = chat.ask("Compare the top two")
    assert kinds(a) == ["bar", "bar", "bar"] and " vs " in a["answer"]

    a = chat.ask("What if the first supplier shuts down?")
    assert kinds(a) == ["motion_story", "forecast_band"]
    story = a["visuals"][0]
    assert story["story"] == "supplier_disruption" and story["provenance"] == "synthetic"
    assert "not a real event" in story["disclaimer"]

    a = chat.ask("Which factories would be affected?")
    assert kinds(a) == ["table"] and "factory" in a["answer"]

    a = chat.ask("Prepare an action plan")
    plan = a["visuals"][0]
    assert plan["kind"] == "plan" and all(s["approval"] for s in plan["steps"])
    assert "I have not executed anything" in a["answer"]

    a = chat.ask("Convert this to a PDF")
    url = actions(a, "download")[0]["url"]
    assert url.startswith("/api/exports/conversation.pdf?ref=")
    pdf = client.get(url, headers=chat.h)
    assert pdf.status_code == 200 and "highest-risk suppliers" in pdf_text(pdf.content)
    assert_clean(pdf_text(pdf.content), "conversation PDF")

    a = chat.ask("Show me where the intelligence came from")
    xray = actions(a, "open_xray")[0]
    steps = client.get(f"/api/xray/{xray['agent_run_id']}", headers=chat.h).json()["steps"]
    assert [s["kind"] for s in steps][:3] == ["input", "agent", "policy"]


def test_architecture_databricks_kubernetes_and_animation(client):
    chat = Chat(client)
    a = chat.ask("How does this connect to Databricks and Kubernetes?")
    flow = a["visuals"][0]
    assert flow["kind"] == "flow"
    states = {n["id"]: n.get("state") for n in flow["nodes"]}
    assert states["databricks"] == "adapter_available" and states["kubernetes"] == "adapter_available"
    assert "never writes SQL from your question" in a["answer"] and "no exec" in a["answer"]
    a = chat.ask("Animate how these systems work together")
    assert a["visuals"][0]["kind"] == "motion_story" and a["visuals"][0]["story"] == "architecture"
    gif = client.get(actions(a, "download")[0]["url"], headers=chat.h)
    assert gif.status_code == 200 and gif.content[:6] == b"GIF89a"
    assert Image.open(io.BytesIO(gif.content)).n_frames > 10
    assert client.get("/api/motion/secrets.gif", headers=chat.h).status_code == 404
    assert client.get("/api/motion/supplier_disruption.gif?site=x';--", headers=chat.h).status_code == 422


@pytest.mark.parametrize("q,expected", [
    ("How is my business performing today, and what changed?", {"line", "kpis"}),
    ("Where is my supply chain vulnerable, and what will it cost us?", {"forecast_band"}),
    ("Where are we losing money through waste, spoilage, and stockouts?", {"waterfall"}),
    ("Are we exposed to any food safety, quality, or compliance incidents?", {"table"}),
    ("Which factories, stores, or distribution centers are underperforming, and why?", {"bar"}),
])
def test_executive_questions_get_fitting_visuals(client, q, expected):
    a = Chat(client).ask(q)
    assert a["answered"] and expected <= set(kinds(a))


def test_unmeasurable_losses_are_gaps_not_zeros(client):
    a = Chat(client).ask("Where are we losing money through waste, spoilage, and stockouts?")
    wf = a["visuals"][0]
    assert "Spoilage / expiry" in wf["missing"] and "Not measurable yet" in a["answer"]


def test_board_export_command_creates_a_real_file(client):
    chat = Chat(client)
    a = chat.ask("Prepare a PDF for my board")
    dl = actions(a, "download")[0]
    assert dl["url"] == "/api/exports/board.pdf"
    assert client.get(dl["url"], headers=chat.h).content.startswith(b"%PDF")


def test_invalid_visuals_and_actions_are_dropped():
    v, a, errors = visuals.validate(
        [{"kind": "bar", "title": "ok", "unit": "x", "items": [], "provenance": "synthetic"},
         {"kind": "script", "code": "alert(1)"}],
        [{"type": "download", "label": "x", "url": "https://evil.example/x"}, {"type": "run_kubectl", "label": "x"}])
    assert [x["kind"] for x in v] == ["bar"] and a == [] and len(errors) == 3
