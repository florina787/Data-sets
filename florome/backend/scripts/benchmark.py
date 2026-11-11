"""Measure representative workflows in-process (SQLite, sandbox connector). Prints JSON. Not a production benchmark."""

import json
import secrets
import statistics
import tempfile
import time
import tracemalloc

from fastapi.testclient import TestClient

from florome.config import Settings
from florome.main import create_app

H = lambda r: {"Authorization": f"Bearer demo-meridian-{r}"}  # noqa: E731


def run(n: int = 10) -> dict:
    rca_ms, plan_ms, exec_ms, total_ms = [], [], [], []
    tracemalloc.start()
    for _ in range(n):
        app = create_app(Settings(database_url=f"sqlite:///{tempfile.mktemp(suffix='.db')}"))
        with TestClient(app) as c:
            inc = c.get("/api/v1/incidents", headers=H("viewer")).json()["items"][0]["id"]
            t0 = time.perf_counter()
            c.post(f"/api/v1/rca/{inc}", headers=H("operator"))
            t1 = time.perf_counter()
            p = c.post("/api/v1/remediations", json={"incident_id": inc}, headers=H("operator")).json()
            t2 = time.perf_counter()
            c.post("/api/v1/approvals", json={"plan_id": p["id"], "decision": "approve", "plan_hash": p["plan_hash"], "nonce": secrets.token_hex(12)}, headers=H("approver"))
            t3 = time.perf_counter()
            out = c.post("/api/v1/executions", json={"plan_id": p["id"]}, headers=H("operator")).json()
            t4 = time.perf_counter()
            assert out["status"] == "succeeded"
            rca_ms.append((t1 - t0) * 1e3); plan_ms.append((t2 - t1) * 1e3); exec_ms.append((t4 - t3) * 1e3); total_ms.append((t4 - t0) * 1e3)
    _, peak = tracemalloc.get_traced_memory()
    med = lambda v: round(statistics.median(v), 1)  # noqa: E731
    return {"runs": n, "median_ms": {"rca_collect_and_analyse": med(rca_ms), "plan": med(plan_ms), "execute_5_steps_and_validate": med(exec_ms),
            "detect_to_validated_total": med(total_ms)}, "max_total_ms": round(max(total_ms), 1), "python_peak_traced_mb": round(peak / 1e6, 1),
            "setup": "SQLite file DB, in-process TestClient, sandbox connector (18 evidence items, 9 hypotheses)"}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
