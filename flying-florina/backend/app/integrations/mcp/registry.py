"""Tool registry, allowlist pinning and the policy gateway.

Trust chain for every agent tool call:

    intent router -> workflow step (agent) -> ToolGateway.invoke
        -> policy.evaluate (deny-by-default, before execution)
        -> argument schema validation, rate limit, circuit breaker, timeout
        -> typed tool function (read model over the synthetic DB)
        -> redacted tool_invocations record + audit event

Tools are registered only if their name, version and input-schema SHA-256
match fixtures/policies/tool_allowlist.yaml. MCP exposes a subset of these
same tools; MCP is an agent interface, not the security boundary.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.core import audit, db
from app.core.config import FIXTURES_DIR
from app.core.policy import Decision, PolicyRequest, evaluate
from app.core.security import Actor
from app.core.util import new_id, now_iso, redact_obj, sha256_json

ALLOWLIST_PATH = FIXTURES_DIR / "policies" / "tool_allowlist.yaml"


class UntrustedToolError(Exception):
    pass


class ToolDenied(Exception):
    def __init__(self, decision: Decision):
        super().__init__(decision.reason)
        self.decision = decision


class ToolFailed(Exception):
    pass


@dataclass
class ToolSpec:
    name: str
    version: str
    description: str
    action: str  # read | search | draft_write | write | export
    label: str  # data label of what the tool returns or touches
    input_model: type[BaseModel]
    fn: Callable[..., Any]
    destination: str = "none"
    idempotent: bool = True
    timeout_s: float = 10.0
    label_fn: Callable[[dict[str, Any]], str] | None = None
    needs_actor: bool = False  # tool filters its own output by the requesting human's attributes

    @property
    def schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    @property
    def schema_sha256(self) -> str:
        return sha256_json(self.schema)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "description": self.description, "action": self.action,
                "label": self.label, "destination": self.destination, "idempotent": self.idempotent,
                "input_schema": self.schema, "schema_sha256": self.schema_sha256}


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float = 0.0


@dataclass
class Registry:
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    _breakers: dict[str, _Breaker] = field(default_factory=dict)
    _rate: dict[str, list[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    rate_limit_per_minute: int = 240
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 30.0

    @staticmethod
    def allowlist() -> dict[str, dict[str, str]]:
        with open(ALLOWLIST_PATH, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return {t["name"]: t for t in data.get("tools", [])}

    def register(self, spec: ToolSpec) -> None:
        pins = self.allowlist()
        pin = pins.get(spec.name)
        reason = None
        if pin is None:
            reason = "not on allowlist"
        elif pin["version"] != spec.version:
            reason = f"version {spec.version} != pinned {pin['version']}"
        elif pin["schema_sha256"] != spec.schema_sha256:
            reason = "input schema hash differs from pinned value"
        if reason:
            self.rejected.append({"name": spec.name, "version": spec.version, "reason": reason, "ts": now_iso()})
            raise UntrustedToolError(f"Tool '{spec.name}' rejected: {reason}")
        self.tools[spec.name] = spec

    def _check_rate(self, actor_id: str) -> bool:
        now = time.time()
        with self._lock:
            window = [t for t in self._rate.get(actor_id, []) if now - t < 60]
            if len(window) >= self.rate_limit_per_minute:
                self._rate[actor_id] = window
                return False
            window.append(now)
            self._rate[actor_id] = window
            return True

    @staticmethod
    def _destination(spec: ToolSpec | None, args: dict[str, Any]) -> str:
        if spec is None:
            return "none"
        requested = str(args.get("destination", ""))
        if spec.action == "export" and requested in {"personal_email", "external_email", "external_url", "removable_media"}:
            return requested
        return spec.destination

    def invoke(self, agent: Actor, human: Actor, tool: str, args: dict[str, Any], run_id: str | None = None,
               instruction_source: str = "user", idempotency_key: str | None = None,
               fault: str | None = None) -> tuple[Any, Decision]:
        spec = self.tools.get(tool)
        label = spec.label if spec else "UNKNOWN"
        if spec and spec.label_fn:
            label = spec.label_fn(args)
        req = PolicyRequest(
            action=spec.action if spec else "tool_call", resource=f"tool:{tool}", label=label,
            destination=self._destination(spec, args), tool=tool, run_id=run_id,
            instruction_source=instruction_source, tool_registered=spec is not None,
            tool_pinned=spec is not None and self.allowlist().get(tool, {}).get("schema_sha256") == spec.schema_sha256,
            idempotency_key=idempotency_key,
        )
        decision = evaluate(agent, req, on_behalf_of=human)
        if not decision.allowed:
            raise ToolDenied(decision)
        assert spec is not None
        try:
            parsed = spec.input_model.model_validate(args)
        except ValidationError as err:
            self._log(human, spec, args, "invalid_args", 0.0, run_id, decision.id, idempotency_key)
            raise ToolFailed(f"Invalid arguments for {tool}: {err.errors(include_url=False)}") from err
        if not self._check_rate(human.id):
            self._log(human, spec, args, "rate_limited", 0.0, run_id, decision.id, idempotency_key)
            raise ToolFailed(f"Rate limit exceeded for {human.id}")
        br = self._breakers.setdefault(tool, _Breaker())
        if br.failures >= self.breaker_threshold and time.time() - br.opened_at < self.breaker_cooldown_s:
            self._log(human, spec, args, "circuit_open", 0.0, run_id, decision.id, idempotency_key)
            raise ToolFailed(f"Circuit breaker open for {tool}")
        started = time.perf_counter()
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            if fault == "timeout":
                future = pool.submit(lambda: time.sleep(spec.timeout_s + 1))
                future.result(timeout=min(spec.timeout_s, 0.5))
            kwargs = parsed.model_dump()
            if spec.needs_actor:
                kwargs["actor"] = human
            future = pool.submit(spec.fn, **kwargs)
            result = future.result(timeout=spec.timeout_s)
        except concurrent.futures.TimeoutError as err:
            br.failures += 1
            br.opened_at = time.time()
            self._log(human, spec, args, "timeout", (time.perf_counter() - started) * 1000, run_id, decision.id, idempotency_key)
            raise ToolFailed(f"Tool {tool} timed out") from err
        except Exception as err:  # noqa: BLE001 - surfaced as a typed failure
            br.failures += 1
            br.opened_at = time.time()
            self._log(human, spec, args, "error", (time.perf_counter() - started) * 1000, run_id, decision.id, idempotency_key)
            raise ToolFailed(f"Tool {tool} failed: {err}") from err
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        br.failures = 0
        self._log(human, spec, args, "ok", (time.perf_counter() - started) * 1000, run_id, decision.id, idempotency_key)
        return result, decision

    def _log(self, human: Actor, spec: ToolSpec, args: dict[str, Any], status: str, ms: float, run_id: str | None,
             decision_id: str, idem: str | None) -> None:
        with db.session(write=True) as conn:
            conn.execute(
                "INSERT INTO tool_invocations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (new_id("TOOL"), now_iso(), human.id, spec.name, spec.version, db.jdump(redact_obj(args)), status,
                 round(ms, 2), run_id, decision_id, idem),
            )
            audit.append(human.id, "tool.invocation", f"{spec.name}@{spec.version} -> {status}",
                         {"tool": spec.name, "status": status, "run_id": run_id, "decision_id": decision_id}, conn)


def invocation_count(tool: str) -> int:
    r = db.query_one("SELECT COUNT(*) n FROM tool_invocations WHERE tool = ?", (tool,))
    return r["n"] if r else 0


# ---------------------------------------------------------------- tool input models

class AircraftArgs(BaseModel):
    aircraft_id: str = Field(pattern=r"^AC-\d{3}$")
    days: int = Field(default=60, ge=7, le=548)


class HistoryArgs(BaseModel):
    aircraft_id: str = Field(pattern=r"^AC-\d{3}$")
    limit: int = Field(default=20, ge=1, le=200)


class DocSearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=6, ge=1, le=20)


class PartArgs(BaseModel):
    part_number: str = Field(pattern=r"^P-[0-9A-Z]{3,8}$")


class RosterArgs(BaseModel):
    base: str = Field(pattern=r"^[A-Z\-]{3,20}$")
    required: list[str] = Field(min_length=1, max_length=6)
    on_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class SlotArgs(BaseModel):
    base: str = Field(pattern=r"^[A-Z\-]{3,20}$")


class DraftWorkOrderArgs(BaseModel):
    aircraft_id: str = Field(pattern=r"^AC-\d{3}$")
    title: str = Field(max_length=300)
    part_number: str | None = Field(default=None, pattern=r"^P-[0-9A-Z]{3,8}$")
    plan: dict[str, Any] = Field(default_factory=dict)


class ExportArgs(BaseModel):
    destination: str = Field(max_length=200)
    record_set: str = Field(max_length=100)
