"""Offline check: run every seeded demo and report generation with external egress blocked.

Runs in-process with OFFLINE_MODE=true and the egress guard installed, with no LLM.
Fails if any workflow errors or if anything attempted to reach a non-loopback address.
Usage: backend/.venv/bin/python scripts/offline_check.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="ff-offline-")
os.environ.update({"FF_DATA_DIR": tmp, "FF_GENERATED_DIR": tmp + "/gen", "OFFLINE_MODE": "true", "DEMO_MODE": "true", "LLM_ENABLED": "false"})
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.core import egress  # noqa: E402
from app.main import app  # noqa: E402
from app.workflows.intent import SUGGESTIONS  # noqa: E402

failures = []
with TestClient(app) as c:
    assert egress.status()["installed"], "egress guard not installed"
    tok = c.post("/api/auth/login", json={"user_id": "planner.marco"}).json()["data"]["token"]
    h = {"Authorization": "Bearer " + tok}
    for q in SUGGESTIONS:
        t0 = time.perf_counter()
        r = c.post("/api/chat/query", headers=h, json={"query": q}).json()["data"]
        ok = r["finished"] and not r["state"]["errors"]
        print(f"{'PASS' if ok else 'FAIL'} {r['workflow']:26s} {r['status']:20s} {1000 * (time.perf_counter() - t0):6.0f} ms")
        if not ok:
            failures.append(q)
    for kind, fmt in [("executive_brief", "pdf"), ("one_page_brief", "pdf"), ("work_orders", "csv"), ("architecture", "md")]:
        r = c.post("/api/reports/generate", headers=h, json={"kind": kind, "fmt": fmt})
        print(("PASS" if r.status_code == 200 else "FAIL"), "report", kind, fmt)
        if r.status_code != 200:
            failures.append(kind)
    blocked = egress.status()["blocked_attempts"]
    print(f"Blocked external egress attempts: {blocked}")
    if blocked:
        failures.append(f"egress attempts: {egress.status()['recent_blocked']}")
print("OFFLINE CHECK", "PASSED" if not failures else f"FAILED {failures}")
sys.exit(1 if failures else 0)
