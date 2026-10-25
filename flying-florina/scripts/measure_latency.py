"""Measure cold and warm latency of rules-only demo queries on this machine (no fabricated numbers)."""
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="ff-perf-")
os.environ.update({"FF_DATA_DIR": tmp, "FF_GENERATED_DIR": tmp + "/gen"})
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
t0 = time.perf_counter()
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.workflows.intent import SUGGESTIONS  # noqa: E402

out = {"machine": {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count()}}
with TestClient(app) as c:
    out["startup_incl_seed_s"] = round(time.perf_counter() - t0, 2)
    h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"user_id": "fde.sam"}).json()["data"]["token"]}
    rows = []
    for q in SUGGESTIONS:
        times = []
        for _ in range(4):
            s = time.perf_counter()
            r = c.post("/api/chat/query", headers=h, json={"query": q}).json()["data"]
            times.append((time.perf_counter() - s) * 1000)
        rows.append({"workflow": r["workflow"], "cold_ms": round(times[0]), "warm_median_ms": round(statistics.median(times[1:]))})
    out["queries"] = rows
print(json.dumps(out, indent=1))
