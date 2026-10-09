"""Command line helpers: ``python -m app.cli reset`` (deterministic demo reset)."""

from __future__ import annotations

import sys
import time

import httpx

from app import auth
from app.config import get_settings


def reset() -> int:
    settings = get_settings()
    base = f"http://{settings.api_host}:{settings.api_port}"
    try:
        httpx.get(f"{base}/api/health", timeout=1.5).raise_for_status()
        running = True
    except httpx.HTTPError:
        running = False
    if running:
        with httpx.Client(base_url=base, timeout=120) as client:
            token = client.post("/api/auth/login", json={"username": "eli.engineer",
                                                          "password": auth.DEMO_PASSWORD}).json()["token"]
            job = client.post("/api/demo/reset", headers={"Authorization": f"Bearer {token}"}).json()["job_id"]
            while (status := client.get(f"/api/jobs/{job}").json().get("status", "running")) == "running":
                time.sleep(1)
        print(f"Reset through the running server: {status}")
        return 0 if status == "succeeded" else 1
    from app.services import system

    result = system.reset_demo("cli")
    print(f"Reset offline: baseline {result['baseline_revision'][:10]}, storefront {result['deployment']['status']}")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command != "reset":
        print("usage: python -m app.cli reset")
        raise SystemExit(2)
    raise SystemExit(reset())
