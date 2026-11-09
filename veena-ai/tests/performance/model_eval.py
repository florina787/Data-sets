"""Real-model evaluation of VEENA's own tasks, through VEENA's real API.

Nothing is simulated: real Ollama models, real MiniLM embeddings, real
Tesseract, VEENA's real retrieval, governance and semantic-spine code.

    python -m tests.performance.model_eval --text qwen2.5:1.5b qwen3:1.7b --vision qwen3-vl:2b-instruct

Writes docs/benchmarks/model_eval.json. Each task has a pass rule that is
checked mechanically and printed with the raw answer, so results can be audited.
"""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import Settings
from backend.screen.frames import encode_png_b64
from tests.conftest import TOKEN, ndjson
from tests.unit.test_screen_and_vision import text_image

DOC = (
    "# Project Falcon design\n\nFalcon stores document embeddings in a FAISS HNSW index with 32 neighbours per node, rebuilt nightly.\n\n"
    "The ingestion service runs at 02:00 UTC and processes PDF manuals from the shared drive.\n\n"
    "Search requests have a p95 latency budget of 300 ms; cache hits are served from Redis."
)
TRANSCRIPT = [
    "Asha: Let's ship the Falcon search update on Friday.",
    "Ravi: Agreed. I will update the runbook by Thursday.",
    "Mei: I still need to confirm the Redis memory limit with infra.",
    "Asha: Decision made, Friday release. Mei owns the Redis check.",
]


def _chat(c: TestClient, sid: str, text: str, **kw) -> dict:
    t0 = time.perf_counter()
    events = ndjson(c.post("/api/chat", json={"session_id": sid, "text": text, **kw}))
    done = events[-1]
    answer = "".join(e["t"] for e in events if e["type"] == "token").strip()
    return {
        "answer": answer,
        "seconds": round(time.perf_counter() - t0, 2),
        "ok": done.get("type") == "done",
        "first_token_ms": (done.get("stats") or {}).get("first_token_ms"),
        "tokens_per_second": (done.get("stats") or {}).get("tokens_per_second"),
        "flags": [f["kind"] for f in (done.get("governance") or {}).get("flags", [])],
        "spine": done.get("spine"),
        "error": done.get("message") if done.get("type") == "error" else None,
    }


def eval_text(c: TestClient, model: str, cid: str) -> list[dict]:
    c.patch("/api/settings", json={"text_model": model})
    out = []
    sid = c.post("/api/sessions", json={}).json()["id"]

    r = _chat(c, sid, "What is 12 plus 30? Reply with only the number.")
    out.append({"task": "arithmetic", "pass": "42" in r["answer"], "rule": "answer contains 42", **r})

    sid = c.post("/api/sessions", json={}).json()["id"]
    r = _chat(c, sid, "Which vector index does Project Falcon use, and what is its latency budget? Cite sources.", collection_ids=[cid])
    a = r["answer"].lower()
    out.append(
        {
            "task": "rag_grounded",
            "pass": "hnsw" in a and "300" in a and "[1]" in r["answer"],
            "rule": "mentions HNSW and 300 ms and cites [1]",
            **r,
        }
    )

    sid = c.post("/api/sessions", json={}).json()["id"]
    r = _chat(c, sid, "How many engineers built Falcon, which company owns it, and what does it cost per month?", collection_ids=[cid])
    out.append(
        {
            "task": "rag_trap_no_invention",
            "pass": "unbacked_claims" not in r["flags"],
            "rule": "does not state names or figures absent from the document (no unbacked_claims flag)",
            **r,
        }
    )

    sid = c.post("/api/sessions", json={"mode": "meeting"}).json()["id"]
    for line in TRANSCRIPT:
        c.post(f"/api/sessions/{sid}/transcript", json={"text": line})
    t0 = time.perf_counter()
    resp = c.post(f"/api/meeting/{sid}/summarize")
    secs = round(time.perf_counter() - t0, 2)
    notes = resp.json().get("notes", {}) if resp.status_code == 200 else {}
    decisions = json.dumps(notes.get("decisions", [])).lower()
    actions = json.dumps(notes.get("action_items", [])).lower()
    out.append(
        {
            "task": "meeting_notes",
            "pass": resp.status_code == 200 and "friday" in decisions and "runbook" in actions and "redis" in actions,
            "rule": "the Friday release is a decision, and both the runbook update and the Redis check are action items",
            "answer": json.dumps(notes)[:1200],
            "seconds": secs,
            "ok": resp.status_code == 200,
        }
    )

    iv = c.post("/api/interview", json={"role": "senior_ai_engineer", "focus": "architecture"}).json()["interview"]
    t0 = time.perf_counter()
    q = c.post(f"/api/interview/{iv['id']}/questions", json={"count": 2}).json()
    q_secs = round(time.perf_counter() - t0, 2)
    turn = q["turns"][0]
    t0 = time.perf_counter()
    fb = c.post(
        f"/api/interview/turns/{turn['id']}/evaluate",
        json={
            "answer": "I would chunk documents, embed them with a sentence transformer, store vectors in FAISS, retrieve the top passages "
            "and pass them to the model with citations, then evaluate retrieval with a labelled question set."
        },
    )
    out.append(
        {
            "task": "interview_practice",
            "pass": q.get("source") == "model" and fb.status_code == 200 and isinstance(fb.json().get("score"), (int, float)),
            "rule": "model generated the questions (not the fallback bank) and returned a numeric score",
            "answer": json.dumps({"question": turn["question"], "feedback": fb.json()})[:1200],
            "seconds": round(q_secs + time.perf_counter() - t0, 2),
            "ok": fb.status_code == 200,
        }
    )
    return out


def eval_vision(c: TestClient, model: str) -> list[dict]:
    c.patch("/api/settings", json={"vision_model": model})
    out = []
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
    sid = c.post("/api/sessions", json={"mode": "screen"}).json()["id"]
    r = _chat(c, sid, "What error is shown and what is the likely cause?", image_b64=img, screen_action="find_errors")
    out.append(
        {
            "task": "screen_error",
            "pass": "keyerror" in r["answer"].lower() or "user_id" in r["answer"],
            "rule": "names the KeyError or user_id",
            **r,
        }
    )

    img = encode_png_b64(text_image(["def is_palindrome(s):", "    s = s.lower()", "    return s == s[::-1]"], size=(900, 220)))
    sid = c.post("/api/sessions", json={"mode": "screen"}).json()["id"]
    r = _chat(c, sid, "Explain the code on the screen.", image_b64=img, screen_action="explain_code")
    out.append(
        {
            "task": "screen_code",
            "pass": "palindrome" in r["answer"].lower() or "revers" in r["answer"].lower(),
            "rule": "explains it as a palindrome/reverse check",
            **r,
        }
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", nargs="*", default=[])
    ap.add_argument("--vision", nargs="*", default=[])
    ap.add_argument("--out", default="docs/benchmarks/model_eval.json")
    args = ap.parse_args()

    results: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "machine": {
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 1e9, 1),
            "gpu": "none",
        },
        "models": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(token=TOKEN, data_dir=Path(tmp) / "data"))
        with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
            c.patch("/api/settings", json={"profile": "balanced", "onboarded": True})
            col = c.post("/api/knowledge/collections", json={"name": "Falcon", "kind": "docs"}).json()
            c.post(f"/api/knowledge/collections/{col['id']}/documents", files={"file": ("falcon-design.md", DOC.encode(), "text/markdown")})
            # Warm-up so the first measured task does not include model loading.
            for m in [*args.text, *args.vision]:
                c.post("/api/models/warm", json={"model": m})
            for m in args.text:
                print(f"== text {m}", flush=True)
                results["models"][m] = eval_text(c, m, col["id"])
            for m in args.vision:
                print(f"== vision {m}", flush=True)
                results["models"][m] = eval_vision(c, m)
    for m, tasks in results["models"].items():
        passed = sum(t["pass"] for t in tasks)
        print(f"\n{m}: {passed}/{len(tasks)} passed")
        for t in tasks:
            print(f"  {'PASS' if t['pass'] else 'FAIL'} {t['task']:<22} {t['seconds']:>6}s  {t['answer'][:110]!r}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
