"""Release / build registry for the demonstration environments.

The platform keeps a small registry of *application builds*. Each build pins the
availability status-mapping variant used by the Verification Agent. Switching the
active build in the ``demo`` environments is how the AI-SDLC demonstration
"deploys" - it is a SIMULATED deployment inside this process, clearly labelled.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from pydantic import BaseModel


class Build(BaseModel):
    version: str
    status_mapping: str
    description: str
    defect_injected: bool = False


BUILDS: dict[str, Build] = {
    "1.4.0": Build(version="1.4.0", status_mapping="correct", description="Baseline build."),
    "1.5.0": Build(version="1.5.0", status_mapping="defect_unverified_as_confirmed", defect_injected=True,
                   description="Ranking enhancements. CONTAINS CONTROLLED DEMONSTRATION DEFECT: advertised "
                               "(unverified) slots mapped to VERIFIED_AVAILABLE."),
    "1.5.1": Build(version="1.5.1", status_mapping="correct",
                   description="Hotfix: restores ADVERTISED -> ADVERTISED_UNVERIFIED mapping; adds regression tests."),
}

ENVIRONMENTS = ("demo-staging", "demo-production")
_lock = threading.Lock()
_active: dict[str, str] = {"demo-staging": "1.4.0", "demo-production": "1.4.0"}
_history: list[dict] = []
PATIENT_ENV = "demo-production"  # environment serving the patient workflow


def active_build(env: str = PATIENT_ENV) -> Build:
    return BUILDS[_active[env]]


def deploy(version: str, env: str, actor: str, approval_id: str | None) -> dict:
    if version not in BUILDS:
        raise ValueError(f"unknown build {version}")
    if env not in ENVIRONMENTS:
        raise ValueError(f"unknown environment {env}")
    if env == "demo-production" and not approval_id:
        raise PermissionError("Production deployment requires an approved release approval request.")
    with _lock:
        prev = _active[env]
        _active[env] = version
        entry = {"env": env, "from": prev, "to": version, "actor": actor, "approval_id": approval_id,
                 "at": datetime.now(UTC).isoformat(), "simulated": True}
        _history.append(entry)
    return entry


def history() -> list[dict]:
    return list(_history)


def state() -> dict:
    return {"active": dict(_active), "builds": {k: v.model_dump() for k, v in BUILDS.items()},
            "history": history(), "note": "Simulated in-process deployments for the demonstration environments."}


def reset() -> None:
    with _lock:
        for e in ENVIRONMENTS:
            _active[e] = "1.4.0"
        _history.clear()
