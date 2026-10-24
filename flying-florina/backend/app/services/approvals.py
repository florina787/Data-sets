"""Human approval gate and the simulated, approval-bound write.

A request stores the exact payload and its SHA-256. Approval records the
approver, time and a hash over (approval id, payload hash, approver, decision,
time). Execution re-evaluates policy at execution time, requires the approval's
idempotency key, and records the key so a replay is rejected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core import audit, db, policy
from app.core.config import get_settings
from app.core.security import Actor
from app.core.util import new_id, now_iso, sha256_json


class ApprovalError(Exception):
    def __init__(self, code: str, message: str, decision: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.decision = decision


def create(kind: str, title: str, requested_by: Actor, payload: dict[str, Any], run_id: str | None = None,
           risk: str = "high", ttl_seconds: int | None = None) -> dict[str, Any]:
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().approval_ttl_seconds
    approval = {
        "id": new_id("APR"),
        "kind": kind,
        "title": title,
        "requested_by": requested_by.id,
        "requested_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat(),
        "status": "pending",
        "payload": payload,
        "payload_sha256": sha256_json(payload),
        "run_id": run_id,
        "risk": risk,
        "idempotency_key": new_id("IDEM"),
    }
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO approvals (id, kind, title, requested_by, requested_at, expires_at, status, payload_json, "
            "payload_sha256, run_id, risk, idempotency_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (approval["id"], kind, title, requested_by.id, approval["requested_at"], approval["expires_at"], "pending",
             db.jdump(payload), approval["payload_sha256"], run_id, risk, approval["idempotency_key"]),
        )
        audit.append(requested_by.id, "approval.requested", f"{kind}: {title}",
                     {"approval_id": approval["id"], "payload_sha256": approval["payload_sha256"], "run_id": run_id}, conn)
    return approval


def get(approval_id: str) -> dict[str, Any] | None:
    a = db.query_one("SELECT * FROM approvals WHERE id = ?", (approval_id,))
    if a:
        a["payload"] = db.jload(a.pop("payload_json"), {})
        a["expired"] = datetime.fromisoformat(a["expires_at"]) < datetime.now(timezone.utc)
    return a


def list_all(status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM approvals"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    out = db.query(sql + " ORDER BY requested_at DESC", params)
    now = datetime.now(timezone.utc)
    for a in out:
        a["payload"] = db.jload(a.pop("payload_json"), {})
        a["expired"] = datetime.fromisoformat(a["expires_at"]) < now
    return out


def decide(approval_id: str, actor: Actor, approve: bool, note: str = "") -> dict[str, Any]:
    a = get(approval_id)
    if not a:
        raise ApprovalError("not_found", "Approval request not found.")
    if a["status"] != "pending":
        raise ApprovalError("already_decided", f"Approval is already '{a['status']}'.")
    if a["expired"]:
        with db.session(write=True) as conn:
            conn.execute("UPDATE approvals SET status='expired' WHERE id = ?", (approval_id,))
        raise ApprovalError("expired", "Approval request has expired.")
    d = policy.evaluate(actor, policy.PolicyRequest(action="approve", resource=f"approval:{approval_id}",
                                                    label="RESTRICTED" if a["kind"] == "work_order" else "INTERNAL",
                                                    approval_id=approval_id, run_id=a["run_id"]))
    if not d.allowed:
        raise ApprovalError("policy_denied", d.reason, d.as_dict())
    decided_at = now_iso()
    status = "approved" if approve else "rejected"
    evidence = sha256_json([approval_id, a["payload_sha256"], actor.id, status, decided_at])
    with db.session(write=True) as conn:
        conn.execute("UPDATE approvals SET status=?, decided_by=?, decided_at=?, evidence_sha256=?, note=? WHERE id=? AND status='pending'",
                     (status, actor.id, decided_at, evidence, note[:500], approval_id))
        audit.append(actor.id, f"approval.{status}", f"{a['kind']} {approval_id} {status}",
                     {"approval_id": approval_id, "evidence_sha256": evidence, "decision_id": d.id}, conn)
    return {**get(approval_id), "decision": d.as_dict()}


def execute(approval_id: str, actor: Actor, idempotency_key: str | None) -> dict[str, Any]:
    """Run the approved write against the synthetic DB (simulated system of record)."""
    a = get(approval_id)
    if not a:
        raise ApprovalError("not_found", "Approval request not found.")
    d = policy.evaluate(actor, policy.PolicyRequest(action="write", resource=f"approval:{approval_id}", label="RESTRICTED",
                                                    approval_id=approval_id, idempotency_key=idempotency_key, run_id=a["run_id"]))
    if not d.allowed:
        raise ApprovalError("policy_denied", d.reason, d.as_dict())
    payload = a["payload"]
    result: dict[str, Any] = {"simulated": True, "approval_id": approval_id}
    with db.session(write=True) as conn:
        if a["kind"] == "work_order":
            wo_id = f"WO-{95000 + conn.execute('SELECT COUNT(*) FROM write_log').fetchone()[0]}"  # noqa: S608 - constant SQL
            conn.execute("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (wo_id, payload.get("aircraft_id"), "planned", "urgent", now_iso()[:10], None,
                          (payload.get("title") or "")[:300] + " [created from approved draft - synthetic]",
                          payload.get("part_number"), payload.get("technician"), None, "FLYING-FLORINA-SIM", "RESTRICTED"))
            result["work_order_id"] = wo_id
        conn.execute("INSERT INTO write_log VALUES (?,?,?,?,?,?)",
                     (idempotency_key, now_iso(), actor.id, approval_id, a["kind"], db.jdump(result)))
        conn.execute("UPDATE approvals SET executed = 1 WHERE id = ?", (approval_id,))
        audit.append(actor.id, "write.executed", f"Simulated write for {approval_id}",
                     {"approval_id": approval_id, "result": result, "decision_id": d.id}, conn)
    return {"result": result, "decision": d.as_dict()}
