"""Run state machine. Every transition is validated and checkpointed to the database."""
from __future__ import annotations

from enum import Enum
from typing import Any

from .. import audit, db
from ..common import AppError, now_iso


class RunState(str, Enum):
    RECEIVED = "RECEIVED"
    INSPECTING = "INSPECTING"
    PLANNING = "PLANNING"
    EXECUTING_READS = "EXECUTING_READS"
    PREVIEW_READY = "PREVIEW_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPLYING = "APPLYING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"


S = RunState
TERMINAL = {S.COMPLETED, S.FAILED, S.CANCELLED, S.ROLLED_BACK}
TRANSITIONS: dict[RunState, set[RunState]] = {
    S.RECEIVED: {S.INSPECTING, S.FAILED, S.CANCELLED},
    S.INSPECTING: {S.PLANNING, S.FAILED, S.CANCELLED},
    S.PLANNING: {S.EXECUTING_READS, S.COMPLETED, S.FAILED, S.CANCELLED},  # COMPLETED: clarification needed
    S.EXECUTING_READS: {S.PREVIEW_READY, S.COMPLETED, S.FAILED, S.CANCELLED},  # read-only requests finish here
    S.PREVIEW_READY: {S.AWAITING_APPROVAL, S.FAILED, S.CANCELLED},
    S.AWAITING_APPROVAL: {S.APPLYING, S.CANCELLED, S.FAILED},
    S.APPLYING: {S.VALIDATING, S.FAILED},
    S.VALIDATING: {S.COMPLETED, S.ROLLED_BACK, S.FAILED},
    S.COMPLETED: set(), S.FAILED: set(), S.CANCELLED: set(), S.ROLLED_BACK: set(),
}

PROGRESS_TEXT = {
    S.RECEIVED: "Received your request…",
    S.INSPECTING: "Inspecting your workbook…",
    S.PLANNING: "Planning the steps…",
    S.EXECUTING_READS: "Reading and calculating…",
    S.PREVIEW_READY: "Preparing a preview of the changes…",
    S.AWAITING_APPROVAL: "Waiting for your approval.",
    S.APPLYING: "Applying the approved changes…",
    S.VALIDATING: "Validating the changes…",
    S.COMPLETED: "Done.",
    S.FAILED: "Something went wrong.",
    S.CANCELLED: "Cancelled.",
    S.ROLLED_BACK: "Validation failed — nothing was changed.",
}


def can_transition(current: RunState, target: RunState) -> bool:
    return target in TRANSITIONS[current]


def load_run(run_id: str) -> dict:
    row = db.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))
    if not row:
        raise AppError("run_not_found", "Run not found.", 404)
    row["steps"] = db.loads(row["steps"], [])
    row["plan"] = db.loads(row["plan"], None)
    row["result"] = db.loads(row["result"], None)
    return row


def transition(run_id: str, target: RunState, *, note: str | None = None, error: str | None = None,
               result: Any = None, result_patch: dict | None = None) -> None:
    run = load_run(run_id)
    current = RunState(run["state"])
    if current == target:
        return
    if not can_transition(current, target):
        raise AppError("invalid_transition", f"Run cannot move from {current.value} to {target.value}.", 409)
    steps = run["steps"]
    steps.append({"type": "state", "state": target.value, "at": now_iso(), "note": note or PROGRESS_TEXT[target]})
    fields: dict[str, Any] = {"state": target.value, "steps": db.dumps(steps), "updated_at": now_iso()}
    if error is not None:
        fields["error"] = error
    if result is not None or result_patch:
        merged = result if result is not None else (run["result"] or {})
        if result_patch:
            merged = {**(merged or {}), **result_patch}
        fields["result"] = db.dumps(merged)
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))
    audit.record("run_state", run_id=run_id, correlation_id=run["correlation_id"], user_id=run["user_id"],
                 workspace_id=run["workspace_id"], workbook_id=run["workbook_id"], workbook_version=run["workbook_version"],
                 state=target.value, previous=current.value)


def advance_run_from_operation(run_id: str, state: str, note: str | None, result_patch: dict | None) -> None:
    """Move a run forward when its operation is approved/applied. Runs that already finished
    (e.g. a second proposal from the same request) just get a step record."""
    run = load_run(run_id)
    current, target = RunState(run["state"]), RunState(state)
    if can_transition(current, target):
        transition(run_id, target, note=note, result_patch=result_patch)
        return
    # Walk APPLYING -> VALIDATING -> target when the operation finished in one call.
    if current == S.AWAITING_APPROVAL and target in (S.VALIDATING, S.COMPLETED, S.ROLLED_BACK):
        transition(run_id, S.APPLYING)
        current = S.APPLYING
    if current == S.APPLYING and target in (S.COMPLETED, S.ROLLED_BACK):
        transition(run_id, S.VALIDATING)
        current = S.VALIDATING
    if can_transition(current, target):
        transition(run_id, target, note=note, result_patch=result_patch)
        return
    steps = run["steps"]
    steps.append({"type": "operation_event", "state": target.value, "at": now_iso(), "note": note or PROGRESS_TEXT[target]})
    db.execute("UPDATE runs SET steps = ?, updated_at = ? WHERE id = ?", (db.dumps(steps), now_iso(), run_id))


def recover_interrupted_runs() -> int:
    """Called at startup: runs left mid-flight by a crash are failed safely. Workbook versions
    are published atomically, so an interrupted APPLYING run never leaves a partial version."""
    rows = db.fetchall("SELECT id, state FROM runs WHERE state IN (?,?,?,?,?,?,?)",
                       tuple(s.value for s in (S.RECEIVED, S.INSPECTING, S.PLANNING, S.EXECUTING_READS, S.PREVIEW_READY,
                                               S.APPLYING, S.VALIDATING)))
    for row in rows:
        steps = load_run(row["id"])["steps"]
        steps.append({"type": "state", "state": "FAILED", "at": now_iso(), "note": "Interrupted by a server restart."})
        db.execute("UPDATE runs SET state = ?, error = ?, steps = ?, updated_at = ? WHERE id = ?",
                   ("FAILED", "Interrupted by a server restart; no partial changes were published.", db.dumps(steps), now_iso(), row["id"]))
    db.execute("UPDATE operations SET status = 'FAILED', updated_at = ? WHERE status = 'APPLYING'", (now_iso(),))
    return len(rows)
