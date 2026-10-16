"""Release Agent: checklist, manifest, rollback/migration plans, approval, deploy."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from app.config.settings import PROJECT_DIR
from app.database.session import session_scope
from app.governance import builds
from app.models import db as m


def git_commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_DIR, capture_output=True, text=True,
                           timeout=5)
        return r.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def prepare(version: str, qa_report: dict, regression_report: dict, security_report: dict, rca: dict | None) -> dict:
    b = builds.BUILDS[version]
    checklist = [
        {"item": "Full scenario suite passes", "passed": qa_report["failed"] == 0,
         "evidence": f"{qa_report['passed']}/{qa_report['executed']} passed on {version}"},
        {"item": "Regression tests for the defect pass", "passed": regression_report["failed"] == 0,
         "evidence": f"{regression_report['passed']}/{regression_report['executed']} regression scenarios"},
        {"item": "No open security findings", "passed": security_report["open_findings"] == 0,
         "evidence": f"{security_report['open_findings']} open finding(s)"},
        {"item": "Root cause confirmed with evidence", "passed": bool(rca and rca.get("confirmed")),
         "evidence": (rca or {}).get("root_cause") or "n/a"},
        {"item": "Build contains no injected defect", "passed": not b.defect_injected, "evidence": b.description},
        {"item": "Rollback plan documented", "passed": True, "evidence": "Redeploy previous build via release API"},
        {"item": "Database migrations", "passed": True, "evidence": "None required (mapping-only change)"},
    ]
    prev = builds.active_build("demo-production").version
    manifest = {"version": version, "status_mapping": b.status_mapping, "git_commit": git_commit(),
                "environments": list(builds.ENVIRONMENTS), "previous_production": prev,
                "test_evidence": {"suite_pass_rate": qa_report["pass_rate"],
                                  "regression_pass_rate": regression_report["pass_rate"]},
                "created_at": datetime.now(UTC).isoformat(), "deployment_type": "SIMULATED (in-process)"}
    plan = {"rollback_plan": [f"POST /api/v1/sdlc/releases/deploy {{version: '{prev}', environment: 'demo-production'}}",
                              "Re-run regression suite and post-release simulation", "Record rollback in audit trail"],
            "migration_plan": ["No schema migrations in this release"]}
    ready = all(c["passed"] for c in checklist)
    with session_scope() as s:
        row = s.get(m.ReleaseVersion, version) or m.ReleaseVersion(version=version, status="DRAFT")
        row.status = "READY_FOR_APPROVAL" if ready else "BLOCKED"
        row.manifest = {**manifest, **plan, "checklist": checklist}
        row.notes = b.description
        s.merge(row)
    return {"version": version, "ready": ready, "checklist": checklist, "manifest": manifest, **plan}


def mark_deployed(version: str, env: str, approver: str | None) -> None:
    with session_scope() as s:
        row = s.get(m.ReleaseVersion, version) or m.ReleaseVersion(version=version, status="DRAFT")
        row.status, row.environment, row.approved_by = f"DEPLOYED:{env}", env, approver
        row.deployed_at = datetime.now(UTC)
        s.merge(row)


def list_releases() -> list[dict]:
    with session_scope() as s:
        rows = s.query(m.ReleaseVersion).order_by(m.ReleaseVersion.created_at.desc()).all()
        return [{"version": r.version, "status": r.status, "environment": r.environment, "approved_by": r.approved_by,
                 "deployed_at": r.deployed_at.isoformat() if r.deployed_at else None, "manifest": r.manifest,
                 "notes": r.notes} for r in rows]
