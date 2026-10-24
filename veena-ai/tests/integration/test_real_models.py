"""Tests against the REAL local models. Nothing here is simulated.

Run with:  pytest -m "ollama or asr or embeddings"
Each test skips when its model or tool is not installed.
"""

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.audio.pcm import encode_frame
from backend.config import Settings
from backend.screen.frames import encode_png_b64
from tests.conftest import TOKEN, ndjson, ollama_model_available, speech_wav
from tests.unit.test_screen_and_vision import text_image

TEXT_MODEL = "qwen2.5:1.5b"
VISION_MODEL = "qwen2.5vl:3b"


@pytest.fixture
def real_client(tmp_path):
    s = Settings(token=TOKEN, data_dir=tmp_path / "data")
    app = create_app(s)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        c.patch("/api/settings", json={"text_model": TEXT_MODEL, "vision_model": VISION_MODEL, "asr_model": "base", "profile": "balanced"})
        yield c


needs_text = pytest.mark.skipif(not ollama_model_available(TEXT_MODEL), reason=f"{TEXT_MODEL} not installed in Ollama")
needs_vision = pytest.mark.skipif(not ollama_model_available(VISION_MODEL), reason=f"{VISION_MODEL} not installed in Ollama")


@pytest.mark.ollama
@needs_text
def test_real_ollama_streaming_answer(real_client):
    sid = real_client.post("/api/sessions", json={}).json()["id"]
    events = ndjson(real_client.post("/api/chat", json={"session_id": sid, "text": "What is 12 plus 30? Reply with only the number."}))
    assert events[-1]["type"] == "done", events[-1]
    answer = "".join(e["t"] for e in events if e["type"] == "token")
    assert "42" in answer
    stats = events[-1]["stats"]
    assert stats["first_token_ms"] > 0 and stats["tokens_per_second"] > 0
    print(f"\n[real] first token {stats['first_token_ms']:.0f} ms, {stats['tokens_per_second']:.1f} tok/s")


@pytest.mark.ollama
@needs_text
def test_real_question_escalation(real_client):
    r = real_client.post("/api/questions/detect", json={"text": "Could the cache layer"}).json()
    assert r["method"] in ("llm", "rules")  # llm when the model returns valid JSON


@pytest.mark.ollama
@pytest.mark.slow
@needs_vision
def test_real_vision_reads_error_on_screen(real_client):
    sid = real_client.post("/api/sessions", json={"mode": "screen"}).json()["id"]
    img = encode_png_b64(
        text_image(
            [
                "Traceback (most recent call last):",
                '  File "app.py", line 12, in load_user',
                "    return users['user_id']",
                "KeyError: 'user_id'",
            ],
            size=(900, 260),
        )
    )
    t0 = time.perf_counter()
    events = ndjson(
        real_client.post(
            "/api/chat",
            json={
                "session_id": sid,
                "text": "What error is shown and what is the likely cause?",
                "image_b64": img,
                "screen_action": "find_errors",
            },
        )
    )
    elapsed = time.perf_counter() - t0
    assert events[1]["vision"] is True and events[1]["model"] == VISION_MODEL
    assert events[-1]["type"] == "done", events[-1]
    answer = "".join(e["t"] for e in events if e["type"] == "token").lower()
    assert "keyerror" in answer.replace(" ", "") or "user_id" in answer
    print(f"\n[real] vision analysis {elapsed:.1f} s on this machine")


@pytest.mark.asr
def test_real_whisper_transcribes_speech(tmp_path):
    from backend.transcription.asr import WhisperTranscriber

    audio = speech_wav("How does a hash map handle collisions?", tmp_path / "q.wav")
    if audio is None:
        pytest.skip("espeak-ng/ffmpeg not installed")
    asr = WhisperTranscriber("base")
    res = asr.transcribe(audio, beam_size=3)
    text = res.text.lower()
    assert "hash" in text and "collision" in text, text


@pytest.mark.asr
def test_real_audio_pipeline_end_to_end(real_client, tmp_path):
    """Real speech -> WebSocket -> Silero VAD -> Whisper -> question detection."""
    audio = speech_wav("What is the difference between a process and a thread?", tmp_path / "q.wav")
    if audio is None:
        pytest.skip("espeak-ng/ffmpeg not installed")
    sid = real_client.post("/api/sessions", json={"mode": "meeting"}).json()["id"]
    audio = np.concatenate([np.zeros(8000, np.float32), audio, np.zeros(24000, np.float32)])
    events = []
    with real_client.websocket_connect(f"/ws/audio?session_id={sid}", subprotocols=["veena", TOKEN]) as ws:
        while True:
            ev = ws.receive_json()
            if ev.get("state") == "ready":
                assert ev["vad"] == "silero"
                break
        for i in range(0, audio.size, 1024):
            ws.send_bytes(encode_frame(time.time() * 1000, audio[i : i + 1024]))
        ws.send_text('{"type": "stop"}')
        while True:
            ev = ws.receive_json()
            events.append(ev)
            if ev.get("state") == "stopped":
                break
    finals = [e for e in events if e["type"] == "final"]
    text = " ".join(f["text"] for f in finals).lower()
    assert "process" in text and "thread" in text, events
    assert any(e["type"] == "question" for e in events)
    print(f"\n[real] ASR final latency {finals[-1]['latency_ms']:.0f} ms")


@pytest.mark.embeddings
def test_real_embeddings_rank_and_threshold(tmp_path):
    from backend.memory.db import make_engine
    from backend.rag.embed import Embedder
    from backend.rag.index import VectorIndex
    from backend.rag.service import KnowledgeBase

    emb = Embedder()
    kb = KnowledgeBase(make_engine(tmp_path / "k.db"), emb, VectorIndex(tmp_path, emb.dim), 10 * 2**20)
    col = kb.create_collection("resume", "resume")
    resume = (
        "Asha Rao. Senior ML engineer.\n\n"
        "Built a document retrieval service with FAISS and sentence-transformers serving 2M queries per day.\n\n"
        "Led migration of batch ETL jobs from cron to Airflow.\n\n"
        "Hobbies: long-distance running and watercolour painting."
    )
    kb.ingest(col.id, "resume.txt", resume.encode())
    hits = kb.search("experience with vector search", [col.id])
    assert hits and "FAISS" in hits[0].text
    assert kb.search("recipe for chocolate cake", [col.id]) == []
