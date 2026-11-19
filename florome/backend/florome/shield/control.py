"""Shield security control plane: deterministic authorization that no model can rewrite.

``authorize`` evaluates two independent engines and requires both to allow:

1. the built-in table below (permission, emergency stop, scope, separation of duties, quotas);
2. Open Policy Agent with ``policy/shield.rego`` (``opa eval``, separate process).

Every decision is persisted as a ``SecurityPolicyDecision`` and written to the audit chain. Errors fail closed: an
OPA crash, timeout or unparsable answer is a denial.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from florome.config import PACKAGE_DIR, Settings
from florome.models import Tenant, utcnow
from florome.security import audit
from florome.security.rbac import Principal
from florome.shield.models import ScanRun, SecurityPolicyDecision, VerificationRun

REGO = PACKAGE_DIR / "shield" / "policy" / "shield.rego"
PERMISSION = {
    "repository.register": "shield:manage", "repository.ingest": "shield:research", "repository.scan": "shield:research",
    "hypothesis.verify": "shield:verify", "patch.generate": "shield:research", "patch.review": "shield:review",
    "containment.run": "shield:verify", "mcp.pin": "mcp:manage", "mcp.revoke": "mcp:manage", "evaluation.run": "shield:verify",
}
EXECUTING = {"hypothesis.verify", "containment.run", "evaluation.run", "patch.generate"}


class ShieldDenied(RuntimeError):
    def __init__(self, message: str, status: int = 403):
        super().__init__(message)
        self.status = status


def tool_path(settings: Settings, name: str) -> Path | None:
    p = Path(settings.shield_tools_dir) / name
    return p if p.is_file() and os.access(p, os.X_OK) else None


def in_authorized_scope(settings: Settings, path: str | Path) -> bool:
    """True only if ``path`` resolves (symlinks followed) inside an authorised root."""
    try:
        target = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    for root in settings.shield_authorized_roots:
        r = Path(root).resolve()
        if target == r or r in target.parents:
            return True
    return False


def _quota(db: Session, settings: Settings, tenant_id: str, action: str) -> str | None:
    since = utcnow() - timedelta(hours=1)
    if action == "repository.scan":
        n = db.scalar(select(func.count()).select_from(ScanRun).where(ScanRun.tenant_id == tenant_id, ScanRun.started_at >= since)) or 0
        if n >= settings.shield_scan_quota_per_hour:
            return f"Scan quota reached ({n}/{settings.shield_scan_quota_per_hour} per hour)"
    if action in ("hypothesis.verify", "evaluation.run"):
        n = db.scalar(select(func.count()).select_from(VerificationRun)
                      .where(VerificationRun.tenant_id == tenant_id, VerificationRun.created_at >= since)) or 0
        if n >= settings.shield_verify_quota_per_hour:
            return f"Verification quota reached ({n}/{settings.shield_verify_quota_per_hour} per hour)"
    return None


def _builtin(p: Principal, tenant: Tenant, action: str, resource: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    need = PERMISSION.get(action)
    if need is None:
        return False, [f"Unknown action '{action}' (deny by default)"]
    if not p.can(need):
        reasons.append(f"Missing permission {need}")
    if action in EXECUTING and tenant.emergency_stop:
        reasons.append("Emergency stop is active")
    if resource.get("requires_scope") and not resource.get("in_authorized_scope"):
        reasons.append("Target is outside the authorised scope")
    if action == "patch.review" and resource.get("requested_by") == p.user_id:
        reasons.append("Separation of duties: the requester cannot review their own patch")
    return not reasons, reasons


def _opa(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    if settings.shield_opa_mode == "off":
        return {"engine": "opa", "status": "disabled"}
    opa = tool_path(settings, "opa")
    if opa is None:
        if settings.shield_opa_mode == "required":
            return {"engine": "opa", "status": "error", "allow": False, "detail": "OPA binary not installed (required)"}
        return {"engine": "opa", "status": "not_installed"}
    try:
        proc = subprocess.run([str(opa), "eval", "--format", "json", "--stdin-input", "--data", str(REGO), "data.florome.shield.allow"],
                              input=json.dumps(payload), capture_output=True, text=True, timeout=15, env={"PATH": "/usr/bin:/bin"})
        value = json.loads(proc.stdout)["result"][0]["expressions"][0]["value"]
        if not isinstance(value, bool):
            raise ValueError("non-boolean decision")
        return {"engine": "opa", "status": "evaluated", "allow": value}
    except Exception as exc:  # noqa: BLE001 - any failure is a denial
        return {"engine": "opa", "status": "error", "allow": False, "detail": f"{type(exc).__name__}"}


def authorize(db: Session, settings: Settings, p: Principal, action: str, resource: dict[str, Any] | None = None) -> SecurityPolicyDecision:
    resource = resource or {}
    tenant = db.get(Tenant, p.tenant_id)
    ok, reasons = _builtin(p, tenant, action, resource)
    quota = _quota(db, settings, p.tenant_id, action) if ok else None
    if quota:
        ok, reasons = False, [quota]
    opa = _opa(settings, {"action": action, "principal": {"user_id": p.user_id, "permissions": sorted(p.permissions)},
                          "tenant": {"emergency_stop": tenant.emergency_stop}, "resource": resource})
    opa_allows = opa.get("allow", True) if opa["status"] in ("evaluated", "error") else True
    allowed = ok and opa_allows
    if ok and not opa_allows:
        reasons.append("OPA policy denied" if opa["status"] == "evaluated" else f"OPA error (fail closed): {opa.get('detail')}")
    decision = SecurityPolicyDecision(tenant_id=p.tenant_id, actor=p.user_id, action=action, resource=str(resource.get("id", ""))[:300],
                                      allowed=allowed, engines={"builtin": {"allow": ok, "reasons": reasons if not ok else []}, "opa": opa})
    db.add(decision)
    audit.record(db, p.tenant_id, p.user_id, f"shield.policy.{action}", str(resource.get("id", "")), "success" if allowed else "denied",
                 {"reasons": reasons, "opa": opa.get("status")})
    db.flush()
    if not allowed:
        db.commit()
        raise ShieldDenied("; ".join(reasons) or "Denied", 429 if quota else 403)
    return decision
