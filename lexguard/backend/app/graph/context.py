"""Per-request runtime context (non-serialisable services passed to graph nodes via config)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.access.matter_access import AccessScope
from app.audit import service as audit
from app.config import Settings
from app.services.data_store import DataStore


class RequestTimeout(TimeoutError):
    pass


class IterationLimitExceeded(RuntimeError):
    pass


@dataclass
class RunContext:
    store: DataStore
    settings: Settings
    request_id: str
    user_id: str
    matter_id: str | None
    message: str
    selected_finding_id: str | None = None
    destination_override: str | None = None
    cfg: dict = field(default_factory=dict)        # evaluation overrides (top_k, strict_numbers, ...)
    scope: AccessScope | None = None
    mg: object | None = None
    tools: object | None = None
    providers: object | None = None
    client_id: str | None = None
    started: float = field(default_factory=time.perf_counter)
    audit_ids: list[str] = field(default_factory=list)
    persist: bool = True

    @property
    def max_steps(self) -> int:
        return int(self.cfg.get("max_agent_steps", self.settings.max_agent_steps))

    def check_deadline(self) -> None:
        timeout = float(self.cfg.get("timeout_s", self.settings.request_timeout_s))
        if time.perf_counter() - self.started > timeout:
            raise RequestTimeout(f"Request exceeded {timeout}s time budget.")

    def audit(self, event_type: str, payload: dict | None = None, severity: str = "INFO") -> str | None:
        if not self.persist:
            return None
        eid = audit.record(event_type, request_id=self.request_id, user_id=self.user_id, client_id=self.client_id,
                           matter_id=self.matter_id, payload=payload or {}, severity=severity)
        self.audit_ids.append(eid)
        return eid
