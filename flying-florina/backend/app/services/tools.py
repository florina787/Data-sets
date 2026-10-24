"""Concrete agent tools, registered against the pinned allowlist."""

from __future__ import annotations

from typing import Any

from app.core import db
from app.core.util import DEMO_TODAY, new_id, now_iso
from app.integrations.mcp.registry import (
    AircraftArgs,
    DocSearchArgs,
    DraftWorkOrderArgs,
    ExportArgs,
    HistoryArgs,
    PartArgs,
    Registry,
    RosterArgs,
    SlotArgs,
    ToolSpec,
)
from app.services import data

_registry: Registry | None = None


def _telemetry(aircraft_id: str, days: int) -> dict[str, Any]:
    return {"aircraft_id": aircraft_id, "series": data.telemetry_series(aircraft_id, days),
            "fleet_band": data.fleet_vibration_band(days)}


def _history(aircraft_id: str, limit: int) -> dict[str, Any]:
    return {"events": data.maintenance_history(aircraft_id, limit),
            "work_orders": data.work_orders(aircraft_id=aircraft_id, limit=limit)["items"]}


def _docs(query: str, limit: int, actor: Any) -> dict[str, Any]:
    # The gateway authorized the call; the search additionally filters each
    # document by the requesting human's label and role attributes.
    from app.retrieval.search import search

    return search(actor, query, limit)


def _parts(part_number: str) -> dict[str, Any]:
    return {"part": data.part(part_number), "availability": data.part_availability(part_number),
            "substitutes": data.substitution_check(part_number)}


def _roster(base: str, required: list[str], on_date: str) -> dict[str, Any]:
    return {"qualified": data.qualified_technicians(base, required, on_date),
            "expired": data.technicians_with_expired(base, required, on_date)}


def _slots(base: str) -> dict[str, Any]:
    return {"available": data.hangar_slots(base)}


def _draft_wo(aircraft_id: str, title: str, part_number: str | None, plan: dict[str, Any]) -> dict[str, Any]:
    # Dry run only: nothing is written to the work order table here.
    return {"draft_id": new_id("DRAFT"), "aircraft_id": aircraft_id, "title": title, "part_number": part_number,
            "plan": plan, "dry_run": True, "created": now_iso(), "note": "Draft only. Requires human approval before any write."}


def _export_email(destination: str, record_set: str) -> dict[str, Any]:  # pragma: no cover - must never run
    # Exists so the governance demo can prove a denied tool is never executed.
    # It does not send anything; if it were ever reached it records that fact.
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO meta(key, value) VALUES ('export_tool_executed', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (now_iso(),))
    return {"sent": False, "destination": destination, "record_set": record_set}


def _export_label(args: dict[str, Any]) -> str:
    rs = str(args.get("record_set", "")).lower()
    return "RESTRICTED" if ("restricted" in rs or "maintenance" in rs) else "UNKNOWN"


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec("telemetry.get_series", "1.0.0", "Daily synthetic telemetry for one aircraft plus fleet band.",
                 "read", "INTERNAL", AircraftArgs, _telemetry),
        ToolSpec("maintenance.get_history", "1.0.0", "Maintenance events and work orders for one aircraft.",
                 "read", "RESTRICTED", HistoryArgs, _history),
        ToolSpec("docs.search", "1.1.0", "Access-filtered document search with citations.",
                 "search", "PUBLIC", DocSearchArgs, _docs, needs_actor=True),
        ToolSpec("parts.check_availability", "1.0.0", "Reconciled inventory, substitutes and lead time for one part.",
                 "read", "INTERNAL", PartArgs, _parts),
        ToolSpec("roster.find_qualified", "1.0.0", "Technicians with unexpired qualifications at a base.",
                 "read", "INTERNAL", RosterArgs, _roster),
        ToolSpec("hangar.find_slots", "1.0.0", "Available hangar slots at a base.",
                 "read", "INTERNAL", SlotArgs, _slots),
        ToolSpec("workorder.create_draft", "1.0.0", "Create a dry-run work order draft (no write).",
                 "draft_write", "RESTRICTED", DraftWorkOrderArgs, _draft_wo),
        ToolSpec("records.export_email", "0.9.0", "Send a record set to an e-mail address (always external).",
                 "export", "RESTRICTED", ExportArgs, _export_email, destination="external_email",
                 idempotent=False, label_fn=_export_label),
    ]


def registry() -> Registry:
    global _registry
    if _registry is None:
        reg = Registry()
        for spec in tool_specs():
            reg.register(spec)
        _registry = reg
    return _registry


def demo_today() -> str:
    return DEMO_TODAY
