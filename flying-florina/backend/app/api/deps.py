"""Response envelope, typed errors and shared dependencies."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.core import policy
from app.core.config import get_settings
from app.core.security import Actor
from app.core.util import now_iso


def envelope(request: Request, data: Any, warnings: list[str] | None = None, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    s = get_settings()
    return {
        "request_id": getattr(request.state, "request_id", None),
        "data": data,
        "warnings": warnings or [],
        "provenance": provenance or {"source": "synthetic demo database", "synthetic": True},
        "demo": {"demo_mode": s.demo_mode, "offline_mode": s.offline_mode, "synthetic_data": True, "live_ifs_connection": False},
        "timestamp": now_iso(),
    }


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(status_code=status, detail={"code": code, "message": message, "details": details})


def require(actor: Actor, action: str, resource: str, label: str = "INTERNAL", **kw: Any) -> policy.Decision:
    """Evaluate policy for an endpoint; raise a typed 403 on deny."""
    d = policy.evaluate(actor, policy.PolicyRequest(action=action, resource=resource, label=label, **kw))
    if not d.allowed:
        raise ApiError(403, "policy_denied", d.reason, d.as_dict())
    return d


def labels_for(actor: Actor) -> list[str]:
    return [lbl for lbl in policy.LABELS if policy.label_allows(actor, lbl)[0]]
