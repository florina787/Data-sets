"""Run the seeded BR-101 journey against a throwaway database and write sample reports to
evaluation/reports/. Every number in the reports is computed from the fixtures at run time.
    python -m scripts.generate_reports
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evaluation" / "reports"


def main() -> None:
    tmp = tempfile.mkdtemp()
    os.environ.update({"DATABASE_URL": f"sqlite:///{tmp}/r.db", "EVAL_EXECUTION": "inline", "APP_ENV": "demo", "LLM_MODE": "deterministic"})
    from fastapi.testclient import TestClient
    from app.main import create_app

    H = lambda u, **x: {"X-Demo-User": u, **x}  # noqa: E731
    with TestClient(create_app()) as c:
        def ok(r):
            assert r.status_code < 300, r.text
            return r.json()
        d = ok(c.get("/api/changes/BR-101", headers=H("u-po")))
        for cl in d["clarifications"]:
            ok(c.post("/api/changes/BR-101/clarifications", headers=H("u-po"), json={"key": cl["key"], "use_suggested": True}))
        ok(c.post("/api/changes/BR-101/requirements/approve", headers=H("u-po")))
        ok(c.post("/api/changes/BR-101/investigate", headers=H("u-ml-eng")))
        ok(c.post("/api/changes/BR-101/impact/accept", headers=H("u-po")))
        ok(c.post("/api/changes/BR-101/candidates", headers=H("u-cv-eng"), json={"model_id": "shade-matcher-v2.4.0-rc1"}))
        r1 = ok(c.post("/api/changes/BR-101/evaluations", headers=H("u-ml-eng")))
        ok(c.post("/api/changes/BR-101/candidates", headers=H("u-cv-eng"), json={"model_id": "shade-matcher-v2.4.0-rc2"}))
        ok(c.post("/api/changes/BR-101/reviews", headers=H("u-qa"), json={"kind": "code", "decision": "APPROVE"}))
        r2 = ok(c.post("/api/changes/BR-101/evaluations", headers=H("u-ml-eng")))
        for u, k in (("u-domain", "domain"), ("u-privacy", "privacy")):
            ok(c.post("/api/changes/BR-101/reviews", headers=H(u), json={"kind": k, "decision": "APPROVE"}))
        ok(c.post("/api/changes/BR-101/release-approvals", headers=H("u-release"), json={"decision": "APPROVED"}))
        rel = ok(c.post("/api/changes/BR-101/releases", headers=H("u-release", **{"Idempotency-Key": "report"}), json={}))["release"]
        alert = None
        for _ in range(8):
            w = ok(c.post(f"/api/releases/{rel['id']}/monitoring/advance", headers=H("u-ops")))
            if w["new_alerts"]:
                alert = w["new_alerts"][0]
                break
            if w["window"]["allocation_pct"] < 25:
                ok(c.post(f"/api/releases/{rel['id']}/promote", headers=H("u-release")))
        ok(c.post(f"/api/alerts/{alert['id']}/investigate", headers=H("u-ops")))
        rb = ok(c.post(f"/api/releases/{rel['id']}/rollback-requests", headers=H("u-ops", **{"Idempotency-Key": "rb"}),
                       json={"reason": "DEV-T3 warm_indoor outcome regression", "alert_id": alert["id"]}))["rollback"]
        ok(c.post(f"/api/rollbacks/{rb['id']}/decision", headers=H("u-release"), json={"decision": "APPROVE"}))
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "BR-101-change-report.md").write_text(c.get("/api/changes/BR-101/report", headers=H("u-po")).text)
        mon = ok(c.get(f"/api/releases/{rel['id']}/monitoring", headers=H("u-ops")))
        summary = {}
        for name, run in (("rc1", r1), ("rc2", r2)):
            full = ok(c.get(f"/api/evaluations/{run['id']}", headers=H("u-qa")))
            s = full["summary"]
            summary[name] = {"candidate": full["candidate_model_id"], "outcome": full["outcome"],
                             "overall_top1_delta_pp": s["overall"]["delta"]["top1_delta_pp"],
                             "overall_top1": [s["overall"]["baseline"]["top1_accuracy_pct"], s["overall"]["candidate"]["top1_accuracy_pct"]],
                             "eligible": s["eligible_total"], "exclusions": s["exclusions"],
                             "cells": {k: {"n": v["baseline"]["n_eligible"], "baseline_top1": v["baseline"]["top1_accuracy_pct"],
                                           "candidate_top1": v["candidate"]["top1_accuracy_pct"], "delta_pp": v["delta"]["top1_delta_pp"],
                                           "ci95_pp": v["delta_ci95_pp"], "coverage_delta_pp": v["delta"]["coverage_delta_pp"]}
                                       for k, v in s["cells"].items()},
                             "gates": {g["gate_id"]: g["status"] for g in s["gates"]}}
        summary["monitoring"] = {"alert": alert, "windows": [{k: w[k] for k in ("index", "allocation_pct", "simulated_sessions", "labelled")} for w in mon["windows"]],
                                 "investigation": mon["alerts"][0]["investigation"], "rollback": mon["rollbacks"][-1]}
        summary["final_status"] = ok(c.get("/api/changes/BR-101", headers=H("u-po")))["change"]["status"]
        summary["telemetry"] = ok(c.get("/api/changes/BR-101/telemetry", headers=H("u-po")))
        (OUT / "BR-101-summary.json").write_text(json.dumps(summary, indent=1))
        print(json.dumps({k: (v["outcome"], v["overall_top1_delta_pp"]) for k, v in summary.items() if k in ("rc1", "rc2")}),
              summary["monitoring"]["alert"]["scope"], summary["final_status"])


if __name__ == "__main__":
    main()
