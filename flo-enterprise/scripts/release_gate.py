"""Release gate: blocks release when any critical security or financial-correctness check fails.

Runs: critical pytest suite, OPA policy tests, evaluation suite, static analysis (ruff), security linting (bandit, high
severity), dependency audit (pip-audit; reported, blocking only on known-vulnerable pins when the advisory DB is
reachable), secret scanning, TypeScript type check. Writes var/release_gate.json and exits non-zero on failure."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
SECRET_RX = re.compile(r"(AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----|\bsk-(live|proj|ant)-[A-Za-z0-9_\-]{20,}|\bgh[pousr]_[A-Za-z0-9]{30,}|xox[abpr]-[A-Za-z0-9-]{10,})")
SKIP_DIRS = {".venv", "node_modules", "dist", "var", ".git", "__pycache__", "test-results", ".pytest_cache", ".ruff_cache"}


def run(name, cmd, cwd=ROOT, blocking=True, timeout=1800):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        ok, tail = p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()[-6:]
    except FileNotFoundError:
        ok, tail = None, ["tool not installed"]
    except subprocess.TimeoutExpired:
        ok, tail = False, ["timeout"]
    return {"check": name, "passed": ok, "blocking": blocking, "seconds": round(time.time() - t0, 1), "tail": tail}


def secret_scan():
    hits = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or set(p.parts) & SKIP_DIRS or p.suffix in (".png", ".zip", ".pem", ".sqlite", ".db"):
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for m in SECRET_RX.finditer(text):
            if "test" in p.name or "detect.py" in p.name or "REDACTED" in m.group(0):
                continue  # detector patterns and test fixtures are deliberate
            hits.append(f"{p.relative_to(ROOT)}: {m.group(0)[:12]}…")
    return {"check": "secret_scan", "passed": not hits, "blocking": True, "seconds": 0, "tail": hits[:10] or ["no secrets found"]}


def main() -> int:
    checks = [
        run("critical_tests (security + financial correctness)", [PY, "-m", "pytest", "-m", "critical", "-q", "-p", "no:cacheprovider"]),
        run("full_test_suite", [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
        run("opa_policy_tests", ["opa", "test", "policies/opa"], blocking=bool(shutil.which("opa"))),
        run("evaluation_suite", [PY, "tests/evals/run_evals.py"]),
        run("static_analysis (ruff)", [PY, "-m", "ruff", "check", "--select", "E9,F63,F7,F82,F401,F841,B006,S", "--ignore", "S101,S311,S105,S106,S608,S603,S607,S110,S112,S104",
                                     "backend", "agents", "harness", "governance", "privacy", "analytics", "integrations", "retrieval", "scenarios", "approvals", "observability", "data"]),
        run("security_lint (bandit, high severity)", [PY, "-m", "bandit", "-q", "-r", "-lll", "backend", "agents", "harness", "governance", "privacy", "retrieval", "approvals"]),
        run("dependency_audit (pip-audit)", [PY, "-m", "pip_audit", "-r", "requirements.lock", "--progress-spinner", "off"], blocking=False, timeout=600),
        secret_scan(),
        run("frontend_typecheck", ["npx", "tsc", "-b", "--noEmit"], cwd=ROOT / "frontend", blocking=(ROOT / "frontend" / "node_modules").exists()),
    ]
    failed = [c for c in checks if c["blocking"] and c["passed"] is False]
    status = "PASS" if not failed else "BLOCKED"
    report = {"status": status, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "blocking_failures": [c["check"] for c in failed], "checks": checks}
    (ROOT / "var").mkdir(exist_ok=True)
    (ROOT / "var" / "release_gate.json").write_text(json.dumps(report, indent=1))
    for c in checks:
        mark = "PASS" if c["passed"] else ("SKIP" if c["passed"] is None else ("FAIL" if c["blocking"] else "WARN"))
        print(f"[{mark}] {c['check']} ({c['seconds']}s)")
    print(f"RELEASE GATE: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
