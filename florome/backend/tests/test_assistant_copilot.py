"""Bridge to the Conversation Intelligence Copilot (Project A) and the chat-first home page."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from florome.assistant import copilot
from tests.conftest import H

RECORDED = json.loads((Path(__file__).parent / "fixtures" / "copilot_negative_topics.json").read_text())


def ask(c, page, question, conv=None, role="viewer"):
    body = {"page": page, "question": question, **({"conversation_id": conv} if conv else {})}
    return c.post("/api/v1/assistant/ask", json=body, headers=H(role)).json()


def test_translate_real_copilot_response():
    a = copilot.translate(RECORDED)
    assert a["statement"] == RECORDED["headline"]
    assert a["visual"]["type"] == "bars" and a["visual"]["items"][0]["label"] == "General help request" and a["visual"]["items"][0]["value"] == 49
    assert a["follow_ups"][:2] == RECORDED["follow_up_questions"][:2] and len(a["follow_ups"]) == 4
    assert all(e["href"] is None and e["label"].startswith("C") for e in a["evidence"])
    assert a["source"]["model_calls"] == 0 and a["focus"]["copilot_session"] == RECORDED["session_id"]


def test_unsupported_status_is_passed_through_not_upgraded():
    a = copilot.translate({**RECORDED, "status": "unsupported", "headline": "Which analysis did you mean?", "charts": [], "metrics": []})
    assert a["bullets"][0] == "The Conversation Intelligence Copilot reported: unsupported" and a["visual"] is None


@pytest.fixture
def fake_copilot(monkeypatch, client):
    client.ctx.settings.copilot_url = "http://copilot.test"
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={**RECORDED, "session_id": "S-test1"})

    real = httpx.AsyncClient
    monkeypatch.setattr(copilot.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return seen


def test_customer_questions_route_to_copilot_and_keep_its_session(client, fake_copilot):
    a = ask(client, "home", "What are customers most negative about?")
    assert a["intent"] == "customer_negative_topics" and a["source"]["name"] == "Conversation Intelligence Copilot"
    assert fake_copilot[0] == {"question": "What are the top 5 topics associated with negative sentiment in the last month?"}
    b = ask(client, "home", "What about the previous month?", conv=a["conversation_id"])  # Copilot's own follow-up
    assert b["intent"] == "customer_free" and fake_copilot[1] == {"question": "What about the previous month?", "session_id": "S-test1"}
    c = ask(client, "home", "Show me conversation C0000479")
    assert c["intent"] == "customer_free"


def test_florome_questions_still_answered_by_florome(client, fake_copilot):
    a = ask(client, "home", "Which vulnerabilities are confirmed?")
    assert a["source"]["name"] == "Florome records" and a["source"]["model_calls"] == 0 and not fake_copilot


def test_copilot_unreachable_is_reported_honestly(client, monkeypatch):
    client.ctx.settings.copilot_url = "http://127.0.0.1:9"  # nothing listens here
    a = ask(client, "home", "What are customers most negative about?")
    assert a["statement"].startswith("I can't answer customer-conversation questions right now")
    assert a["source"]["status"] == "not reachable"
    client.ctx.settings.copilot_url = ""
    assert "not configured" in ask(client, "home", "Which agents could use coaching?")["statement"]


def test_home_page_config_and_sources(client, fake_copilot):
    cfg = client.get("/api/v1/assistant/pages/home", headers=H("viewer")).json()
    assert len(cfg["starters"]) == 4 and [g["title"] for g in cfg["groups"]][2] == "Customers · Conversation Copilot"
    assert "What are customers most negative about?" in cfg["groups"][2]["questions"]
    src = client.get("/api/v1/assistant/sources", headers=H("viewer")).json()
    assert src["conversation_copilot"] == {"configured": True, "reachable": True, "status": "ok"}


@pytest.mark.skipif(not copilot.httpx, reason="httpx missing")
def test_live_copilot_if_running(client):
    """Integration against a real Project A on :8001 when it is running; skipped otherwise."""
    try:
        httpx.get("http://127.0.0.1:8001/health", timeout=2)
    except httpx.HTTPError:
        pytest.skip("Conversation Intelligence Copilot is not running on :8001")
    client.ctx.settings.copilot_url = "http://127.0.0.1:8001"
    a = ask(client, "home", "Which customer concerns need leadership attention?")
    assert a["source"]["status"] == "completed" and a["source"]["model_calls"] == 0
    assert a["statement"].startswith("Leadership should review")
