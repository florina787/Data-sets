import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(env):
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health_and_dataset_endpoints(client):
    h = client.get("/health").json()
    assert {c["check"] for c in h["checks"]} >= {"analytics_database", "retrieval_index", "llm"}
    assert client.get("/api/dataset/status").json()["sources"][0]["conversations"] == 11
    assert client.get("/api/analytics/taxonomy").json()["months"] == ["2025-01", "2025-02"]


def test_chat_and_stream(client):
    r = client.post("/api/chat", json={"question": "Show the sentiment trend over time."}).json()
    assert r["status"] == "completed" and r["charts"]
    s = client.post("/api/chat/stream", json={"question": "Which recurring customer concerns should leadership review first?"})
    events = [json.loads(line[5:]) for line in s.text.splitlines() if line.startswith("data:")]
    assert events[0]["type"] == "accepted" and events[-1]["type"] == "final"


def test_chat_validates_input(client):
    assert client.post("/api/chat", json={"question": ""}).status_code == 422
    assert client.post("/api/chat", json={"question": "x", "session_id": "../etc"}).status_code == 422


def test_analytics_endpoint_rejects_unregistered_operation(client):
    assert client.post("/api/analytics/query", json={"operation": "drop_everything"}).status_code == 400
    assert client.post("/api/analytics/query", json={"operation": "topic_frequency", "dataset_mode": "combined"}).status_code == 403
    ok = client.post("/api/analytics/query", json={"operation": "topic_frequency", "window": {"type": "last_month"}}).json()
    assert ok["metrics"][0]["value"] == 7


def test_dashboards(client):
    for name in ("leadership", "sentiment", "coaching"):
        d = client.post(f"/api/dashboards/{name}", json={"window": {"type": "all"}}).json()
        assert d["charts"], name
    assert client.post("/api/dashboards/nope", json={}).status_code == 404


def test_conversations_and_retrieval(client):
    lst = client.get("/api/conversations", params={"topic": "duplicate_charge"}).json()
    assert lst["total"] == 3
    one = client.get("/api/conversations/C0000011").json()
    assert "[EMAIL]" in one["messages"][0]["text"]
    assert client.get("/api/conversations/C9999999").status_code == 404
    res = client.post("/api/retrieval/search", json={"query": "charged twice for my wallet", "k": 3}).json()
    ids = [r["conversation_id"] for r in res["results"]]
    assert ids and ids[0] == "C0000001" and len(ids) == len(set(ids))


def test_sessions_clear(client):
    r = client.post("/api/chat", json={"question": "How many conversations are in the dataset?"}).json()
    sid = r["session_id"]
    assert client.get(f"/api/sessions/{sid}").json()["turns"]
    assert client.delete(f"/api/sessions/{sid}").json()["cleared"]
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_human_review_metrics(client):
    assert client.get("/api/review/metrics").json()["status"] == "no_reviews"
    items = client.get("/api/review/sample", params={"reviewer": "alice", "n": 6}).json()["items"]
    assert items and "sentiment" not in items[0], "review must be blind"
    for it in items:
        client.post("/api/review/labels", json={"message_id": it["message_id"], "reviewer": "alice", "sentiment": "negative"})
    m = client.get("/api/review/metrics").json()
    assert m["reviews"] == len(items) and 0 <= m["accuracy"] <= 1 and m["confusion_matrix"]["labels"]
    assert client.post("/api/review/labels", json={"message_id": "C0000001-T00", "reviewer": "a", "sentiment": "furious"}).status_code == 400


def test_governance_prompts_traces(client):
    g = client.get("/api/governance/status").json()
    assert any(c["status"] == "not_implemented" for c in g["controls"])
    assert len(client.get("/api/prompts").json()["prompts"]) == 3
    r = client.post("/api/chat", json={"question": "Show the sentiment trend over time."}).json()
    t = client.get(f"/api/traces/{r['request_id']}").json()
    assert t["nodes"] and client.get("/api/agents/graph").json()["edges"]


def test_secrets_never_leak(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-super-secret-value")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        bodies = [client.get(p).text for p in ("/health", "/api/governance/status", "/api/model/status", "/api/telemetry/summary")]
        assert all("sk-super-secret-value" not in b for b in bodies)
        assert "sk-super-secret-value" not in repr(get_settings())
    finally:
        monkeypatch.delenv("GEMINI_API_KEY")
        get_settings.cache_clear()


def test_corrupt_index_degrades_gracefully(env, tmp_path, monkeypatch):
    from app.agents.graph import run_chat
    from app.config import get_settings
    from app.retrieval import index

    bad = tmp_path / "broken.faiss"
    for suffix in (".faiss", ".lsa.faiss", ".lsa.embedder", ".meta.parquet", ".embedder", ".manifest.json"):
        bad.with_suffix(suffix).write_text("garbage")
    monkeypatch.setenv("FAISS_INDEX_PATH", str(bad))
    get_settings.cache_clear()
    index.get_retriever.cache_clear()
    try:
        status = index.retriever_status()
        assert status["available"] is False and "could not be loaded" in status["reason"]
        r = run_chat("Find conversations about duplicate charges")
        assert r["status"] == "completed" and any(e["node"] == "retrieval" for e in r["errors"])
    finally:
        monkeypatch.delenv("FAISS_INDEX_PATH")
        get_settings.cache_clear()
        index.get_retriever.cache_clear()


def test_missing_database_reports_clearly(tmp_path):
    from app.analytics.db import AnalyticsDB

    with pytest.raises(FileNotFoundError, match="make prepare"):
        AnalyticsDB(tmp_path / "nope.duckdb")


def test_partial_gemini_label_coverage_is_reported(env, tmp_path, monkeypatch):
    """Rebuild with LABEL_SOURCE=gemini and labels for only some texts: coverage must say so."""
    from app.config import get_settings
    from app.data.pipeline import run
    from app.labeling.store import LabelStore, text_key

    labels = tmp_path / "labels.sqlite"
    store = LabelStore(labels)
    store.put(text_key("Thanks, that helps.", "customer", False), "gemini-test", "1.0", "Thanks, that helps.", "customer", False,
              {"act": "gratitude", "sentiment": "positive", "sentiment_score": 0.7, "empathy": False, "courtesy": False, "resolution": None,
               "language": "english", "topic": None, "product": None, "confidence": 0.9})
    monkeypatch.setenv("LABEL_SOURCE", "gemini")
    monkeypatch.setenv("LABELS_DATABASE_PATH", str(labels))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "partial.duckdb"))
    monkeypatch.setenv("MANIFESTS_DIR", str(tmp_path / "manifests"))
    get_settings.cache_clear()
    try:
        cov = run()["manifest"]["label_coverage"]
        assert cov["gemini_labels_used"] == 3 and cov["by_method"]["gemini"] == 3 and cov["by_method"]["template"] > 0
    finally:
        get_settings.cache_clear()
