"""FastAPI endpoints and secret-handling guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import ConfigurationError, Settings
from app.container import build_container
from app.rag.embeddings import HashingEmbedding
from tests.conftest import FakeLLM, make_settings

# Assembled at runtime so no key-shaped literal exists in source (keeps secret scanners quiet).
FAKE_KEY = "sk-" + "ant-api03-THIS-IS-A-FAKE-TEST-KEY-123456"  # pragma: allowlist secret


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory):
    settings = make_settings(tmp_path_factory.mktemp("api"))
    app = create_app(settings, container_factory=lambda s: build_container(s, embedding=HashingEmbedding()))
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"
    assert body["live_llm_configured"] is False
    assert body["documents_indexed"] == 6
    assert body["chunks_indexed"] > 0


def test_tools_endpoint_mcp_shape(client: TestClient) -> None:
    tools = client.get("/tools").json()
    assert {"name", "description", "inputSchema"} <= set(tools[0])


def test_chat(client: TestClient) -> None:
    response = client.post("/chat", json={"question": "Which issues are blocking the October release?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "issue_lookup"
    assert "PHX-214" in body["answer"]
    assert body["request_id"] and body["latency_ms"] > 0


def test_chat_validation(client: TestClient) -> None:
    assert client.post("/chat", json={"question": "  "}).status_code == 422
    assert client.post("/chat", json={"question": "x" * 2001}).status_code == 422


def test_upload_and_query(client: TestClient) -> None:
    doc = b"# Vendor Contract Notes\n\n## Renewal\nThe Zephyrine hosting contract renews on 2027-03-01 with a 9 percent uplift.\n"
    up = client.post("/documents/upload", files={"file": ("vendor_contract.md", doc, "text/markdown")})
    assert up.status_code == 200, up.text
    assert up.json()["document_id"] == "vendor_contract"
    assert up.json()["chunks_indexed"] >= 1
    answer = client.post("/chat", json={"question": "When does the Zephyrine hosting contract renew?"}).json()
    assert "2027-03-01" in answer["answer"]
    assert any(c["document_id"] == "vendor_contract" for c in answer["citations"])


def test_upload_rejects_bad_type(client: TestClient) -> None:
    r = client.post("/documents/upload", files={"file": ("malware.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_metrics(client: TestClient) -> None:
    client.post("/chat", json={"question": "What are the major delivery risks?"})
    body = client.get("/metrics").json()
    assert body["total_requests"] >= 1
    assert body["recent_traces"][0]["agents_invoked"]


def test_settings_live_mode_requires_key() -> None:
    with pytest.raises(ConfigurationError):
        Settings(_env_file=None, app_mode="live", anthropic_api_key=None)


def test_placeholder_key_treated_as_missing() -> None:
    placeholder = "your_api_key_here"  # pragma: allowlist secret
    assert Settings(_env_file=None, anthropic_api_key=placeholder).anthropic_api_key is None


def test_default_mode_is_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_MODE", raising=False)
    assert Settings(_env_file=None).app_mode.value == "demo"


def test_api_key_never_exposed(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, app_mode="live", anthropic_api_key=FAKE_KEY)
    assert FAKE_KEY not in repr(settings) and FAKE_KEY not in str(settings.public_summary())
    app = create_app(
        settings, container_factory=lambda s: build_container(s, llm=FakeLLM(), embedding=HashingEmbedding())
    )
    with TestClient(app) as c:
        bodies = [
            c.get("/health").text,
            c.get("/tools").text,
            c.post("/chat", json={"question": "How is Phoenix doing?"}).text,
            c.get("/metrics").text,
            c.get("/openapi.json").text,
        ]
    for body in bodies:
        assert FAKE_KEY not in body
        assert "THIS-IS-A-FAKE" not in body
