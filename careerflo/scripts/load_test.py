"""Concurrency smoke test against a running Career_flo server (no external services needed).

    backend/.venv/bin/python scripts/load_test.py --base http://localhost:7860 --users 10 --chats 3

Each simulated user registers (local auth mode), uploads a resume, searches jobs, ranks them and builds a career graph.
In parallel, --chats users hold a streamed assistant conversation (Qwen). Reports per-step latency percentiles,
errors and SSE completion. Results are MEASURED on the machine you run it against.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid

import httpx

RESUME = (b"Alex Morgan\nalex@example.com\n\nSUMMARY\nAI engineer.\n\nEXPERIENCE\nSenior AI Engineer, Example Robotics - Mar 2020 - Present\n"
          b"- Built a RAG service with LangGraph and FastAPI used by 5,000 people\n- Cut cloud costs by 20% using Docker\n\n"
          b"EDUCATION\nBSc Computer Science, University of Waterloo, 2015\n\nSKILLS\nPython, SQL, LLMs, RAG, LangGraph, FastAPI, Docker, AWS\n")


async def user_flow(c: httpx.AsyncClient, i: int, lat: dict, errors: list) -> None:
    async def step(name, coro):
        t0 = time.perf_counter()
        try:
            r = await coro
            if r.status_code >= 400:
                errors.append(f"{name}: {r.status_code} {r.text[:120]}")
            lat.setdefault(name, []).append((time.perf_counter() - t0) * 1000)
            return r
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}")
            return None

    r = await step("register", c.post("/api/auth/register", json={"email": f"load-{uuid.uuid4().hex[:10]}@example.com", "password": "CorrectHorse42"}))
    if not r or r.status_code != 201:
        return
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await step("upload_resume", c.post("/api/resumes", headers=h, files={"file": ("r.txt", RESUME, "text/plain")}))
    s = await step("job_search", c.post("/api/jobs/search", headers=h, json={"query": "AI Engineer", "limit": 10}))
    ids = [j["id"] for j in (s.json()["jobs"] if s and s.status_code == 200 else [])][:3]
    if ids:
        await step("job_matching", c.post("/api/match", headers=h, json={"job_ids": ids}))
        await c.post(f"/api/jobs/{ids[0]}/save", headers=h)
    await step("career_graph", c.post("/api/career-graph", headers=h, json={}))
    await step("usage", c.get("/api/usage", headers=h))


async def chat_flow(c: httpx.AsyncClient, lat: dict, errors: list, sse: list) -> None:
    r = await c.post("/api/auth/register", json={"email": f"chat-{uuid.uuid4().hex[:10]}@example.com", "password": "CorrectHorse42"})
    if r.status_code != 201:
        errors.append(f"chat register: {r.status_code}")
        sse.append(False)
        return
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cid = (await c.post("/api/chat/conversations", headers=h)).json()["id"]
    t0 = time.perf_counter()
    first = None
    done = False
    try:
        async with c.stream("POST", f"/api/chat/conversations/{cid}/messages", headers=h,
                            json={"content": "Find AI Engineer jobs in Toronto"}, timeout=600) as s:
            async for line in s.aiter_lines():
                if not line.startswith("data: "):
                    continue
                ev = json.loads(line[6:])
                if ev["type"] == "token" and first is None:
                    first = (time.perf_counter() - t0) * 1000
                if ev["type"] == "done":
                    done = True
                if ev["type"] == "error":
                    errors.append("chat: " + ev["message"])
    except Exception as exc:  # noqa: BLE001
        errors.append(f"chat: {type(exc).__name__}")
    lat.setdefault("chat_first_token", []).append(first or float("nan"))
    lat.setdefault("chat_total", []).append((time.perf_counter() - t0) * 1000)
    sse.append(done)


def pct(xs, p):
    xs = sorted(x for x in xs if x == x)
    return round(xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]) if xs else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:7860")
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--chats", type=int, default=3)
    a = ap.parse_args()
    lat: dict[str, list[float]] = {}
    errors: list[str] = []
    sse: list[bool] = []
    t0 = time.perf_counter()
    async with httpx.AsyncClient(base_url=a.base, timeout=300) as c:
        await asyncio.gather(*[user_flow(c, i, lat, errors) for i in range(a.users)], *[chat_flow(c, lat, errors, sse) for _ in range(a.chats)])
    out = {"users": a.users, "concurrent_chats": a.chats, "wall_seconds": round(time.perf_counter() - t0, 1),
           "errors": errors, "sse_completed": f"{sum(sse)}/{len(sse)}",
           "latency_ms": {k: {"p50": pct(v, .5), "p95": pct(v, .95), "max": pct(v, 1), "n": len(v)} for k, v in lat.items()}}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
