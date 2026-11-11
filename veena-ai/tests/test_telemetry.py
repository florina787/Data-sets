"""Opt-in anonymous statistics: off by default, allow-listed, offline-safe, withdrawable."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.memory.db import make_engine
from backend.memory.store import Store
from backend.telemetry import FEATURES, Telemetry

ALLOWED_TOP = {"install_id", "os", "app_version", "events"}
ALLOWED_EVENT = {"event", "feature", "error_code", "day"}


class Recorder:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            raise httpx.ConnectError("offline")
        self.calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def store(tmp_path):
    return Store(make_engine(tmp_path / "t.db"))


def make(store, tmp_path, rec=None, url="https://insights.example"):
    return Telemetry(store, tmp_path, url=url, transport=httpx.MockTransport(rec or Recorder()))


def test_off_by_default_records_and_sends_nothing(store, tmp_path):
    rec = Recorder()
    t = make(store, tmp_path, rec)
    assert store.get_settings()["share_usage_stats"] is False
    t.track("first_launch")
    t.ai_success("chat")
    t.error("model_error")
    assert t.status()["queued"] == []
    import asyncio

    assert asyncio.run(t.flush()) == "nothing"
    assert rec.calls == []


def test_unavailable_without_server(store, tmp_path, monkeypatch):
    monkeypatch.delenv("VEENA_INSIGHTS_URL", raising=False)
    t = Telemetry(store, tmp_path)
    assert t.available is False
    with pytest.raises(RuntimeError):
        t.opt_in()


def test_opt_in_sends_only_allow_listed_fields(store, tmp_path):
    import asyncio

    rec = Recorder()
    t = make(store, tmp_path, rec)
    t.opt_in()
    for f in FEATURES:
        t.ai_success(f)
    t.error("Traceback in C:/Users/someone/secret.pdf")  # free text is reduced to a code
    assert asyncio.run(t.flush()) == "http 200"
    path, body = rec.calls[0]
    assert path == "/v1/events"
    assert set(body) == ALLOWED_TOP
    assert all(set(e) <= ALLOWED_EVENT for e in body["events"])
    assert {e["error_code"] for e in body["events"] if e["event"] == "error"} == {"other"}
    blob = json.dumps(body)
    assert "secret" not in blob and "Users" not in blob
    assert t.status()["queued"] == []


def test_once_and_daily_deduplication(store, tmp_path):
    t = make(store, tmp_path)
    t.opt_in()
    for _ in range(5):
        t.ai_success("chat")
        t.track("active")
    q = t.status()["queued"]
    assert sum(e["event"] == "ai_first_success" for e in q) == 1
    assert sum(e["event"] == "active" for e in q) == 1
    assert sum(e["event"] == "feature" for e in q) == 1


def test_offline_keeps_queue_and_never_raises(store, tmp_path):
    import asyncio

    t = make(store, tmp_path, Recorder(fail=True))
    t.opt_in()
    t.ai_success("documents")
    assert asyncio.run(t.flush()) == "offline"
    assert len(t.status()["queued"]) >= 3


def test_withdrawal_stops_collection_and_requests_deletion(store, tmp_path):
    import asyncio

    rec = Recorder()
    t = make(store, tmp_path, rec)
    t.opt_in()
    old_id = store.get_settings()["telemetry_id"]
    t.opt_out()
    assert store.get_settings()["telemetry_id"] is None
    assert t.status()["queued"] == []
    t.ai_success("chat")  # after withdrawal: nothing is recorded
    assert t.status()["queued"] == []
    asyncio.run(t.flush())
    assert rec.calls == [("/v1/delete", {"install_id": old_id})]


def test_settings_patch_cannot_flip_consent(client):
    assert client.patch("/api/settings", json={"share_usage_stats": True}).status_code == 400
    assert client.patch("/api/settings", json={"telemetry_id": "x"}).status_code == 400
    st = client.get("/api/telemetry").json()
    assert st["enabled"] is False and st["queued"] == []


def test_chat_answer_records_nothing_when_not_opted_in(client):
    sid = client.post("/api/sessions", json={"mode": "conversation"}).json()["id"]
    r = client.post("/api/chat", json={"session_id": sid, "text": "What is my private plan for Friday?"})
    assert r.status_code == 200 and '"token"' in r.text
    assert client.get("/api/telemetry").json()["queued"] == []


def test_opted_in_chat_records_feature_but_no_content(client, app):
    tel = app.state.veena.telemetry
    tel.url = "https://insights.example"
    tel.transport = httpx.MockTransport(Recorder())
    assert client.post("/api/telemetry", json={"enabled": True}).status_code == 200
    sid = client.post("/api/sessions", json={"mode": "conversation"}).json()["id"]
    client.post("/api/chat", json={"session_id": sid, "text": "What is my private plan for Friday?"})
    q = client.get("/api/telemetry").json()["queued"]
    assert {"event": "feature", "feature": "chat", "day": q[-1]["day"]} in q or any(e.get("feature") == "chat" for e in q)
    assert "private" not in json.dumps(q) and "Friday" not in json.dumps(q)
    assert client.post("/api/telemetry", json={"enabled": False}).json()["enabled"] is False
