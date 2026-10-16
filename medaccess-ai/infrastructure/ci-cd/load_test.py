"""Minimal async load test for capacity planning (synthetic data only).

Usage: python infrastructure/ci-cd/load_test.py --base http://localhost:8000 --concurrency 8 --requests 200
Reports throughput and latency percentiles measured on *your* hardware. Results are not
transferable to other machines; record them in docs/deployment/capacity-planning.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time

import httpx

CITIES = ["Toronto", "North York", "Scarborough", "Etobicoke", "Mississauga", "Markham", "Vaughan", "M5V"]
SERVICES = ["MRI", "CT", "ULTRASOUND", "XRAY", "BLOOD_TEST", "SPECIALIST"]


async def main(base: str, concurrency: int, total: int) -> dict:
    async with httpx.AsyncClient(base_url=base, timeout=60) as c:
        tok = (await c.post("/api/v1/auth/demo-login", json={"user_id": "usr-patient-demo"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {tok}"}
        lat: list[float] = []
        errors = 0
        sem = asyncio.Semaphore(concurrency)
        rng = random.Random(1)

        async def one() -> None:
            nonlocal errors
            body = {"service": rng.choice(SERVICES), "location": rng.choice(CITIES), "radius_km": rng.choice([10, 25, 50]),
                    "requisition_status": "HAS_REQUISITION"}
            async with sem:
                t0 = time.perf_counter()
                r = await c.post("/api/v1/search/appointments", json=body, headers=headers)
                lat.append((time.perf_counter() - t0) * 1000)
                if r.status_code != 200:
                    errors += 1

        t0 = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(total)))
        wall = time.perf_counter() - t0
    s = sorted(lat)
    return {"requests": total, "concurrency": concurrency, "errors": errors, "wall_s": round(wall, 2),
            "throughput_rps": round(total / wall, 2), "p50_ms": round(statistics.median(s), 1),
            "p95_ms": round(s[int(0.95 * (len(s) - 1))], 1), "p99_ms": round(s[int(0.99 * (len(s) - 1))], 1),
            "max_ms": round(s[-1], 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--requests", type=int, default=200)
    a = ap.parse_args()
    print(json.dumps(asyncio.run(main(a.base, a.concurrency, a.requests)), indent=2))
