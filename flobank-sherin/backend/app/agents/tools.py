"""Deterministic agent tools. These do real work on the inputs they are given (code, YAML, logs, database rows).

They do NOT connect to a live Azure DevOps organisation, Azure subscription or cluster. Connectors for those are
listed as pending in docs/STATUS.md; the diagnostics here run on uploaded artefacts and on the seeded records.
"""
from __future__ import annotations

import ast
import difflib
import random
import re
import textwrap
from decimal import Decimal

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as M


# ---------------------------------------------------------------------------------------------- Python
def python_ast_debug(code: str, filename: str = "module.py") -> dict:
    findings: list[dict] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"ok": False, "syntax_error": {"line": e.lineno, "col": e.offset, "message": e.msg, "text": (e.text or "").rstrip()},
                "findings": [{"line": e.lineno, "rule": "syntax", "severity": "error", "message": f"SyntaxError: {e.msg}"}], "diff": "", "fixed_code": None}
    lines = code.splitlines(keepends=True)
    fixed = list(lines)

    class V(ast.NodeVisitor):
        def visit_ExceptHandler(self, node):
            if node.type is None:
                findings.append({"line": node.lineno, "rule": "bare-except", "severity": "warning", "message": "Bare 'except:' swallows KeyboardInterrupt/SystemExit; catch Exception."})
                i = node.lineno - 1
                fixed[i] = re.sub(r"except\s*:", "except Exception:", fixed[i], count=1)
            self.generic_visit(node)

        def visit_Compare(self, node):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
                    findings.append({"line": node.lineno, "rule": "none-comparison", "severity": "warning", "message": "Compare to None with 'is' / 'is not'."})
                    i = node.lineno - 1
                    fixed[i] = fixed[i].replace("!= None", "is not None").replace("== None", "is None")
            self.generic_visit(node)

        def _func(self, node):
            for d in node.args.defaults + node.args.kw_defaults:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    findings.append({"line": node.lineno, "rule": "mutable-default", "severity": "error",
                                     "message": f"Mutable default argument in '{node.name}' is shared between calls."})
            self.generic_visit(node)

        visit_FunctionDef = _func
        visit_AsyncFunctionDef = _func

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                findings.append({"line": node.lineno, "rule": "dangerous-call", "severity": "error", "message": f"Use of {node.func.id}() on dynamic input."})
            self.generic_visit(node)

    V().visit(tree)
    # Undefined names (simple module-level analysis)
    import builtins
    defined = set(dir(builtins))
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            defined.add(n.id)
        elif isinstance(n, ast.arg):
            defined.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            defined.add(n.name)
        elif isinstance(n, (ast.comprehension,)):
            for t in ast.walk(n.target):
                if isinstance(t, ast.Name):
                    defined.add(t.id)
    seen = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in defined and n.id not in seen:
            seen.add(n.id)
            findings.append({"line": n.lineno, "rule": "undefined-name", "severity": "error", "message": f"Name '{n.id}' is not defined."})
    fixed_code = "".join(fixed)
    diff = "".join(difflib.unified_diff(lines, fixed, fromfile=f"a/{filename}", tofile=f"b/{filename}")) if fixed != lines else ""
    findings.sort(key=lambda f: f["line"] or 0)
    return {"ok": True, "findings": findings, "diff": diff, "fixed_code": fixed_code if diff else None,
            "functions": [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]}


def python_test_gen(code: str, module: str = "module") -> dict:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"ok": False, "error": f"Cannot generate tests: SyntaxError line {e.lineno}: {e.msg}", "tests": ""}
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    out = [f'"""Generated by Sherin QA Agent. Review the expected values before merging."""', "import pytest", "",
           f"from {module} import {', '.join(f.name for f in funcs) or '*'}", ""]
    for f in funcs:
        args = [a.arg for a in f.args.args if a.arg != "self"]
        sample = ", ".join("None" for _ in args)
        call = f"{f.name}({sample})"
        out += [f"def test_{f.name}_expected_behaviour():", "    # Scaffold: a reviewer must supply representative inputs and the expected value.",
                f"    pytest.skip('needs reviewer-provided expected value for {call}')", ""]
        if args:
            out += [f"@pytest.mark.parametrize('bad', [object()])", f"def test_{f.name}_rejects_invalid_input(bad):",
                    "    with pytest.raises(Exception):", f"        {f.name}({', '.join(['bad'] * len(args))})", ""]
    tests = "\n".join(out)
    ast.parse(tests)  # the generated file must at least be valid Python
    return {"ok": True, "functions": [f.name for f in funcs], "tests": tests, "count": tests.count("\ndef test_") + tests.startswith("def test_")}


# ---------------------------------------------------------------------------------------------- Pipelines / infra
def pipeline_yaml_lint(text: str, filename: str = "azure-pipelines.yml") -> dict:
    findings: list[dict] = []
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return {"ok": False, "findings": [{"line": (mark.line + 1) if mark else None, "rule": "yaml-syntax", "severity": "error", "message": str(e).splitlines()[0]}], "diff": ""}
    if not isinstance(doc, dict):
        return {"ok": False, "findings": [{"line": 1, "rule": "structure", "severity": "error", "message": "Pipeline root must be a mapping."}], "diff": ""}
    lines = text.splitlines(keepends=True)
    fixed = list(lines)
    if "trigger" not in doc and "pr" not in doc:
        findings.append({"line": 1, "rule": "no-trigger", "severity": "info", "message": "No trigger/pr defined; defaults to CI on all branches."})
    for i, ln in enumerate(lines):
        if re.search(r"vmImage:\s*['\"]?[\w-]*latest", ln):
            findings.append({"line": i + 1, "rule": "unpinned-image", "severity": "warning", "message": "Agent image uses 'latest'; pin a version for reproducible builds."})
            fixed[i] = re.sub(r"(vmImage:\s*['\"]?)ubuntu-latest", r"\1ubuntu-24.04", fixed[i])
        if re.search(r"continueOnError:\s*true", ln):
            findings.append({"line": i + 1, "rule": "continue-on-error", "severity": "warning", "message": "continueOnError hides failing steps."})
        if re.search(r"(?i)(password|secret|token|apikey)\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{8,}", ln) and "$(" not in ln:
            findings.append({"line": i + 1, "rule": "plaintext-secret", "severity": "error", "message": "Possible secret in plain text; use a variable group / Key Vault."})
        m = re.search(r"key:\s*['\"]?([^'\"\n]+)", ln)
        if m and "Cache" in "".join(lines[max(0, i - 3):i + 1]) and not re.search(r"(lock|requirements|\.txt|\.toml)", m.group(1)):
            findings.append({"line": i + 1, "rule": "cache-key", "severity": "error", "message": "Cache key does not include a lock/requirements file; stale or colliding caches."})
            indent = re.match(r"\s*", ln).group(0)
            fixed[i] = f'{indent}key: \'python | "$(Agent.OS)" | requirements.txt\'\n'
        if re.search(r"versionSpec:\s*['\"]?3\.(6|7|8)\b", ln):
            findings.append({"line": i + 1, "rule": "eol-python", "severity": "warning", "message": "End-of-life Python version."})
    jobs_text = text
    if "timeoutInMinutes" not in jobs_text:
        findings.append({"line": None, "rule": "no-timeout", "severity": "info", "message": "No job timeoutInMinutes; hung jobs consume agent minutes."})
    diff = "".join(difflib.unified_diff(lines, fixed, fromfile=f"a/{filename}", tofile=f"b/{filename}")) if fixed != lines else ""
    return {"ok": True, "findings": findings, "diff": diff, "stages": list((doc.get("stages") or [])) and [s.get("stage") for s in doc["stages"] if isinstance(s, dict)]}


INFRA_RULES = [
    (r"publicNetworkAccess\s*[:=]\s*['\"]?Enabled", "public-network", "error", "Public network access enabled on a data service."),
    (r"minimumTlsVersion\s*[:=]\s*['\"]?TLS1_[01]", "weak-tls", "error", "TLS below 1.2."),
    (r"allowBlobPublicAccess\s*[:=]\s*['\"]?true", "public-blob", "error", "Anonymous blob access allowed."),
    (r"0\.0\.0\.0/0|\*\s*sourceAddressPrefix", "open-nsg", "error", "NSG rule open to the internet."),
    (r"httpsOnly\s*[:=]\s*['\"]?false", "http-allowed", "warning", "HTTPS not enforced."),
]


def infra_config_review(text: str) -> dict:
    findings = []
    for i, ln in enumerate(text.splitlines()):
        for pat, rule, sev, msg in INFRA_RULES:
            if re.search(pat, ln, re.I):
                findings.append({"line": i + 1, "rule": rule, "severity": sev, "message": msg})
    if not re.search(r"tags\s*[:=]", text):
        findings.append({"line": None, "rule": "no-tags", "severity": "info", "message": "No resource tags (cost centre / owner) found; FinOps allocation will be incomplete."})
    return {"ok": True, "findings": findings}


SECRET_PATTERNS = [(r"AKIA[0-9A-Z]{16}", "AWS access key"), (r"(?i)AccountKey=[A-Za-z0-9+/=]{20,}", "Azure storage account key"),
                   (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private key"), (r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"$]{8,}['\"]", "Hard-coded credential"),
                   (r"ghp_[A-Za-z0-9]{36}", "GitHub token")]


def secrets_scan(text: str) -> dict:
    hits = []
    for i, ln in enumerate(text.splitlines()):
        for pat, label in SECRET_PATTERNS:
            if re.search(pat, ln):
                hits.append({"line": i + 1, "type": label, "severity": "error", "message": f"{label} detected (value redacted)."})
    return {"ok": True, "findings": hits}


# ---------------------------------------------------------------------------------------------- Azure diagnostics
DIAG_RULES = [
    ("adf", r"(?i)ErrorCode=UserErrorSchemaMapping|column .* not found|schema drift", "Source schema drift broke the copy activity mapping.",
     "Enable 'allow schema drift' on the data flow or update the explicit column mapping; add a schema contract test on the source."),
    ("adf", r"(?i)ErrorCode=SqlFailedToConnect|Login failed for user", "Linked service cannot authenticate to Azure SQL.",
     "Rotate the managed identity / Key Vault secret referenced by the linked service and verify firewall rules include the IR."),
    ("functions", r"(?i)Function host is not running|Host\.Startup|Microsoft\.Azure\.WebJobs\.Script", "Function host failed at startup.",
     "Check app settings for a missing FUNCTIONS_WORKER_RUNTIME / connection string; review the latest deployment package."),
    ("functions", r"(?i)Timeout value of .* exceeded|FunctionTimeoutException", "Function execution timed out.",
     "Move the long-running work to Durable Functions or a queue-triggered worker; raise functionTimeout only on Premium plans."),
    ("aks", r"(?i)CrashLoopBackOff|Back-off restarting failed container", "Pod is crash-looping.",
     "Inspect previous container logs (kubectl logs --previous); common causes are missing config/secrets or failed readiness dependencies."),
    ("aks", r"(?i)OOMKilled|exit code 137", "Container killed for exceeding its memory limit.",
     "Raise memory limits to the observed p95 working set plus headroom, or fix the leak; add a VPA recommendation."),
    ("aks", r"(?i)ImagePullBackOff|ErrImagePull", "Image cannot be pulled.", "Verify image tag exists in ACR and the AKS kubelet identity has AcrPull."),
    ("pipeline", r"(?i)##\[error\].*(ModuleNotFoundError|No module named)", "Build is missing a Python dependency.",
     "Pin the dependency in requirements.txt and include the lock file in the pipeline cache key."),
    ("pipeline", r"(?i)Cache.*(restored|hit).*\n?.*(error|fail)|cache key collision", "Stale pipeline cache restored incompatible packages.",
     "Include requirements/lock hash in the Cache@2 key."),
    ("appinsights", r"(?i)\b5\d\d\b.*(dependency|request)|exceptions \| where", "Server errors on a dependency or request path.",
     "Correlate operation_Id across requests/dependencies to find the failing downstream; check recent deployments."),
    ("monitor", r"(?i)Percentage CPU.*(9\d|100)|CPU throttl", "CPU saturation.", "Scale out or right-size; check for runaway loops after the last release."),
]


def azure_diagnose(text: str, service_hint: str | None = None) -> dict:
    diags = []
    for svc, pat, diagnosis, fix in DIAG_RULES:
        if service_hint and service_hint != svc:
            continue
        if re.search(pat, text or ""):
            diags.append({"service": svc, "diagnosis": diagnosis, "remediation": fix, "evidence": re.search(pat, text).group(0)[:160]})
    return {"ok": True, "diagnoses": diags, "matched": len(diags),
            "note": "Rule-based diagnosis on supplied logs. No live Azure connection is used." if diags else "No known failure signature matched the supplied logs."}


def incidents_summary(db: Session, service: str | None = None, limit: int = 8) -> dict:
    stmt = select(M.Incident).order_by(M.Incident.opened_at.desc())
    if service:
        stmt = stmt.where(M.Incident.service.ilike(f"%{service}%"))
    rows = db.scalars(stmt.limit(limit)).all()
    open_n = db.scalar(select(func.count()).select_from(M.Incident).where(M.Incident.status == "open"))
    return {"open": int(open_n or 0), "recent": [{"id": r.id, "service": r.service, "severity": r.severity, "title": r.title, "status": r.status,
                                                  "opened_at": r.opened_at.isoformat(timespec="minutes"), "data_class": r.data_class} for r in rows]}


# ---------------------------------------------------------------------------------------------- Portfolio / risk
def portfolio_reconcile(db: Session, portfolio_id: str, seed: int = 7) -> dict:
    """Compare book positions with a (synthetic) custodian statement and list breaks."""
    rng = random.Random(f"{portfolio_id}-{seed}")
    breaks = []
    positions = db.scalars(select(M.Position).where(M.Position.portfolio_id == portfolio_id)).all()
    for p in positions:
        book = Decimal(p.market_value_usd)
        cust = book
        if rng.random() < 0.18:
            cust = (book * Decimal(str(1 + rng.uniform(-0.004, 0.004)))).quantize(Decimal("0.01"))
        if cust != book:
            breaks.append({"issuer": p.issuer, "book_usd": float(book), "custodian_usd": float(cust), "difference_usd": float(cust - book),
                           "likely_cause": rng.choice(["Corporate action not booked", "Price source timing", "Unsettled trade", "FX rate cut-off"])})
    return {"portfolio_id": portfolio_id, "positions": len(positions), "breaks": breaks,
            "custodian_source": "Synthetic custodian statement (demo)", "matched": len(positions) - len(breaks)}


def portfolio_risk(db: Session, portfolio_id: str) -> dict:
    import math
    pos = db.scalars(select(M.Position).where(M.Position.portfolio_id == portfolio_id)).all()
    nav = sum(float(p.market_value_usd) for p in pos)
    vol = sum(float(p.market_value_usd) * float(p.volatility) for p in pos) / nav if nav else 0
    low_esg = [{"issuer": p.issuer, "esg": float(p.esg_score)} for p in pos if p.esg_score is not None and float(p.esg_score) < 55]
    return {"portfolio_id": portfolio_id, "nav_usd": round(nav, 2), "weighted_vol": round(vol, 4), "var_99_1d_usd": round(nav * vol / math.sqrt(252) * 2.326, 2),
            "low_esg_positions": low_esg, "method": "Undiversified weighted volatility (conservative upper bound); parametric 99% 1-day VaR."}


def compliance_summary(db: Session) -> dict:
    rows = db.execute(select(M.ComplianceEvent.type, M.ComplianceEvent.status, func.count()).group_by(M.ComplianceEvent.type, M.ComplianceEvent.status)).all()
    by = {}
    for t, s, n in rows:
        by.setdefault(t, {"open": 0, "closed": 0})[s] = int(n)
    return {"by_type": by, "open_total": sum(v["open"] for v in by.values())}


def pr_draft(title: str, diff: str, findings: list[dict]) -> dict:
    body = [f"## Summary", title, "", "## Findings addressed"] + [f"- L{f.get('line')}: {f['message']}" for f in findings[:12]] + \
           ["", "## Verification", "- Independent Verification Agent re-parsed the patched file.", "", "_Drafted by Sherin. Not opened until a human approves._"]
    return {"title": f"[Sherin] {title}"[:120], "body": "\n".join(body), "diff": diff}


def dedent(s: str) -> str:
    return textwrap.dedent(s).strip("\n") + "\n"
