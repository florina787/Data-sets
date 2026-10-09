"""SIMULATED connectors backed by the synthetic database.

Every query is scoped by tenant. Write adapters record simulated outcomes in
SimulatedExternalRecord; nothing leaves the process (no SMS, email or real
dispatch).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models.orm import (
    Account, Case, Customer, DiagnosticSample, Equipment, Incident, NetworkAsset, Service,
    ServiceAssetMapping, SimulatedExternalRecord, SupportInteraction,
)
from .base import ConnectorNotFound, ConnectorTimeout, OutcomeUnknown, ToolSpec

READ_ERRORS = ("CONNECTOR_TIMEOUT", "CONNECTOR_NOT_FOUND", "CONNECTOR_UNAVAILABLE")
WRITE_ERRORS = READ_ERRORS + ("OUTCOME_UNKNOWN",)
AUDIT = ("case_id", "tenant_id", "actor_id", "tool", "source_ids", "latency_ms")

TOOL_SPECS: dict[str, ToolSpec] = {
    "account_context": ToolSpec(
        "account_context", "Account, service, equipment and network mapping for the case",
        "read", "evidence:read", {"case_id": "string"}, 2.0, "none", READ_ERRORS, AUDIT),
    "support_history": ToolSpec(
        "support_history", "Earlier support interactions for the account", "read",
        "evidence:read", {"account_id": "string", "lookback_days": "int"}, 2.0, "none",
        READ_ERRORS, AUDIT),
    "incident_search": ToolSpec(
        "incident_search", "Incidents on the mapped path and, separately, nearby assets", "read",
        "evidence:read", {"asset_ids": "list[string]", "window_start": "datetime",
                          "window_end": "datetime"}, 2.0, "none", READ_ERRORS, AUDIT),
    "diagnostics": ToolSpec(
        "diagnostics", "Line telemetry samples for the service", "read", "evidence:read",
        {"service_id": "string", "since": "datetime"}, 3.0, "none", READ_ERRORS, AUDIT),
    "peer_health": ToolSpec(
        "peer_health", "Aggregate health of other services on the same access node", "read",
        "evidence:read", {"asset_id": "string", "since": "datetime"}, 3.0, "none",
        READ_ERRORS, AUDIT),
    "on_demand_line_test": ToolSpec(
        "on_demand_line_test", "Request a fresh line test sample", "read", "evidence:read",
        {"service_id": "string"}, 5.0, "none", READ_ERRORS, AUDIT),
    "knowledge_search": ToolSpec(
        "knowledge_search", "Scope-filtered troubleshooting and policy retrieval", "read",
        "knowledge:read", {"query": "string", "k": "int"}, 2.0, "none", READ_ERRORS, AUDIT),
    "dispatch_preview": ToolSpec(
        "dispatch_preview", "Preview a technician dispatch without creating it", "read",
        "recommendation:read", {"payload": "object"}, 2.0, "none", READ_ERRORS, AUDIT),
    "dispatch_create": ToolSpec(
        "dispatch_create", "Create a SIMULATED technician appointment", "write",
        "action:execute", {"payload": "object", "idempotency_key": "string"}, 5.0, "required",
        WRITE_ERRORS, AUDIT + ("approval_id", "payload_hash", "idempotency_key"),
        requires_approval=True),
    "incident_link": ToolSpec(
        "incident_link", "Persist case-to-incident association", "write", "action:execute",
        {"incident_id": "string", "idempotency_key": "string"}, 2.0, "required", WRITE_ERRORS,
        AUDIT + ("approval_id", "payload_hash", "idempotency_key"), requires_approval=True),
    "customer_message_preview": ToolSpec(
        "customer_message_preview", "Record a customer-facing draft or guide steps. Never sends.",
        "write", "action:execute", {"payload": "object", "idempotency_key": "string"}, 2.0,
        "required", WRITE_ERRORS, AUDIT + ("approval_id", "payload_hash", "idempotency_key"),
        requires_approval=True),
}


class AccountContextConnector:
    def get(self, db: Session, tenant_id: str, case: Case) -> dict:
        account = db.scalar(select(Account).where(Account.id == case.account_id,
                                                  Account.tenant_id == tenant_id))
        service = db.scalar(select(Service).where(Service.id == case.service_id,
                                                  Service.tenant_id == tenant_id))
        if account is None or service is None:
            raise ConnectorNotFound("account or service not found in scope")
        customer = db.get(Customer, account.customer_id)
        mapping = db.scalar(select(ServiceAssetMapping).where(
            ServiceAssetMapping.service_id == service.id, ServiceAssetMapping.tenant_id == tenant_id,
            ServiceAssetMapping.valid_to.is_(None)))
        equipment = db.scalar(select(Equipment).where(Equipment.service_id == service.id,
                                                      Equipment.tenant_id == tenant_id))
        path: list[NetworkAsset] = []
        if mapping is not None:
            asset = db.get(NetworkAsset, mapping.asset_id)
            while asset is not None and asset.tenant_id == tenant_id:
                path.append(asset)
                asset = db.get(NetworkAsset, asset.parent_id) if asset.parent_id else None
        return {"account": account, "service": service, "customer": customer,
                "mapping": mapping, "equipment": equipment, "path": path}


class SupportHistoryConnector:
    def list(self, db: Session, tenant_id: str, account_id: str, since: datetime) -> list[SupportInteraction]:
        return list(db.scalars(select(SupportInteraction).where(
            SupportInteraction.tenant_id == tenant_id, SupportInteraction.account_id == account_id,
            SupportInteraction.occurred_at >= since).order_by(SupportInteraction.occurred_at)))


class IncidentConnector:
    def on_path(self, db: Session, tenant_id: str, asset_ids: list[str]) -> list[Incident]:
        if not asset_ids:
            return []
        return list(db.scalars(select(Incident).where(Incident.tenant_id == tenant_id,
                                                      Incident.asset_id.in_(asset_ids))))

    def nearby_unmapped(self, db: Session, tenant_id: str, postal_area: str,
                        exclude_asset_ids: list[str]) -> list[Incident]:
        assets = list(db.scalars(select(NetworkAsset.id).where(
            NetworkAsset.tenant_id == tenant_id, NetworkAsset.postal_area == postal_area)))
        ids = [a for a in assets if a not in exclude_asset_ids]
        if not ids:
            return []
        return list(db.scalars(select(Incident).where(Incident.tenant_id == tenant_id,
                                                      Incident.asset_id.in_(ids),
                                                      Incident.status == "active")))


class DiagnosticsConnector:
    def samples(self, db: Session, tenant_id: str, service_id: str, since: datetime | None = None,
                *, include_post_action: bool = False) -> list[DiagnosticSample]:
        q = select(DiagnosticSample).where(DiagnosticSample.tenant_id == tenant_id,
                                           DiagnosticSample.service_id == service_id)
        if since is not None:
            q = q.where(DiagnosticSample.collected_at >= since)
        if not include_post_action:
            q = q.where(DiagnosticSample.simulated_post_action.is_(False))
        return list(db.scalars(q.order_by(DiagnosticSample.collected_at)))

    def latest(self, db: Session, tenant_id: str, service_id: str) -> DiagnosticSample | None:
        return db.scalar(select(DiagnosticSample).where(
            DiagnosticSample.tenant_id == tenant_id, DiagnosticSample.service_id == service_id,
            DiagnosticSample.simulated_post_action.is_(False))
            .order_by(DiagnosticSample.collected_at.desc()).limit(1))

    def peer_health(self, db: Session, tenant_id: str, asset_id: str, exclude_service: str,
                    since: datetime) -> dict:
        peer_services = list(db.scalars(select(ServiceAssetMapping.service_id).where(
            ServiceAssetMapping.tenant_id == tenant_id, ServiceAssetMapping.asset_id == asset_id,
            ServiceAssetMapping.service_id != exclude_service)))
        with_data, with_los = [], []
        for sid in peer_services:
            rows = self.samples(db, tenant_id, sid, since)
            if not rows:
                continue
            with_data.append(sid)
            if any(r.loss_of_signal_events > 0 for r in rows):
                with_los.append(sid)
        return {"asset_id": asset_id, "since": since.isoformat(), "peers_total": len(peer_services),
                "peers_with_fresh_data": len(with_data), "peers_with_loss_of_signal": len(with_los)}

    def on_demand_test(self, db: Session, tenant_id: str, case: Case) -> DiagnosticSample | None:
        """Synthetic on-demand line test. Returns None when the simulated
        test system reports the line test as unavailable."""
        profile = case.simulation_profile or {}
        if profile.get("on_demand_test") == "unavailable":
            return None
        if profile.get("on_demand_test") == "timeout":
            raise ConnectorTimeout("on-demand line test timed out")
        latest = self.latest(db, tenant_id, case.service_id)
        if latest is None:
            return None
        return latest  # fresh telemetry already covers the window; no new sample needed

    POST_ACTION_PROFILES = {
        "healthy": (6, dict(link_state="up", loss_of_signal_events=0, link_retrains=0,
                            packet_loss_pct=0.2, latency_ms=14, snr_margin_db=10.1, crc_errors=8,
                            cpe_unexpected_reboots=0)),
        "incident_ongoing": (6, dict(link_state="up", loss_of_signal_events=2, link_retrains=3,
                                     packet_loss_pct=4.2, latency_ms=37, snr_margin_db=9.7,
                                     crc_errors=44, cpe_unexpected_reboots=0)),
        "still_failing": (6, dict(link_state="up", loss_of_signal_events=0, link_retrains=3,
                                  packet_loss_pct=2.4, latency_ms=28, snr_margin_db=3.9,
                                  crc_errors=1100, cpe_unexpected_reboots=0)),
        "telemetry_gap": (1, dict(link_state="up", loss_of_signal_events=0, link_retrains=0,
                                  packet_loss_pct=0.3, latency_ms=15, snr_margin_db=10.0,
                                  crc_errors=9, cpe_unexpected_reboots=0)),
    }

    def simulate_post_action(self, db: Session, case: Case, execution_id: str,
                             start: datetime, window_minutes: int) -> list[DiagnosticSample]:
        """SIMULATION: fast-forwards telemetry after an action using the case's
        hidden post-action profile. Samples are flagged simulated_post_action."""
        existing = list(db.scalars(select(DiagnosticSample).where(
            DiagnosticSample.service_id == case.service_id,
            DiagnosticSample.simulated_post_action.is_(True),
            DiagnosticSample.source == f"sim:{execution_id}")))
        if existing:
            return existing
        name = (case.simulation_profile or {}).get("post_action", "telemetry_gap")
        count, values = self.POST_ACTION_PROFILES[name]
        step = max(window_minutes // 6, 1)
        rows = []
        for i in range(count):
            row = DiagnosticSample(
                id=f"DS-POST-{execution_id[-8:]}-{i:02d}", tenant_id=case.tenant_id,
                service_id=case.service_id, collected_at=start + timedelta(minutes=step * (i + 1)),
                source=f"sim:{execution_id}", interval_minutes=step, cpe_uptime_s=3600,
                simulated_post_action=True, **values)
            db.add(row)
            rows.append(row)
        db.flush()
        return rows


class SimulatedWriteConnector:
    """Simulated external system with idempotency keys and fault injection.

    Faults (case.simulation_profile["write_fault"]):
      - "timeout_after_create": record is created but the response is lost.
      - "timeout_before_create": nothing is created and the call times out.
    """

    def __init__(self, system: str):
        self.system = system

    def find(self, db: Session, idempotency_key: str) -> SimulatedExternalRecord | None:
        return db.scalar(select(SimulatedExternalRecord).where(
            SimulatedExternalRecord.system == self.system,
            SimulatedExternalRecord.idempotency_key == idempotency_key))

    def create(self, db: Session, case: Case, payload: dict, idempotency_key: str,
               fault_consumed: bool = False) -> SimulatedExternalRecord:
        existing = self.find(db, idempotency_key)
        if existing is not None:
            return existing  # idempotent replay
        fault = None if fault_consumed else (case.simulation_profile or {}).get("write_fault")
        if fault == "timeout_before_create":
            raise OutcomeUnknown("simulated timeout; record may not exist")
        rec = SimulatedExternalRecord(
            id=f"SIM-{self.system.upper()[:4]}-{uuid.uuid4().hex[:8]}", system=self.system,
            tenant_id=case.tenant_id, case_id=case.id, idempotency_key=idempotency_key,
            payload=payload, status="created", created_at=utcnow())
        try:
            with db.begin_nested():
                db.add(rec)
        except IntegrityError:
            found = self.find(db, idempotency_key)
            if found is None:
                raise
            return found
        if fault == "timeout_after_create":
            raise OutcomeUnknown("simulated lost response after create")
        return rec


account_context = AccountContextConnector()
support_history = SupportHistoryConnector()
incidents = IncidentConnector()
diagnostics = DiagnosticsConnector()
dispatch_system = SimulatedWriteConnector("dispatch")
message_preview = SimulatedWriteConnector("message_preview")
incident_link_system = SimulatedWriteConnector("incident_link")
