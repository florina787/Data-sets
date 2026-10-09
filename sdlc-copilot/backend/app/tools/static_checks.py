"""Review tools: ruff with the platform-owned policy, plus a forbidden-call scan.

These are automated checks, not a security certification.
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path

from app.config import FIXTURES, get_settings
from app.db import new_id, now_iso, session
from app.records import evidence
from app.tools import runner, workspace

POLICY = FIXTURES / "policy" / "ruff.toml"
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {"subprocess", "pickle", "marshal", "ctypes", "socket"}
FORBIDDEN_ATTRS = {("os", "system"), ("os", "popen"), ("os", "exec"), ("shutil", "rmtree")}


def _scan(root: Path) -> list[dict]:
    findings = []
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    if name.split(".")[0] in FORBIDDEN_MODULES:
                        findings.append({"file": rel, "line": node.lineno, "rule": "forbidden-import",
                                         "message": f"import of '{name}' is not permitted"})
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                    findings.append({"file": rel, "line": node.lineno, "rule": "forbidden-call",
                                     "message": f"call to '{func.id}' is not permitted"})
                if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                        and (func.value.id, func.attr) in FORBIDDEN_ATTRS):
                    findings.append({"file": rel, "line": node.lineno, "rule": "forbidden-call",
                                     "message": f"call to '{func.value.id}.{func.attr}' is not permitted"})
    return findings


def _record(run_id, revision, tool, command, exit_code, status, output, findings) -> str:
    check_id = new_id("SC")
    with session() as conn:
        conn.execute(
            "INSERT INTO static_checks (id, run_id, revision, tool, command, exit_code, status, output,"
            " findings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (check_id, run_id, revision, tool, command, exit_code, status, output,
             json.dumps(findings), now_iso()),
        )
    evidence("static_check", tool, f"{tool}: {status} ({len(findings)} findings)", "tool",
             revision=revision, run_id=run_id, ref_table="static_checks", ref_id=check_id)
    return check_id


def run_static_checks(run_id: str | None, revision: str) -> list[dict]:
    settings = get_settings()
    work = settings.var_dir / "static" / new_id("SRC")
    src = workspace.export_revision(revision, work)
    (work / "home").mkdir(exist_ok=True)
    argv = [sys.executable, "-m", "ruff", "check", "--no-cache", "--config", str(POLICY),
            "--output-format", "json", "storefront"]
    result = runner.run(argv, cwd=src, env=runner.scrubbed_env(home=work / "home"), timeout_s=60)
    try:
        ruff_findings = [
            {"file": f["filename"].replace(str(src) + "/", ""), "line": f["location"]["row"],
             "rule": f["code"], "message": f["message"]}
            for f in json.loads(result.output or "[]")
        ]
    except json.JSONDecodeError:
        ruff_findings = [{"file": "-", "line": 0, "rule": "ruff-error", "message": result.output[-500:]}]
    ruff_status = "passed" if result.exit_code == 0 else "failed"
    results = [{
        "id": _record(run_id, revision, "ruff", "ruff check --config fixtures/policy/ruff.toml storefront",
                      result.exit_code, ruff_status, result.output[-20000:], ruff_findings),
        "tool": "ruff", "status": ruff_status, "findings": ruff_findings, "exit_code": result.exit_code,
    }]
    scan = _scan(src / "storefront")
    scan_status = "passed" if not scan else "failed"
    results.append({
        "id": _record(run_id, revision, "forbidden-call-scan", "ast scan storefront/**/*.py",
                      0 if not scan else 1, scan_status, json.dumps(scan, indent=1), scan),
        "tool": "forbidden-call-scan", "status": scan_status, "findings": scan,
        "exit_code": 0 if not scan else 1,
    })
    shutil.rmtree(work, ignore_errors=True)
    return results
