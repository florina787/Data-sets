"""Network-disconnected check of VEENA's features with REAL local models.

Run inside a network namespace that has only loopback (no route to the internet):

    unshare -rn sh -c 'python3 tests/performance/lo_up.py && \
      OLLAMA_HOST=127.0.0.1:11500 ollama serve & sleep 5; \
      OLLAMA_URL=http://127.0.0.1:11500 .venv/bin/python -m tests.performance.offline_check; \
      pkill -f "ollama serve"; pkill -f llama-server'

Prerequisite: the models were downloaded once beforehand (as Setup does). The
check first proves the internet is unreachable, then exercises each feature.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import Settings
from backend.screen.frames import encode_png_b64
from tests.conftest import TOKEN, ndjson, speech_wav
from tests.unit.test_screen_and_vision import text_image

TEXT = os.environ.get("VEENA_TEXT_MODEL", "qwen2.5:1.5b")
VISION = os.environ.get("VEENA_VISION_MODEL", "qwen3-vl:2b-instruct")


def internet_reachable() -> bool:
    for host in [("1.1.1.1", 443), ("8.8.8.8", 53)]:
        try:
            socket.create_connection(host, timeout=3).close()
            return True
        except OSError:
            pass
    return False


def main() -> None:
    results: dict = {"internet_reachable": internet_reachable(), "features": {}}
    assert not results["internet_reachable"], "this check must run with the network disconnected"
    url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(token=TOKEN, data_dir=Path(tmp) / "data", ollama_url=url))
        with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
            c.patch("/api/settings", json={"text_model": TEXT, "vision_model": VISION, "asr_model": "base", "onboarded": True})

            def record(name, fn):
                t0 = time.perf_counter()
                try:
                    detail = fn()
                    results["features"][name] = {"ok": True, "seconds": round(time.perf_counter() - t0, 1), "detail": detail}
                except Exception as e:  # noqa: BLE001
                    results["features"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
                print(name, json.dumps(results["features"][name])[:300], flush=True)

            def chat():
                sid = c.post("/api/sessions", json={}).json()["id"]
                ev = ndjson(c.post("/api/chat", json={"session_id": sid, "text": "What is 12 plus 30? Reply with only the number."}))
                assert ev[-1]["type"] == "done", ev[-1]
                return "".join(e["t"] for e in ev if e["type"] == "token").strip()

            def documents():
                col = c.post("/api/knowledge/collections", json={"name": "Offline", "kind": "docs"}).json()
                up = c.post(
                    f"/api/knowledge/collections/{col['id']}/documents",
                    files={
                        "file": (
                            "falcon.md",
                            b"# Falcon\n\nFalcon uses a FAISS HNSW index.\n\nSearch has a p95 latency budget of 300 ms.",
                            "text/markdown",
                        )
                    },
                )
                assert up.status_code == 200, up.text
                sid = c.post("/api/sessions", json={}).json()["id"]
                ev = ndjson(
                    c.post("/api/chat", json={"session_id": sid, "text": "What is Falcon's latency budget?", "collection_ids": [col["id"]]})
                )
                assert ev[-1]["type"] == "done", ev[-1]
                cites = ev[1].get("citations", [])
                assert cites, "no passage retrieved"
                return {"answer": "".join(e["t"] for e in ev if e["type"] == "token").strip()[:200], "citations": len(cites)}

            def meeting():
                sid = c.post("/api/sessions", json={"mode": "meeting"}).json()["id"]
                for line in ["Asha: We ship on Friday.", "Ravi: I will update the runbook by Thursday."]:
                    c.post(f"/api/sessions/{sid}/transcript", json={"text": line})
                r = c.post(f"/api/meeting/{sid}/summarize")
                assert r.status_code == 200, r.text
                return r.json()["notes"].get("summary", "")[:200]

            def interview():
                iv = c.post("/api/interview", json={"role": "senior_ai_engineer", "focus": "architecture"}).json()["interview"]
                q = c.post(f"/api/interview/{iv['id']}/questions", json={"count": 1}).json()
                return {"source": q["source"], "question": q["turns"][0]["question"][:160]}

            def screen():
                img = encode_png_b64(text_image(["Traceback (most recent call last):", "KeyError: 'user_id'"], size=(800, 200)))
                sid = c.post("/api/sessions", json={"mode": "screen"}).json()["id"]
                ev = ndjson(c.post("/api/chat", json={"session_id": sid, "text": "What error is shown?", "image_b64": img}))
                assert ev[-1]["type"] == "done", ev[-1]
                return {"vision": ev[1].get("vision"), "answer": "".join(e["t"] for e in ev if e["type"] == "token").strip()[:200]}

            def speech():
                wav = speech_wav("What is a hash map?", Path(tmp) / "q.wav")
                if wav is None:
                    raise RuntimeError("espeak-ng/ffmpeg not available to synthesise test speech")
                asr = app.state.veena.asr("base", None)
                res = asr.transcribe(np.asarray(wav, dtype=np.float32))
                return res.text

            for name, fn in [
                ("chat", chat),
                ("documents", documents),
                ("meeting_notes", meeting),
                ("interview", interview),
                ("screen", screen),
                ("speech_to_text", speech),
            ]:
                record(name, fn)
    out = Path("docs/benchmarks/offline_check.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
