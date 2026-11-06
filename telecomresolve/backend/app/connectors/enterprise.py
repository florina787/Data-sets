"""Enterprise connector stubs (Phase 3).

These adapters exist so the integration surface is explicit and testable.
Each one fails clearly until credentials, contracts, data access and action
authorization are supplied. None of them is wired to a real system.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import ConnectorUnavailable

REASON = ("Not configured: requires credentials, a data-access agreement, an integration "
          "contract and action authorization. Disabled in this prototype.")


@dataclass(frozen=True)
class EnterpriseConnector:
    name: str
    system: str
    capabilities: tuple[str, ...]
    classification: str

    def call(self, *_args, **_kwargs):
        raise ConnectorUnavailable(f"{self.system}: {REASON}")

    def status(self) -> dict:
        return {"name": self.name, "system": self.system, "capabilities": list(self.capabilities),
                "classification": self.classification, "mode": "UNCONFIGURED",
                "available": False, "reason": REASON}


ENTERPRISE_CONNECTORS = [
    EnterpriseConnector("servicenow_incidents", "ITSM incident management (e.g. ServiceNow)",
                        ("incident_search", "incident_link"), "read/write"),
    EnterpriseConnector("crm_account", "CRM account and interaction history",
                        ("account_context", "support_history"), "read"),
    EnterpriseConnector("network_telemetry", "Network telemetry / line test platform",
                        ("diagnostics", "peer_health", "on_demand_line_test"), "read"),
    EnterpriseConnector("provisioning", "Service provisioning / equipment management",
                        ("reset_equipment", "modify_service"), "write"),
    EnterpriseConnector("field_dispatch", "Field-service dispatch and scheduling",
                        ("dispatch_preview", "dispatch_create"), "write"),
    EnterpriseConnector("customer_comms", "SMS / email customer communications",
                        ("send_customer_message",), "write"),
    EnterpriseConnector("billing", "Billing and credits", ("apply_bill_credit",), "write"),
]


def get_enterprise(name: str) -> EnterpriseConnector:
    for c in ENTERPRISE_CONNECTORS:
        if c.name == name:
            return c
    raise KeyError(name)
