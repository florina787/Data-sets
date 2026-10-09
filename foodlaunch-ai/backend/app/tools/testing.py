"""QA tool: run the protected acceptance suite against an exact revision.

Tests come from the platform's fixture store (never from the candidate tree)
and must match the hashes frozen when the requirement set was approved, so an
agent cannot weaken or delete a regression test to get a green result.
"""

from __future__ import annotations

import json
import shutil
import sys

from app.config import FIXTURES, get_settings
from app.db import new_id, now_iso, session, sha256_text
from app.errors import ToolRejected
from app.records import evidence
from app.tools import runner, workspace

TESTS_DIR = FIXTURES / "acceptance_tests"
SUPPORT_FILES = ("conftest.py",)


def plan_hashes(files: list[str]) -> dict:
    """Hash every protected file of a test plan (support files included)."""
    hashes = {}
    for name in [*SUPPORT_FILES, *files]:
        if "/" in name or "\\" in name or not name.endswith(".py"):
            raise ToolRejected("Invalid test file name", name=name)
        hashes[name] = sha256_text((TESTS_DIR / name).read_text(encoding="utf-8"))
    combined = sha256_text(json.dumps(hashes, sort_keys=True))
    return {"files": files, "hashes": hashes, "tests_hash": combined}


def run_acceptance(
    *,
    run_id: str | None,
    revision: str,
    suite_version: int,
    plan: dict,
    purpose: str,
) -> dict:
    workspace.validate_revision(revision)
    current = plan_hashes(plan["files"])
    if current["tests_hash"] != plan["tests_hash"]:
        changed = [f for f, h in current["hashes"].items() if plan["hashes"].get(f) != h]
        raise ToolRejected(
            "Protected acceptance tests differ from the approved test plan", changed=changed
        )
    settings = get_settings()
    test_run_id = new_id("TR")
    run_dir = settings.test_runs_dir / test_run_id
    src = workspace.export_revision(revision, run_dir / "src")
    tests = run_dir / "tests"
    tests.mkdir(parents=True)
    for name in current["hashes"]:
        shutil.copy2(TESTS_DIR / name, tests / name)
    (run_dir / "pytest.ini").write_text("[pytest]\n")
    (run_dir / "home").mkdir()
    report_path = run_dir / "report.json"
    argv = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--color=no",
            "-c", str(run_dir / "pytest.ini"), "--rootdir", str(tests),
            *[str(tests / f) for f in plan["files"]]]
    started = now_iso()
    with session() as conn:
        conn.execute(
            "INSERT INTO test_runs (id, run_id, revision, suite_version, tests_hash, purpose, command,"
            " status, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)",
            (test_run_id, run_id, revision, suite_version, plan["tests_hash"], purpose,
             " ".join(argv[1:]).replace(str(run_dir), "<run>"), started),
        )
    result = runner.run(
        argv, cwd=run_dir,
        env=runner.scrubbed_env({"PYTHONPATH": str(src), "ACCEPTANCE_REPORT": str(report_path)},
                                home=run_dir / "home"),
    )
    report = json.loads(report_path.read_text()) if report_path.exists() else {"tests": []}
    outcomes = [t["outcome"] for t in report["tests"]]
    if result.exit_code == 0 and outcomes and all(o == "passed" for o in outcomes):
        status = "passed"
    elif result.exit_code == 1 and outcomes:
        status = "failed"
    else:
        status = "error"
    with session() as conn:
        conn.execute(
            "UPDATE test_runs SET exit_code = ?, status = ?, duration_s = ?, output = ?,"
            " report_json = ?, finished_at = ? WHERE id = ?",
            (result.exit_code, status, result.duration_s, result.output, json.dumps(report),
             now_iso(), test_run_id),
        )
        conn.executemany(
            "INSERT INTO test_results (test_run_id, nodeid, outcome, ac_ids_json,"
            " regression_ids_json, critical, duration_s, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (test_run_id, t["nodeid"], t["outcome"], json.dumps(t["acceptance_criteria"]),
                 json.dumps(t["regression_ids"]), int(t["critical"]), t["duration_s"], t["message"])
                for t in report["tests"]
            ],
        )
    passed = outcomes.count("passed")
    evidence("test_run", "pytest (acceptance suite)",
             f"{passed}/{len(outcomes)} passed, exit code {result.exit_code} ({purpose})",
             "tool", revision=revision, run_id=run_id, ref_table="test_runs", ref_id=test_run_id)
    return {"id": test_run_id, "status": status, "exit_code": result.exit_code,
            "passed": passed, "total": len(outcomes),
            "failed": [t["nodeid"] for t in report["tests"] if t["outcome"] != "passed"],
            "duration_s": result.duration_s}
