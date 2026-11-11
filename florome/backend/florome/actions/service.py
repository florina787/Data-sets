"""Remediation lifecycle: PLAN -> APPROVE -> EXECUTE -> VALIDATE -> LEARN.

Execution guarantees
--------------------
* Approval is bound to the plan hash. Changing a plan invalidates earlier approvals.
* Separation of duties: the approver must not be the plan's creator.
* Replay protection: each approval carries a client nonce that may be used once (unique constraint).
* Approvals expire (policy ``approval_ttl_minutes``); expiry is checked again when execution starts.
* Policy (emergency stop, budget, environment, mode) is re-evaluated at execution time, not only at planning.
* Only one executor at a time: the plan moves to ``executing`` with a compare-and-set on (status, version).
* Durable checkpoints: each step is an ``ActionExecution`` row keyed by a deterministic idempotency key. Resuming
  a failed plan skips steps that already succeeded and continues from the failed one.
* Each attempt runs under a timeout; only errors the connector marks retryable are retried, up to a fixed limit.
* Nothing is reported as successful unless the connector returned success, and the incident is resolved only if
  post-execution validation passes.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from florome.actions.planner import build_plan
from florome.connectors.base import ConnectorError
from florome.context import AppContext
from florome.governance.policy import effective_policy, evaluate_plan
from florome.models import (
    ActionExecution,
    Approval,
    Evidence,
    Incident,
    RCAReport,
    RemediationPlan,
    Tenant,
    ValidationResult,
    as_utc,
    utcnow,
)
from florome.rca.service import load_topology
from florome.security import audit
from florome.security.rbac import Principal


class ActionError(RuntimeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _actions_last_hour(db: Session, tenant_id: str) -> int:
    since = utcnow() - timedelta(hours=1)
    return db.scalar(select(func.count()).select_from(ActionExecution)
                     .where(ActionExecution.tenant_id == tenant_id, ActionExecution.started_at >= since)) or 0


RUNTIME_STEP_FIELDS = {"status", "message"}


def plan_hash(steps: list[dict[str, Any]], validation_targets: list[str], incident_id: str) -> str:
    """Hash of what was approved: steps without their runtime progress fields."""
    frozen = [{k: v for k, v in s.items() if k not in RUNTIME_STEP_FIELDS} for s in steps]
    return audit.sha256({"incident": incident_id, "steps": frozen, "validation_targets": validation_targets})


def create_plan(db: Session, ctx: AppContext, actor: Principal, incident: Incident) -> RemediationPlan:
    rca = db.scalars(select(RCAReport).where(RCAReport.incident_id == incident.id).order_by(RCAReport.created_at.desc())).first()
    if rca is None:
        raise ActionError("Run RCA before planning remediation", 409)
    tenant = db.get(Tenant, incident.tenant_id)
    topo = load_topology(db, incident.tenant_id)
    ev = {e.id: {"kind": e.kind, "payload": e.payload} for e in db.scalars(select(Evidence).where(Evidence.incident_id == incident.id))}
    draft = build_plan(rca.report, topo, ev, lambda cid: ctx.registry.get(cid) if ctx.registry.has(cid) else None, utcnow())
    policy = effective_policy(tenant.policy)
    decision = evaluate_plan(draft["steps"], policy, emergency_stop=tenant.emergency_stop, tenant_mode=tenant.mode,
                             actions_last_hour=_actions_last_hour(db, tenant.id))
    for s in draft["steps"]:
        s["status"] = "pending"
    status = "blocked" if not decision.allowed else ("pending_approval" if decision.requires_approval else "approved")
    meta = {"notes": draft["notes"], "validation_targets": draft["validation_targets"], "rca_status": draft["rca_status"],
            "next_diagnostics": draft["next_diagnostics"]}
    plan = RemediationPlan(tenant_id=incident.tenant_id, incident_id=incident.id, rca_id=rca.id, status=status, steps=draft["steps"],
                           plan_hash=plan_hash(draft["steps"], draft["validation_targets"], incident.id), risk=draft["risk"],
                           requires_approval=decision.requires_approval, policy_decision={**decision.as_dict(), **meta},
                           created_by=actor.user_id)
    db.add(plan)
    db.flush()
    audit.record(db, incident.tenant_id, actor.user_id, "plan.create", plan.id, "success",
                 {"incident": incident.id, "status": status, "plan_hash": plan.plan_hash, "steps": [s["action_id"] for s in draft["steps"]]})
    return plan


def decide(db: Session, ctx: AppContext, actor: Principal, plan: RemediationPlan, *, approve: bool, presented_hash: str,
           nonce: str, comment: str = "") -> Approval:
    tenant = db.get(Tenant, plan.tenant_id)
    policy = effective_policy(tenant.policy)

    def deny(reason: str, status: int = 403) -> ActionError:
        audit.record(db, plan.tenant_id, actor.user_id, "plan.approve", plan.id, "denied", {"reason": reason})
        db.commit()
        return ActionError(reason, status)

    if not actor.can("plan:approve"):
        raise deny("Missing permission plan:approve")
    if plan.status != "pending_approval":
        raise deny(f"Plan is '{plan.status}', not pending approval", 409)
    if policy["require_separation_of_duties"] and actor.user_id == plan.created_by:
        raise deny("Separation of duties: the plan's creator cannot approve it")
    if presented_hash != plan.plan_hash:
        raise deny("Plan hash mismatch: the plan changed after it was presented for approval", 409)
    if not nonce or len(nonce) < 16:
        raise deny("A unique approval nonce of at least 16 characters is required", 422)
    appr = Approval(tenant_id=plan.tenant_id, plan_id=plan.id, approver_id=actor.user_id, decision="approved" if approve else "rejected",
                    plan_hash=plan.plan_hash, nonce=nonce, comment=comment[:2000],
                    expires_at=utcnow() + timedelta(minutes=policy["approval_ttl_minutes"]))
    try:
        with db.begin_nested():
            db.add(appr)
    except IntegrityError:
        raise deny("Approval nonce already used (replay rejected)", 409) from None
    plan.status = "approved" if approve else "rejected"
    plan.version += 1
    audit.record(db, plan.tenant_id, actor.user_id, "plan.approve" if approve else "plan.reject", plan.id, "success",
                 {"plan_hash": plan.plan_hash, "approval_id": appr.id, "expires_at": appr.expires_at.isoformat()})
    return appr


def _valid_approval(db: Session, plan: RemediationPlan) -> Approval | None:
    a = db.scalars(select(Approval).where(Approval.plan_id == plan.id, Approval.decision == "approved")
                   .order_by(Approval.created_at.desc())).first()
    if a is None or a.plan_hash != plan.plan_hash or as_utc(a.expires_at) < utcnow():
        return None
    return a


async def execute(db: Session, ctx: AppContext, actor: Principal, plan: RemediationPlan) -> RemediationPlan:
    tenant = db.get(Tenant, plan.tenant_id)
    policy = effective_policy(tenant.policy)

    def deny(reason: str, status: int = 403) -> ActionError:
        audit.record(db, plan.tenant_id, actor.user_id, "plan.execute", plan.id, "denied", {"reason": reason})
        db.commit()
        return ActionError(reason, status)

    if not actor.can("plan:execute"):
        raise deny("Missing permission plan:execute")
    if tenant.emergency_stop:
        raise deny("Emergency stop is active", 423)
    if plan.status not in ("approved", "failed"):
        raise deny(f"Plan is '{plan.status}'; only approved plans (or failed plans being resumed) can execute", 409)
    if plan_hash(plan.steps, plan.policy_decision.get("validation_targets", []), plan.incident_id) != plan.plan_hash:
        raise deny("Stored plan does not match its hash; refusing to execute", 409)
    if plan.requires_approval and _valid_approval(db, plan) is None:
        raise deny("No valid approval: missing, expired, or bound to a different plan version")
    remaining = [s for s in plan.steps if s.get("status") != "succeeded"]
    decision = evaluate_plan(remaining, policy, emergency_stop=tenant.emergency_stop, tenant_mode=tenant.mode,
                             actions_last_hour=_actions_last_hour(db, tenant.id))
    if not decision.allowed:
        raise deny("Policy re-evaluation blocked execution: " + "; ".join(decision.reasons))

    # Compare-and-set: exactly one executor proceeds.
    claimed = db.execute(update(RemediationPlan).where(RemediationPlan.id == plan.id, RemediationPlan.status == plan.status,
                                                       RemediationPlan.version == plan.version)
                         .values(status="executing", version=plan.version + 1)).rowcount
    if claimed != 1:
        raise deny("Plan is already being executed or changed concurrently", 409)
    db.commit()
    db.refresh(plan)
    audit.record(db, plan.tenant_id, actor.user_id, "plan.execute.start", plan.id, "info", {"from_step": plan.current_step})

    steps = [dict(s) for s in plan.steps]
    incident = db.get(Incident, plan.incident_id)
    incident.status = "remediating"
    for i in range(plan.current_step, len(steps)):
        step = steps[i]
        ok, message = await _run_step(db, ctx, actor, plan, step)
        steps[i] = {**step, "status": "succeeded" if ok else "failed", "message": message}
        plan.steps = [dict(x) for x in steps]  # new object each time: JSON columns only persist on reassignment
        if not ok:
            plan.status, plan.current_step, plan.last_error = "failed", i, message
            plan.version += 1
            audit.record(db, plan.tenant_id, actor.user_id, "plan.execute", plan.id, "failed", {"step": i, "error": message})
            db.commit()
            return plan
        plan.current_step = i + 1
        db.commit()  # durable checkpoint after every step

    result = await validate(db, ctx, plan)
    plan.status = "succeeded" if result.passed else "failed"
    plan.last_error = None if result.passed else "Post-execution validation failed"
    plan.version += 1
    if result.passed:
        incident.status, incident.resolved_at = "resolved", utcnow()
    incident.fingerprint = {**incident.fingerprint, "outcome": {"resolved": result.passed, "plan_id": plan.id,
                                                                "actions": [s["action_id"] for s in steps]}}
    audit.record(db, plan.tenant_id, actor.user_id, "plan.execute", plan.id, "success" if result.passed else "failed",
                 {"validation_id": result.id, "validation_passed": result.passed})
    db.commit()
    return plan


async def _run_step(db: Session, ctx: AppContext, actor: Principal, plan: RemediationPlan, step: dict[str, Any]) -> tuple[bool, str]:
    key = audit.sha256(f"{plan.id}:{step['index']}:{plan.plan_hash}")
    row = db.scalars(select(ActionExecution).where(ActionExecution.idempotency_key == key)).first()
    if row is not None and row.status == "succeeded":
        return True, "Already succeeded (idempotent resume)"
    if row is None:
        row = ActionExecution(tenant_id=plan.tenant_id, plan_id=plan.id, step_index=step["index"], connection_id=step["connection_id"],
                              action_id=step["action_id"], target_resource_id=step["target_resource_id"], params=step["params"],
                              idempotency_key=key, status="running", executed_by=actor.user_id)
        db.add(row)
    row.status, row.started_at, row.error = "running", utcnow(), None
    db.commit()

    if not ctx.registry.has(step["connection_id"]):
        row.status, row.error, row.finished_at = "failed", "Connector instance unavailable", utcnow()
        return False, row.error
    connector = ctx.registry.get(step["connection_id"])
    target_ref = load_topology(db, plan.tenant_id).resources[step["target_resource_id"]]["source_ref"]
    try:
        connector.validate_action(step["action_id"], step["target_kind"], step["params"])
    except ConnectorError as exc:
        row.status, row.error, row.finished_at = "failed", str(exc), utcnow()
        return False, str(exc)

    max_attempts = ctx.settings.action_max_attempts
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        row.attempts += 1
        try:
            res = await asyncio.wait_for(connector.execute_action(step["action_id"], target_ref, step["params"], key),
                                         timeout=ctx.settings.action_timeout_seconds)
        except TimeoutError:
            last_error, retry = f"Timed out after {ctx.settings.action_timeout_seconds}s", True
            row.status = "timed_out"
        except ConnectorError as exc:
            last_error, retry = str(exc), exc.retryable
        else:
            row.result = {"success": res.success, "message": res.message, "details": res.details, "idempotent_replay": res.idempotent_replay}
            if not res.success:
                row.status, row.error, row.finished_at = "failed", res.message, utcnow()
                audit.record(db, plan.tenant_id, actor.user_id, "action.execute", f"{step['action_id']}@{step['target_name']}", "failed",
                             {"plan": plan.id, "step": step["index"], "message": res.message, "attempts": row.attempts})
                return False, res.message
            v = await connector.verify(target_ref)
            row.verification = {"healthy": v.healthy, "checks": v.checks}
            row.status, row.finished_at = "succeeded", utcnow()
            audit.record(db, plan.tenant_id, actor.user_id, "action.execute", f"{step['action_id']}@{step['target_name']}", "success",
                         {"plan": plan.id, "step": step["index"], "message": res.message, "attempts": row.attempts,
                          "simulated": connector.is_simulated})
            return True, res.message
        if not retry or attempt == max_attempts:
            break
        await asyncio.sleep(min(0.05 * 2 ** (attempt - 1), 2.0))
    row.status = "timed_out" if row.status == "timed_out" else "failed"
    row.error, row.finished_at = last_error, utcnow()
    audit.record(db, plan.tenant_id, actor.user_id, "action.execute", f"{step['action_id']}@{step['target_name']}", "failed",
                 {"plan": plan.id, "step": step["index"], "error": last_error, "attempts": row.attempts})
    return False, last_error


async def validate(db: Session, ctx: AppContext, plan: RemediationPlan) -> ValidationResult:
    """Validation Agent: read the post-action state of every resource on the causal chain plus impacted business processes."""
    topo = load_topology(db, plan.tenant_id)
    checks: list[dict[str, Any]] = []
    for rid in plan.policy_decision.get("validation_targets", []):
        r = topo.resources[rid]
        if not r.get("connection_id") or not ctx.registry.has(r["connection_id"]):
            checks.append({"resource": r["name"], "check": "connector_available", "passed": False})
            continue
        try:
            v = await ctx.registry.get(r["connection_id"]).verify(r["source_ref"])
        except ConnectorError as exc:
            checks.append({"resource": r["name"], "check": "verify", "passed": False, "error": str(exc)})
            continue
        checks.extend({**c, "resource_id": rid} for c in v.checks)
    passed = bool(checks) and all(c["passed"] for c in checks)
    vr = ValidationResult(tenant_id=plan.tenant_id, plan_id=plan.id, incident_id=plan.incident_id, passed=passed, checks=checks)
    db.add(vr)
    db.flush()
    return vr
