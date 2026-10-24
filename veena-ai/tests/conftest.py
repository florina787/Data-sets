"""Shared fixtures.

TEST DOUBLES ARE LABELLED: ``ScriptedLLM`` and ``HashEmbedder`` are simulated
components used only by the deterministic test suite. The real-model suites
(markers ``ollama``, ``asr``, ``embeddings``) exercise the actual local models.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import Settings
from backend.llm.ollama import GenerationStats, LLMUnavailable, ModelInfo

TOKEN = "test-token-0123456789abcdef"


class ScriptedLLM:
    """SIMULATED Ollama client for deterministic tests. Not used by the app."""

    def __init__(self, reply: str = "Simulated answer [1].", vision: bool = True, json_reply: dict | None = None):
        self.reply = reply
        self.json_reply = json_reply or {}
        self.calls: list[dict] = []
        self.up = True
        self.fail_next = False
        self.delay_per_token = 0.0
        self.models = [ModelInfo("qwen2.5:1.5b", 986_000_000, "qwen2", "1.5B", "Q4_K_M", ["completion"])]
        if vision:
            self.models.append(ModelInfo("qwen2.5vl:3b", 3_200_000_000, "qwen25vl", "3.8B", "Q4_K_M", ["completion", "vision"]))

    async def version(self):
        return "simulated" if self.up else None

    async def list_models(self):
        if not self.up:
            raise LLMUnavailable("Ollama is not reachable (simulated)")
        return self.models

    async def capabilities(self, model):
        return next((m.capabilities for m in self.models if m.name == model), [])

    async def warm(self, model):
        return None

    async def pull(self, model) -> AsyncIterator[dict]:
        yield {"status": "pulling manifest"}
        yield {"status": "success"}

    async def chat_stream(self, model, messages, *, options=None, fmt=None, stats: GenerationStats | None = None):
        import asyncio

        self.calls.append({"model": model, "messages": messages, "fmt": fmt})
        if not self.up:
            raise LLMUnavailable("Ollama is not reachable (simulated)")
        if self.fail_next:
            self.fail_next = False
            raise LLMUnavailable("model crashed (simulated)")
        text = json.dumps(self.json_reply) if fmt == "json" else self.reply
        if stats is not None:
            stats.first_token_ms = 1.0
        n = 0
        for tok in text.split(" "):
            if self.delay_per_token:
                await asyncio.sleep(self.delay_per_token)
            n += 1
            yield tok + " "
        if stats is not None:
            stats.eval_tokens = n
            stats.tokens_per_second = 100.0

    async def chat(self, model, messages, **kw):
        return "".join([d async for d in self.chat_stream(model, messages, **kw)]).strip()

    async def aclose(self):
        return None


class HashEmbedder:
    """SIMULATED embedder: bag-of-words hashing. Deterministic, no download."""

    model_name = "test-hash-embedder"
    dim = 256

    def __init__(self):
        self._model = None
        self.cache_hits = 0

    def embed(self, texts):
        out = np.zeros((len(texts), self.dim), np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().split():
                w = "".join(c for c in w if c.isalnum())
                if w:
                    out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1
        out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
        return out


class FakeASR:
    """SIMULATED transcriber: returns scripted text per call."""

    def __init__(self, size="base", language=None, texts=None):
        self.model_size = size
        self.language = language
        self.loaded = False
        self.device = "cpu"
        self.texts = list(texts or ["what is a hash map?"])
        self.calls = 0

    def load(self):
        self.loaded = True

    def transcribe(self, audio, **kw):
        from backend.transcription.asr import ASRResult

        self.calls += 1
        text = self.texts[min(self.calls - 1, len(self.texts) - 1)]
        return ASRResult(text, "en", 0.99, [{"start": 0, "end": 1, "text": text, "no_speech_prob": 0.0}])


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(token=TOKEN, data_dir=tmp_path / "data", allowed_origins=("http://localhost:5173", "null"))


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM()


@pytest.fixture
def app(settings, llm):
    a = create_app(settings, llm=llm, embedder=HashEmbedder(), transcriber_factory=lambda s, lang=None: FakeASR(s, lang))
    # Bag-of-words hashing gives lower cosines than a sentence model.
    a.state.veena.kb.min_score = 0.1
    return a


@pytest.fixture
def client(app):
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        yield c


def ndjson(resp) -> list[dict]:
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def ollama_model_available(name: str) -> bool:
    try:
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2, trust_env=False)
        return any(m["name"] == name for m in r.json().get("models", []))
    except httpx.HTTPError:
        return False


def speech_wav(text: str, path: Path) -> np.ndarray | None:
    """Real synthetic speech via espeak-ng, resampled to 16 kHz with ffmpeg."""
    if not (shutil.which("espeak-ng") and shutil.which("ffmpeg")):
        return None
    raw = path.with_suffix(".raw.wav")
    subprocess.run(["espeak-ng", "-s", "150", "-w", str(raw), text], check=True, capture_output=True)
    pcm = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(raw), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
