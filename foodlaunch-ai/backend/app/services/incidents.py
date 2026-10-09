"""Incident detection and analysis over recorded telemetry and release changes.

The analysis is a deterministic rule set. In the demo the fault is injected
deliberately; the analysis output says so and never claims general autonomous
root-cause discovery.
"""

from __future__ import annotations

import json
import re

from app.db import new_id, now_iso, row, rows, session
from app.errors import Conflict, NotFound
from app.records import audit, evidence
from app.services import delivery
from app.tools import inventory_sim, telemetry, workspace
from app.tools.retrieval import get_index

DISCLAIMER = (
    "Scripted fault demonstration. The inventory timeout was injected with the demo fault control. "
    "This analysis applies fixed rules to recorded telemetry and the release diff. It shows evidence "
    "linking and hypothesis tracking. It is not proof of general autonomous root-cause discovery."
)
ERROR_RATE_THRESHOLD = 0.2
LATENCY_THRESHOLD_MS = 3000


def get_incident(incident_id: str) -> dict:
    found = row("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    if found is None:
        raise NotFound("Incident not found", incident_id=incident_id)
    found["analysis"] = json.loads(found.pop("analysis_json") or "{}")
    return found


def open_incidents() -> list[dict]:
    return rows("SELECT id, title, status, release_id, opened_at FROM incidents WHERE status != 'resolved'")


def analyse(actor: str) -> dict:
    """Detect and analyse an incident on the currently deployed release."""
    release = delivery.current_release()
    if release is None:
        raise Conflict("No release is deployed")
    since = release["deployed_at"] or release["created_at"]
    stats = telemetry.summary(since=since, revision=release["revision"])
    checkout = stats["checkout_requests"]
    breached = checkout > 0 and (
        (stats["checkout_error_rate"] or 0) >= ERROR_RATE_THRESHOLD
        or (stats["checkout_p95_ms"] or 0) >= LATENCY_THRESHOLD_MS
    )
    if not breached:
        return {"incident": None, "stats": stats,
                "message": "No threshold breach in telemetry for the deployed revision."}
    existing = row("SELECT id FROM incidents WHERE release_id = ? AND status != 'resolved'", (release["id"],))
    if existing:
        return {"incident": get_incident(existing["id"]), "stats": stats, "message": "Incident already open"}

    evidence_items = []
    tel_id = evidence("telemetry_summary", "telemetry query",
                      f"checkout 5xx {stats['checkout_5xx']}/{checkout}, p95 {stats['checkout_p95_ms']} ms",
                      "deterministic", revision=release["revision"], run_id=release["run_id"])
    evidence_items.append({"id": tel_id, "kind": "evidence", "type": "telemetry",
                           "statement": f"{stats['checkout_5xx']} of {checkout} checkout requests returned 5xx "
                                        f"since {release['id']} was deployed; "
                                        f"checkout p95 {stats['checkout_p95_ms']} ms.",
                           "provenance": "deterministic"})
    reserve = next((d for d in stats["dependencies"] if d["operation"] == "inventory.reserve"), None)
    if reserve:
        evidence_items.append({"id": tel_id, "kind": "evidence", "type": "dependency_telemetry",
                               "statement": f"inventory.reserve: {reserve['errors']}/{reserve['count']} errors "
                                            f"{reserve['error_types']}, p95 {reserve['p95_ms']} ms, "
                                            f"max {reserve['max_ms']} ms.",
                               "provenance": "deterministic"})
    fault = inventory_sim.fault_state()
    if fault.get("active"):
        evidence_items.append({"id": "kv:fault.inventory_timeout", "kind": "evidence", "type": "fault_control",
                               "statement": f"Demo fault control shows an injected inventory timeout "
                                            f"({fault.get('delay_s')} s, by {fault.get('changed_by')}).",
                               "provenance": "injected_fault"})
    changed, added_no_timeout, inventory_files = [], [], "none in inventory"
    if release["manifest"].get("replaces_revision"):
        base = release["manifest"]["replaces_revision"]
        changed = workspace.changed_files(base, release["revision"])
        diff = workspace.diff(base, release["revision"])
        inventory_files = ", ".join(f for f in changed if "inventory" in f) or inventory_files
        current_file = None
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("+") and re.search(r"timeout\s*=\s*None", line):
                added_no_timeout.append(current_file)
        evidence_items.append({"id": release["id"], "kind": "evidence", "type": "release_change",
                               "statement": f"{release['id']} changed {len(changed)} files relative to "
                                            f"{base[:10]}, including "
                                            f"{inventory_files}.",
                               "provenance": "tool"})
    standard = get_index().search("client calls explicit timeout fail closed temporarily unavailable", k=1)
    hypotheses = []
    if added_no_timeout:
        hypotheses.append({
            "id": "H1", "kind": "hypothesis", "status": "supported by evidence (not proven)",
            "statement": f"The new order reservation call in {added_no_timeout[0]} sets timeout=None. While the "
                         "inventory dependency is slow, checkout waits and then fails with HTTP 500, instead of "
                         "failing fast as ENG-INV §4 requires.",
            "evidence_refs": [e["id"] for e in evidence_items] + [s["ref"] for s in standard],
            "test_to_confirm": "REG-002: run the inventory-timeout regression test on the released revision "
                               "(expected to fail) and on the candidate repair (expected to pass).",
        })
    hypotheses.append({
        "id": "H2", "kind": "hypothesis", "status": "known cause in this demo (injected)",
        "statement": "The inventory dependency itself is slow. In this demo that is the injected fault; in "
                     "production it would need confirming from the dependency owner's telemetry.",
        "evidence_refs": [e["id"] for e in evidence_items if e["type"] == "fault_control"],
    })
    analysis = {
        "disclaimer": DISCLAIMER, "window_start": since, "stats": stats, "evidence": evidence_items,
        "hypotheses": hypotheses, "standards": standard, "changed_files": changed,
        "proposed_actions": [
            {"action": "rollback", "detail": "Approved rollback to the last-known-good release (mitigation)."},
            {"action": "repair_release", "detail": "Bounded timeout and fail-closed handling for order reservation. "
                                                   "Reviewed through the same release gates."},
        ],
    }
    incident_id = new_id("INC")
    with session() as conn:
        conn.execute(
            "INSERT INTO incidents (id, run_id, release_id, revision, status, title, opened_at, analysis_json,"
            " fault_scripted) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, 1)",
            (incident_id, release["run_id"], release["id"], release["revision"],
             "Checkout failures after campaign release", now_iso(), json.dumps(analysis)),
        )
    audit(actor, "incident.open", entity_type="incident", entity_id=incident_id, release_id=release["id"])
    evidence("incident", "incident analyst", f"{incident_id} opened for {release['id']}", "deterministic",
             revision=release["revision"], run_id=release["run_id"], ref_table="incidents", ref_id=incident_id)
    return {"incident": get_incident(incident_id), "stats": stats, "message": "Incident opened"}


def set_status(incident_id: str, status: str, actor: str, note: str) -> None:
    with session() as conn:
        conn.execute("UPDATE incidents SET status = ?, resolved_at = CASE WHEN ? = 'resolved' THEN ? ELSE"
                     " resolved_at END WHERE id = ?", (status, status, now_iso(), incident_id))
    audit(actor, f"incident.{status}", entity_type="incident", entity_id=incident_id, note=note)
