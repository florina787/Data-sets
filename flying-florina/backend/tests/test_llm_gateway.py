import pytest
from pydantic import BaseModel

from app.core.config import reset_settings
from app.llm import telemetry
from app.llm.discovery import discover, quantization_from_name
from app.llm.gateway import LLMError, LLMUnavailable, LocalLLMGateway, set_gateway
from tests.fake_ollama import FakeOllama


class Summary(BaseModel):
    summary: str


@pytest.fixture
def ollama(monkeypatch):
    fake = FakeOllama()
    monkeypatch.setenv("LLM_URL", fake.url)
    monkeypatch.setenv("LLM_ENABLED", "auto")
    reset_settings()
    yield fake
    fake.close()
    monkeypatch.undo()
    reset_settings()
    set_gateway(None)


def test_quantization_parsing():
    assert quantization_from_name("qwen2.5-1.5b-instruct-q4_k_m.gguf") == "Q4_K_M"
    assert quantization_from_name("Qwen2.5-7B-Instruct-Q8_0.gguf") == "Q8_0"


def test_discovers_existing_qwen_on_ollama(ollama):
    d = discover()
    assert d.found and d.runtime == "ollama" and d.model.startswith("qwen") and d.quantization == "Q4_K_M"


def test_gguf_found_but_runtime_missing_is_reported(tmp_path, monkeypatch):
    f = tmp_path / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    f.write_bytes(b"\0" * 2_000_000)
    monkeypatch.setenv("LLM_ENABLED", "auto")
    monkeypatch.setenv("FF_QWEN_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setenv("LLM_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("FF_QWEN_RUNTIME", "llama_cpp")
    reset_settings()
    try:
        d = discover()
        assert not d.found and str(f) in d.reason and "llama-cpp-python" in d.reason
        assert d.candidates[0]["path"] == str(f)
    finally:
        monkeypatch.undo()
        reset_settings()


def test_non_loopback_server_refused(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "auto")
    monkeypatch.setenv("FF_QWEN_BASE_URL", "https://api.example.com")
    reset_settings()
    try:
        d = discover()
        assert not d.found and "loopback" in d.reason
    finally:
        monkeypatch.undo()
        reset_settings()


def test_off_mode_never_calls_a_model(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    reset_settings()
    try:
        g = LocalLLMGateway()
        assert not g.available()
        with pytest.raises(LLMUnavailable):
            g.generate(agent="t", task="t", system="s", user="u")
    finally:
        monkeypatch.undo()
        reset_settings()


def test_generate_streams_validates_caches_and_records(ollama):
    g = LocalLLMGateway()
    r = g.generate(agent="Diagnostics", task="explain", system="sys", user="facts", schema=Summary, max_tokens=50)
    assert r.data == {"summary": "AC-204 vibration rose."}
    assert r.runtime == "ollama" and r.prompt_tokens == 42 and r.first_token_ms is not None and r.tokens_per_s
    assert ollama.calls[0]["format"]["properties"]["summary"]  # JSON schema sent to the runtime
    assert ollama.calls[0]["options"]["num_predict"] == 50
    again = g.generate(agent="Diagnostics", task="explain", system="sys", user="facts", schema=Summary, max_tokens=50)
    assert again.cached and len(ollama.calls) == 1
    m = telemetry.metrics()
    assert m["calls"] >= 2 and m["cached_calls"] >= 1 and any(a["agent"] == "Diagnostics" for a in m["by_agent"])


def test_schema_violation_is_rejected(ollama):
    ollama.reply = "not json at all"
    with pytest.raises(LLMError):
        LocalLLMGateway().generate(agent="t", task="t", system="s", user="u2", schema=Summary)


def test_context_is_trimmed_to_window(ollama, monkeypatch):
    monkeypatch.setenv("FF_QWEN_N_CTX", "600")
    reset_settings()
    r = LocalLLMGateway().generate(agent="t", task="t", system="s", user="x " * 5000, max_tokens=50)
    assert r.truncated_context
    assert len(ollama.calls[-1]["messages"][1]["content"]) < 3000


def test_timeout_is_enforced(monkeypatch):
    fake = FakeOllama(reply="a b c d e f g h", delay_chunks=0.3)
    monkeypatch.setenv("LLM_URL", fake.url)
    monkeypatch.setenv("FF_QWEN_TIMEOUT_S", "0.5")
    monkeypatch.setenv("LLM_ENABLED", "auto")
    reset_settings()
    try:
        with pytest.raises(LLMError, match="timeout"):
            LocalLLMGateway().generate(agent="t", task="t", system="s", user="slow", use_cache=False)
    finally:
        fake.close()
        monkeypatch.undo()
        reset_settings()
