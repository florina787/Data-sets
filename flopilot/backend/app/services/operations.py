"""Operation lifecycle: propose -> (approve) -> apply -> validate -> publish, plus restore.

Approval is bound to the operation id, the base workbook version and the change-set hash. A
proposal made against version N can only be applied while N is still current; otherwise it is
marked STALE and must be re-proposed. Idempotency keys make retried approvals safe: the
second request returns the first result instead of writing again.
"""
from __future__ import annotations

from typing import Any

from .. import audit, db
from ..auth import Principal
from ..common import AppError, new_id, now_iso, sha256_bytes, stable_hash
from ..workbook import recalc
from ..workbook.changes import apply_change_set, make_change_set
from ..workbook.fidelity import detect_features
from ..workbook.model import load_model
from ..workbook.validate import validate_candidate
from . import workbooks as W

PENDING, APPLYING, APPLIED, FAILED, REJECTED, STALE = "PROPOSED", "APPLYING", "APPLIED", "FAILED", "REJECTED", "STALE"
SAMPLE_CHANGES = 60


def _load(op_id: str) -> dict:
    row = db.fetchone("SELECT * FROM operations WHERE id = ?", (op_id,))
    if not row:
        raise AppError("operation_not_found", "Operation not found.", 404)
    row["payload"] = db.loads(row["payload"], {})
    row["result"] = db.loads(row["result"], {})
    return row


def _set(op_id: str, **fields: Any) -> None:
    fields["updated_at"] = now_iso()
    for key in ("payload", "result"):
        if key in fields:
            fields[key] = db.dumps(fields[key])
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE operations SET {cols} WHERE id = ?", (*fields.values(), op_id))


def view(op: dict, current_version: int | None = None) -> dict:
    cs = op["payload"]
    res = op["result"] or {}
    if current_version is None:
        row = db.fetchone("SELECT current_version FROM workbooks WHERE id = ?", (op["workbook_id"],))
        current_version = row["current_version"] if row else None
    out_of_date = op["status"] == PENDING and current_version is not None and current_version != op["base_version"]
    return {
        "out_of_date": out_of_date, "current_version": current_version,
        "schema_version": "1.0",
        "id": op["id"], "workbook_id": op["workbook_id"], "base_version": op["base_version"],
        "run_id": op["run_id"], "action_type": op["action_type"], "mutating": bool(op["mutating"]),
        "status": op["status"], "title": op["title"], "description": cs.get("description"),
        "sheet": cs.get("sheet"), "target_range": cs.get("target_range"),
        "affected_cells": cs.get("affected_cells"), "flags": cs.get("flags"), "destructive": cs.get("destructive"),
        "warnings": cs.get("warnings", []), "details": cs.get("details", {}),
        "changes_sample": cs.get("changes", [])[:SAMPLE_CHANGES], "changes_total": len(cs.get("changes", [])),
        "structural": {k: v for k, v in (cs.get("structural") or {}).items() if k != "removed"} or None,
        "removed_rows_sample": (cs.get("structural") or {}).get("removed", [])[:20],
        "new_sheet": cs.get("new_sheet"), "target_version": cs.get("target_version"),
        "change_set_hash": op["change_set_hash"], "approval_required": True,
        "requires_acknowledgement": bool(res.get("dry_run", {}).get("fidelity", {}).get("lost")),
        "fidelity_at_risk": res.get("fidelity_at_risk", []),
        "dry_run": res.get("dry_run"), "verification": res.get("verification"),
        "validation": res.get("validation"), "error": res.get("error"),
        "result_version": op["result_version"], "created_at": op["created_at"], "updated_at": op["updated_at"],
        "validation_rules": ["reopens", "no_sheet_removed", "sheet_order", "only_planned_cells_changed",
                             "no_unexpected_formula_overwrites", "changes_applied_exactly", "totals_reconcile",
                             "features_preserved", "package_fidelity"],
        "preconditions": cs.get("preconditions", []),
    }


def propose(principal: Principal, workbook_id: str, base_version: int, change_set: dict, run_id: str | None = None) -> dict:
    principal.require("propose")
    row = W.get_workbook_row(principal, workbook_id)
    if row["current_version"] != base_version:
        raise AppError("stale_version", "The workbook changed while this proposal was being prepared. Ask again.", 409)
    base = W.version_bytes(workbook_id, base_version)
    if change_set["action_type"] == "restore_version":
        candidate = W.version_bytes(workbook_id, change_set["target_version"])
        dry = _validate_restore(candidate, change_set)
    else:
        candidate = apply_change_set(base, change_set)
        dry = validate_candidate(base, candidate, change_set, acknowledged_risks=True)
    verification = _verify_formulas(candidate, change_set)
    op_id = new_id("op")
    ts = now_iso()
    result = {
        "dry_run": dry,
        "fidelity_at_risk": detect_features(base)["at_risk"],
        "verification": verification,
    }
    db.execute(
        "INSERT INTO operations(id,workbook_id,base_version,run_id,action_type,mutating,status,title,payload,change_set_hash,"
        "result,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (op_id, workbook_id, base_version, run_id, change_set["action_type"], 1, PENDING, change_set["title"],
         db.dumps(change_set), stable_hash(change_set), db.dumps(result), principal.user_id, ts, ts))
    audit.record("operation_proposed", run_id=run_id, user_id=principal.user_id, workspace_id=principal.workspace_id,
                 workbook_id=workbook_id, workbook_version=base_version, operation_id=op_id,
                 action_type=change_set["action_type"], affected_cells=change_set["affected_cells"],
                 destructive=change_set.get("destructive"), dry_run_passed=dry["passed"])
    return view(_load(op_id))


def _validate_restore(candidate: bytes, cs: dict) -> dict:
    checks = []
    try:
        load_model(candidate)
        checks.append({"name": "reopens", "passed": True, "detail": "The restored version opens successfully."})
    except AppError:
        checks.append({"name": "reopens", "passed": False, "detail": "The restored version could not be opened."})
    ok = sha256_bytes(candidate) == cs["target_sha256"]
    checks.append({"name": "identical_to_target", "passed": ok,
                   "detail": f"Content is byte-identical to version {cs['target_version']}." if ok else "Content does not match the target version."})
    return {"passed": all(c["passed"] for c in checks), "checks": checks, "fidelity": {"lost": {}}}


def _verify_formulas(candidate: bytes, cs: dict) -> dict | None:
    formula_cells = [(c["sheet"], c["cell"]) for c in cs.get("changes", []) if c["after"].get("formula")]
    if not formula_cells:
        return None
    sample = formula_cells[:200]
    result = recalc.verify_cells(candidate, sample)
    previews = {f"{c['sheet']}!{c['cell']}": c["after"]["value"] for c in cs["changes"] if c["after"].get("formula")}
    if result["status"] == "verified":
        mismatches = []
        for key, value in result["values"].items():
            p = previews.get(key)
            if p is None or value is None:
                continue
            if isinstance(p, (int, float)) and isinstance(value, (int, float)):
                if abs(p - value) > 1e-6 * max(1.0, abs(value)):
                    mismatches.append(key)
            elif str(p) != str(value):
                mismatches.append(key)
        result["checked_cells"] = len(result["values"])
        result["preview_mismatches"] = mismatches[:20]
        result["values"] = dict(list(result["values"].items())[:SAMPLE_CHANGES])
        result["unsupported_by_engine"] = sum(1 for v in result["values"].values() if v == "#NAME?")
    result["total_formula_cells"] = len(formula_cells)
    return result


def get_operation(principal: Principal, op_id: str) -> dict:
    op = _load(op_id)
    W.get_workbook_row(principal, op["workbook_id"])
    return view(op)


def list_operations(principal: Principal, workbook_id: str) -> list[dict]:
    W.get_workbook_row(principal, workbook_id)
    rows = db.fetchall("SELECT id FROM operations WHERE workbook_id = ? ORDER BY created_at DESC LIMIT 200", (workbook_id,))
    out = []
    for r in rows:
        v = view(_load(r["id"]))
        v.pop("changes_sample", None)
        out.append(v)
    return out


def reject(principal: Principal, op_id: str) -> dict:
    op = _load(op_id)
    W.get_workbook_row(principal, op["workbook_id"])
    principal.require("approve")
    if op["status"] != PENDING:
        raise AppError("operation_not_pending", f"This change is already {op['status'].lower()}.", 409)
    _set(op_id, status=REJECTED)
    _record_approval(op, principal, "rejected", False)
    _advance_run(op["run_id"], "CANCELLED", "Change rejected by the user.")
    audit.record("operation_rejected", run_id=op["run_id"], user_id=principal.user_id, workspace_id=principal.workspace_id,
                 workbook_id=op["workbook_id"], workbook_version=op["base_version"], operation_id=op_id)
    return view(_load(op_id))


def supersede(principal: Principal, op_id: str) -> None:
    """Mark an out-of-date proposal STALE after it has been prepared again."""
    op = _load(op_id)
    if op["status"] == PENDING:
        _set(op_id, status=STALE)
        audit.record("operation_superseded", user_id=principal.user_id, workspace_id=principal.workspace_id,
                     workbook_id=op["workbook_id"], workbook_version=op["base_version"], operation_id=op_id)


def _record_approval(op: dict, principal: Principal, decision: str, ack: bool) -> None:
    db.execute("INSERT INTO approvals(id,operation_id,workbook_version,change_set_hash,decision,acknowledged_risks,user_id,created_at) "
               "VALUES(?,?,?,?,?,?,?,?)",
               (new_id("apr"), op["id"], op["base_version"], op["change_set_hash"], decision, str(ack), principal.user_id, now_iso()))


def _advance_run(run_id: str | None, state: str, note: str | None = None, result_patch: dict | None = None) -> None:
    if not run_id:
        return
    from ..harness.state import advance_run_from_operation

    advance_run_from_operation(run_id, state, note, result_patch)


def approve_and_apply(principal: Principal, op_id: str, expected_version: int, change_set_hash: str,
                      acknowledge_risks: bool = False, idempotency_key: str | None = None) -> dict:
    op = _load(op_id)
    W.get_workbook_row(principal, op["workbook_id"])
    principal.require("approve")

    if idempotency_key:
        prior = db.fetchone("SELECT id FROM operations WHERE idempotency_key = ?", (idempotency_key,))
        if prior and prior["id"] != op_id:
            raise AppError("idempotency_conflict", "This idempotency key was already used for a different change.", 409)
    if op["status"] == APPLIED:
        # Safe retry: never write twice for the same operation.
        return view(op) | {"idempotent_replay": True}
    if op["status"] != PENDING:
        raise AppError("operation_not_pending", f"This change is {op['status'].lower()} and cannot be applied.", 409)
    if change_set_hash != op["change_set_hash"]:
        raise AppError("approval_mismatch", "The approval does not match the proposed change set. Review the latest proposal.", 409)
    current = W.get_workbook_row(principal, op["workbook_id"])["current_version"]
    if expected_version != op["base_version"] or current != op["base_version"]:
        _set(op_id, status=STALE)
        _advance_run(op["run_id"], "FAILED", "The workbook changed after this change was proposed.")
        audit.record("approval_rejected_stale", user_id=principal.user_id, workspace_id=principal.workspace_id,
                     workbook_id=op["workbook_id"], workbook_version=current, operation_id=op_id,
                     approved_version=expected_version, base_version=op["base_version"])
        raise AppError("stale_approval", f"This change was prepared for version {op['base_version']}, but the workbook is now at "
                       f"version {current}. Ask FloPilot to prepare it again.", 409)
    if view(op)["requires_acknowledgement"] and not acknowledge_risks:
        raise AppError("acknowledgement_required", "Applying this change would drop workbook features (see the fidelity warning). "
                       "Confirm that you accept this before applying.", 412)

    # Claim the operation atomically so concurrent approvals cannot both apply it.
    with db.tx() as conn:
        claimed = conn.execute("UPDATE operations SET status = ?, idempotency_key = ?, updated_at = ? WHERE id = ? AND status = ?",
                               (APPLYING, idempotency_key, now_iso(), op_id, PENDING)).rowcount
    if claimed != 1:
        raise AppError("operation_not_pending", "This change is already being applied.", 409)
    _record_approval(op, principal, "approved", acknowledge_risks)
    audit.record("operation_approved", run_id=op["run_id"], user_id=principal.user_id, workspace_id=principal.workspace_id,
                 workbook_id=op["workbook_id"], workbook_version=op["base_version"], operation_id=op_id,
                 acknowledged_risks=acknowledge_risks)
    _advance_run(op["run_id"], "APPLYING")

    cs = op["payload"]
    result = dict(op["result"])
    try:
        base = W.version_bytes(op["workbook_id"], op["base_version"])
        if cs["action_type"] == "restore_version":
            candidate = W.version_bytes(op["workbook_id"], cs["target_version"])
            _advance_run(op["run_id"], "VALIDATING")
            validation = _validate_restore(candidate, cs)
        else:
            candidate = apply_change_set(base, cs)
            _advance_run(op["run_id"], "VALIDATING")
            validation = validate_candidate(base, candidate, cs, acknowledged_risks=acknowledge_risks)
        result["validation"] = validation
        if not validation["passed"]:
            _set(op_id, status=FAILED, result=result)
            _advance_run(op["run_id"], "ROLLED_BACK", "Validation failed; the previous version is unchanged.")
            audit.record("validation_failed", run_id=op["run_id"], user_id=principal.user_id, workspace_id=principal.workspace_id,
                         workbook_id=op["workbook_id"], workbook_version=op["base_version"], operation_id=op_id,
                         failed_checks=[c["name"] for c in validation["checks"] if not c["passed"]])
            return view(_load(op_id))
        kind = "restore" if cs["action_type"] == "restore_version" else "edit"
        new_version = W.publish_version(principal, op["workbook_id"], op["base_version"], candidate, kind, op_id, cs["title"])
    except AppError as exc:
        result["error"] = exc.to_dict()
        status = STALE if exc.code in ("stale_version", "precondition_failed") else FAILED
        _set(op_id, status=status, result=result)
        _advance_run(op["run_id"], "FAILED", exc.message)
        audit.record("operation_failed", run_id=op["run_id"], user_id=principal.user_id, workspace_id=principal.workspace_id,
                     workbook_id=op["workbook_id"], workbook_version=op["base_version"], operation_id=op_id, code=exc.code)
        raise
    except Exception:
        result["error"] = {"code": "apply_failed", "message": "The change could not be applied. The previous version is unchanged."}
        _set(op_id, status=FAILED, result=result)
        _advance_run(op["run_id"], "FAILED", "The change could not be applied.")
        raise

    _set(op_id, status=APPLIED, result=result, result_version=new_version)
    _advance_run(op["run_id"], "COMPLETED", None, {"applied_version": new_version, "operation_id": op_id})
    audit.record("operation_applied", run_id=op["run_id"], user_id=principal.user_id, workspace_id=principal.workspace_id,
                 workbook_id=op["workbook_id"], workbook_version=new_version, operation_id=op_id,
                 action_type=cs["action_type"], affected_cells=cs["affected_cells"],
                 checks_passed=len(validation["checks"]))
    return view(_load(op_id))


def restore_change_set(principal: Principal, workbook_id: str, target_version: int) -> dict:
    row = W.get_workbook_row(principal, workbook_id)
    principal.require("restore")
    if not 1 <= target_version < row["current_version"]:
        raise AppError("invalid_restore", f"Choose a version between 1 and {row['current_version'] - 1}.", 422)
    target = db.fetchone("SELECT sha256, note FROM versions WHERE workbook_id = ? AND version_no = ?", (workbook_id, target_version))
    cs = make_change_set("restore_version", f"Restore version {target_version}",
                         f"Create version {row['current_version'] + 1} with the exact contents of version {target_version} "
                         f"({target['note']}). Later versions stay in history and can be restored again.", None, [],
                         warnings=[f"Changes made after version {target_version} will not be in the new current version."])
    cs["target_version"] = target_version
    cs["target_sha256"] = target["sha256"]
    return cs
