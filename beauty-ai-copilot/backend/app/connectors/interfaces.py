"""Connector interfaces for real integrations. All are explicitly UNCONFIGURED in this prototype:
calling one raises IntegrationUnavailable rather than returning fabricated data. Local simulated
components (fixture model registry, simulated deployment executor) are separate and labelled."""
from __future__ import annotations

from dataclasses import dataclass

from app.errors import IntegrationUnavailable


@dataclass(frozen=True)
class ConnectorStatus:
    name: str
    purpose: str
    status: str = "unconfigured"
    prototype_substitute: str | None = None


CONNECTORS = [
    ConnectorStatus("git", "Read revisions and diffs from the source repository", prototype_substitute="fixture diffs in data/synthetic/revisions (read-only)"),
    ConnectorStatus("ci", "Trigger and read CI pipelines for candidate builds"),
    ConnectorStatus("experiment_tracking", "Read training/evaluation experiment metadata"),
    ConnectorStatus("model_registry", "Resolve model versions and artifact digests", prototype_substitute="fixture registry (ModelVersion table seeded from data/synthetic/models.json)"),
    ConnectorStatus("catalogue", "Resolve product/shade catalogue versions", prototype_substitute="fictional catalogue CAT-2026.1 fixture"),
    ConnectorStatus("dataset_storage", "Private object storage for consented images", prototype_substitute="no images; synthetic:// references only"),
    ConnectorStatus("identity", "SSO / OIDC identity and group-to-role mapping", prototype_substitute="demo persona header (disabled in production mode)"),
    ConnectorStatus("deployment", "Progressive delivery to real serving infrastructure", prototype_substitute="simulated release executor (no external writes)"),
    ConnectorStatus("incident_management", "Open and update incidents for alerts"),
]


class UnconfiguredConnector:
    def __init__(self, name: str):
        self.name = name

    def __getattr__(self, item):
        def _fail(*_, **__):
            raise IntegrationUnavailable(f"{self.name}_unconfigured",
                                         f"The {self.name} connector is not configured. Supply real access and authorization first.")
        return _fail


def get_connector(name: str) -> UnconfiguredConnector:
    if name not in {c.name for c in CONNECTORS}:
        raise KeyError(name)
    return UnconfiguredConnector(name)


def status() -> list[dict]:
    return [c.__dict__ for c in CONNECTORS]
