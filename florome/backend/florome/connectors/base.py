"""Connector contract.

Every platform integration (sandbox, REST, SDK, MCP-backed) implements :class:`Connector`. A connector
*declares* the capabilities it really supports; calling an undeclared capability raises
:class:`UnsupportedCapability` instead of returning empty data, so callers can tell "nothing happened"
from "this integration cannot do that".

Actions are never free-form: a connector publishes a typed catalog of :class:`ActionSpec`, parameters
are validated against each spec's JSON schema, and only catalog actions can be executed.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import jsonschema


class Capability(StrEnum):
    DISCOVER_RESOURCES = "discover_resources"
    READ_STATUS = "read_status"
    FETCH_LOGS = "fetch_logs"
    FETCH_METRICS = "fetch_metrics"
    FETCH_TRACES = "fetch_traces"
    FETCH_DEPLOYMENTS = "fetch_deployments"
    FETCH_CHANGES = "fetch_changes"
    FETCH_INCIDENTS = "fetch_incidents"
    LIST_ACTIONS = "list_actions"
    EXECUTE_ACTIONS = "execute_actions"
    VERIFY = "verify"


class ConnectorError(RuntimeError):
    """A failure talking to the target system. ``retryable`` marks transient errors (timeouts, 429, 5xx)."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class UnsupportedCapability(ConnectorError):
    pass


class ActionValidationError(ConnectorError):
    pass


@dataclass
class ResourceRecord:
    source_ref: str
    kind: str
    name: str
    platform: str
    environment: str = "prod"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Observation:
    """One raw fact returned by a connector, before it is stored as Evidence."""

    kind: str  # log | metric | deployment | config_change | trace | status
    resource_ref: str
    observed_at: datetime
    summary: str
    payload: dict[str, Any]
    source_ref: str


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    title: str
    description: str
    applies_to_kinds: tuple[str, ...]
    params_schema: dict[str, Any]
    risk: str  # low | medium | high
    reversible: bool
    rollback: str  # documented rollback / recovery strategy
    required_permission: str  # provider-side permission the connector identity needs
    expected_outcome: str
    tested: bool = False  # exercised by an automated test against a safe target; prerequisite for autonomy

    def public(self) -> dict[str, Any]:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


@dataclass
class ActionResult:
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    idempotent_replay: bool = False


@dataclass
class HealthResult:
    ok: bool
    message: str
    checked_operations: list[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    healthy: bool
    checks: list[dict[str, Any]]


class Connector(ABC):
    connector_type: str = "abstract"
    platform: str = "unknown"
    is_simulated: bool = False

    def capabilities(self) -> set[Capability]:
        return set()

    def _require(self, cap: Capability) -> None:
        if cap not in self.capabilities():
            raise UnsupportedCapability(f"{self.connector_type} does not support {cap.value}")

    async def health(self) -> HealthResult:
        raise NotImplementedError

    async def discover_resources(self) -> list[ResourceRecord]:
        self._require(Capability.DISCOVER_RESOURCES)
        raise NotImplementedError

    async def read_status(self, resource_ref: str) -> dict[str, Any]:
        self._require(Capability.READ_STATUS)
        raise NotImplementedError

    async def fetch_observations(self, resource_ref: str, start: datetime, end: datetime, kinds: set[str]) -> list[Observation]:
        """Logs / metrics / deployments / config changes / traces for one resource, limited to declared capabilities."""
        raise NotImplementedError

    def list_actions(self) -> list[ActionSpec]:
        self._require(Capability.LIST_ACTIONS)
        return []

    def get_action(self, action_id: str) -> ActionSpec:
        for spec in self.list_actions():
            if spec.action_id == action_id:
                return spec
        raise ActionValidationError(f"Action '{action_id}' is not in {self.connector_type}'s catalog")

    def validate_action(self, action_id: str, resource_kind: str, params: dict[str, Any]) -> ActionSpec:
        spec = self.get_action(action_id)
        if resource_kind not in spec.applies_to_kinds:
            raise ActionValidationError(f"Action '{action_id}' does not apply to resource kind '{resource_kind}'")
        try:
            jsonschema.validate(params, spec.params_schema)
        except jsonschema.ValidationError as exc:
            raise ActionValidationError(f"Invalid parameters for '{action_id}': {exc.message}") from exc
        return spec

    async def execute_action(self, action_id: str, resource_ref: str, params: dict[str, Any], idempotency_key: str) -> ActionResult:
        self._require(Capability.EXECUTE_ACTIONS)
        raise NotImplementedError

    async def verify(self, resource_ref: str) -> VerificationResult:
        self._require(Capability.VERIFY)
        raise NotImplementedError
