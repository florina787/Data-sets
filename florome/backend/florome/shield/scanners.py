"""Adapters for external analysers. Each runs as a separate process with a timeout, and its output is normalised.

Normalised finding: tool, tool_version, rule_id, vuln_class, cwe, severity, file (repo-relative), line, message,
fingerprint. The fingerprint is sha256(repository, snapshot tree hash, file, line, vuln_class), so the same weakness
reported by two tools on the same line deduplicates, while the raw tool output is kept as separate evidence.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from florome.config import PACKAGE_DIR, Settings
from florome.security.audit import sha256
from florome.shield.control import tool_path

RULES = PACKAGE_DIR / "shield" / "rules" / "python-security.yml"
BANDIT_CLASS = {"B608": ("sql_injection", "CWE-89"), "B602": ("command_injection", "CWE-78"), "B605": ("command_injection", "CWE-78"),
                "B604": ("command_injection", "CWE-78"), "B603": ("command_injection", "CWE-78"), "B607": ("command_injection", "CWE-78"), "B301": ("unsafe_deserialization", "CWE-502"),
                "B403": ("unsafe_deserialization", "CWE-502"), "B307": ("code_injection", "CWE-94"), "B102": ("code_injection", "CWE-94"),
                "B506": ("unsafe_deserialization", "CWE-502"), "B105": ("hardcoded_secret", "CWE-798"), "B106": ("hardcoded_secret", "CWE-798")}
SEV = {"ERROR": "high", "WARNING": "medium", "INFO": "low", "HIGH": "high", "MEDIUM": "medium", "LOW": "low", "CRITICAL": "critical"}


@dataclass
class NormalizedFinding:
    tool: str
    tool_version: str
    rule_id: str
    vuln_class: str
    cwe: str | None
    severity: str
    file: str
    line: int
    message: str
    raw: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self, repo_id: str, tree_hash: str) -> str:
        return sha256({"repo": repo_id, "tree": tree_hash, "file": self.file, "line": self.line, "class": self.vuln_class})


@dataclass
class ToolRun:
    tool: str
    version: str
    status: str  # succeeded | failed | not_installed
    findings: list[NormalizedFinding]
    seconds: float
    error: str | None = None

    def summary(self) -> dict[str, Any]:
        return {"tool": self.tool, "version": self.version, "status": self.status, "findings": len(self.findings),
                "seconds": round(self.seconds, 2), "error": self.error}


def _run(cmd: list[str], timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "SEMGREP_SEND_METRICS": "off", "TRIVY_NO_PROGRESS": "true"})


def _rel(root: Path, path: str) -> str:
    p = Path(path)
    try:
        return str((p if p.is_absolute() else (Path.cwd() / p)).resolve().relative_to(root.resolve()))
    except ValueError:
        return path


def run_opengrep(settings: Settings, root: Path) -> ToolRun:
    t0 = time.perf_counter()
    exe = tool_path(settings, "opengrep")
    if exe is None:
        return ToolRun("opengrep", "-", "not_installed", [], 0.0, "binary not found; run scripts/fetch_shield_tools.sh")
    try:
        ver = _run([str(exe), "--version"], 30).stdout.strip()
        proc = _run([str(exe), "scan", "--config", str(RULES), "--json", "--quiet", str(root)], settings.shield_tool_timeout_seconds)
        data = json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        return ToolRun("opengrep", "-", "failed", [], time.perf_counter() - t0, type(exc).__name__)
    out = []
    for r in data.get("results", []):
        md = r.get("extra", {}).get("metadata", {})
        out.append(NormalizedFinding("opengrep", ver, r["check_id"].rsplit(".", 2)[-2] + "." + r["check_id"].rsplit(".", 1)[-1],
                                     md.get("vuln_class", "other"), md.get("cwe"), SEV.get(r["extra"].get("severity", ""), "medium"),
                                     _rel(root, r["path"]), r["start"]["line"], r["extra"].get("message", ""),
                                     {"check_id": r["check_id"], "lines": r["extra"].get("lines", "")[:300]}))
    return ToolRun("opengrep", ver, "succeeded", out, time.perf_counter() - t0)


def run_bandit(settings: Settings, root: Path) -> ToolRun:
    import shutil
    import sys

    t0 = time.perf_counter()
    exe = shutil.which("bandit", path=str(Path(sys.executable).parent))
    if exe is None:
        return ToolRun("bandit", "-", "not_installed", [], 0.0, "bandit not installed in this environment")
    try:
        ver = _run([exe, "--version"], 30).stdout.split()[1]
        proc = _run([exe, "-r", str(root), "-f", "json", "-q"], settings.shield_tool_timeout_seconds)
        data = json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        return ToolRun("bandit", "-", "failed", [], time.perf_counter() - t0, type(exc).__name__)
    out = []
    for r in data.get("results", []):
        cls, cwe = BANDIT_CLASS.get(r["test_id"], ("other", f"CWE-{r.get('issue_cwe', {}).get('id', '')}" if r.get("issue_cwe") else None))
        out.append(NormalizedFinding("bandit", ver, r["test_id"], cls, cwe, SEV.get(r["issue_severity"], "medium"),
                                     _rel(root, r["filename"]), r["line_number"], r["issue_text"],
                                     {"confidence": r["issue_confidence"], "code": r.get("code", "")[:300]}))
    return ToolRun("bandit", ver, "succeeded", out, time.perf_counter() - t0)


def run_trivy(settings: Settings, root: Path) -> ToolRun:
    t0 = time.perf_counter()
    exe = tool_path(settings, "trivy")
    if exe is None:
        return ToolRun("trivy", "-", "not_installed", [], 0.0, "binary not found; run scripts/fetch_shield_tools.sh")
    try:
        ver = _run([str(exe), "--version"], 30).stdout.split()[1]
        proc = _run([str(exe), "fs", "--scanners", "vuln,secret", "--format", "json", "--quiet", "--skip-dirs", "node_modules", str(root)],
                    settings.shield_tool_timeout_seconds)
        data = json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        return ToolRun("trivy", "-", "failed", [], time.perf_counter() - t0, type(exc).__name__)
    out = []
    for res in data.get("Results", []):
        for v in res.get("Vulnerabilities") or []:
            out.append(NormalizedFinding("trivy", ver, v["VulnerabilityID"], "vulnerable_dependency", None, SEV.get(v.get("Severity", ""), "medium"),
                                         _rel(root, res["Target"]), 0, f"{v['PkgName']} {v['InstalledVersion']}: {v.get('Title', '')}"[:300],
                                         {"package": v["PkgName"], "installed": v["InstalledVersion"], "fixed": v.get("FixedVersion")}))
        for s in res.get("Secrets") or []:
            out.append(NormalizedFinding("trivy", ver, s["RuleID"], "hardcoded_secret", "CWE-798", SEV.get(s.get("Severity", ""), "high"),
                                         _rel(root, res["Target"]), s.get("StartLine", 0), s.get("Title", ""), {"category": s.get("Category")}))
    return ToolRun("trivy", ver, "succeeded", out, time.perf_counter() - t0)


def run_all(settings: Settings, root: Path) -> list[ToolRun]:
    return [run_opengrep(settings, root), run_bandit(settings, root), run_trivy(settings, root)]
