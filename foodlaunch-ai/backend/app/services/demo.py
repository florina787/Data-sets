"""Guided demo: an ordered script of real actions performed as real demo accounts.

Every step calls the same services as the UI, runs to completion (tests, git,
deployments, HTTP traffic) and then compares the actual outcome with what the
step expects. Nothing advances on a timer. Pause takes effect between steps.
"""

from __future__ import annotations

from typing import Callable

from app import auth
from app.db import kv_get, kv_set, now_iso, rows
from app.errors import PlatformError
from app.graph import flows, jobs
from app.services import delivery, incidents, system
from app.tools import inventory_sim, traffic

STATE_KEY = "demo.state"
BRIEF = delivery.scenario()["brief"]


class StepFailed(Exception):
    pass


def _user(username: str) -> auth.User:
    _, user = auth.login(username, auth.DEMO_PASSWORD)
    return user


def _run_id() -> str:
    run_id = kv_get(STATE_KEY, {}).get("run_id")
    if not run_id:
        raise StepFailed("Guided demo run has not been created yet")
    return run_id


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise StepFailed(message)


def step_submit_brief() -> dict:
    maya = _user("maya.marketing")
    run_id = delivery.create_run(maya, BRIEF["title"], BRIEF["text"], "demo")
    state = kv_get(STATE_KEY, {})
    state["run_id"] = run_id
    kv_set(STATE_KEY, state)
    flow = flows.advance(run_id, "delivery")
    open_q = delivery.open_required_clarifications(run_id)
    _expect(flow["state"] == "waiting" and any(q["id"] == "Q-ONCE" for q in open_q),
            "Brief Analyst did not flag the once-per-customer ambiguity")
    return {"run_id": run_id, "open_clarifications": [q["id"] for q in open_q]}


def step_blocked_implementation() -> dict:
    eli = _user("eli.engineer")
    try:
        system.request_implementation(_run_id(), eli)
    except PlatformError as exc:
        _expect("open" in exc.details, "Expected a clarification gate rejection")
        return {"rejected": True, "reason": exc.message, "open": exc.details["open"]}
    raise StepFailed("Implementation was not blocked")


def step_decide() -> dict:
    maya = _user("maya.marketing")
    run_id = _run_id()
    count = delivery.apply_seeded_decisions(run_id, maya)
    flow = flows.advance(run_id, "delivery")
    _expect(flow["state"] == "waiting" and delivery.requirement_set(run_id)["status"] == "draft",
            "Requirements were not drafted")
    return {"decisions_recorded": count, "label": "Selected demo decisions (seeded)"}


def step_approve_requirements() -> dict:
    omar = _user("omar.product")
    run_id = _run_id()
    plan = delivery.approve_requirement_set(run_id, 1, omar)
    flow = flows.advance(run_id, "delivery")
    runs = rows("SELECT id, revision, status, exit_code FROM test_runs WHERE run_id = ? ORDER BY started_at",
                (run_id,))
    _expect(len(runs) >= 2 and runs[0]["status"] == "failed" and runs[-1]["status"] == "passed",
            f"Expected a failing then passing test run, got {[r['status'] for r in runs]}")
    _expect(flow["state"] == "waiting", "Release did not reach approval")
    return {"tests_hash": plan["tests_hash"][:12],
            "test_runs": [{k: r[k] for k in ("id", "status", "exit_code")} | {"revision": r["revision"][:10]}
                          for r in runs]}


def _pending_release(run_id: str) -> dict:
    release_id = flows.snapshot(run_id, "delivery" if not _incident_id() else "incident",
                                _incident_id())["values"].get("release_id")
    _expect(bool(release_id), "No release candidate found")
    return delivery.get_release(release_id)


def _incident_id() -> str | None:
    return kv_get(STATE_KEY, {}).get("incident_id")


def step_unauthorized_approval() -> dict:
    eli = _user("eli.engineer")
    release = _pending_release(_run_id())
    try:
        delivery.approve_release(release["id"], eli, release["manifest_hash"])
    except PlatformError as exc:
        _expect(exc.status_code == 403, "Expected HTTP 403")
        return {"rejected": True, "status_code": 403, "reason": exc.message}
    raise StepFailed("Engineer approval was not rejected")


def _approve_and_deploy() -> dict:
    rina = _user("rina.release")
    release = _pending_release(_run_id())
    delivery.approve_release(release["id"], rina, release["manifest_hash"])
    result = system.deploy_and_resume(release["id"], rina)
    _expect(result["deployment"]["status"] == "healthy", "Deployment health check failed")
    return {"release_id": release["id"], "revision": release["revision"][:10],
            "manifest_hash": release["manifest_hash"][:12], "pid": result["deployment"]["pid"],
            "flow": result["flow"]["state"]}


def step_approve_and_deploy() -> dict:
    return _approve_and_deploy()


def step_shopper() -> dict:
    report = traffic.generate(1, run_id=_run_id())
    _expect(report["outcomes"] == {"order_created": 1}, f"Expected an order, got {report['outcomes']}")
    return {"outcomes": report["outcomes"], "revision": report["revision"][:10]}


def step_inject_fault() -> dict:
    eli = _user("eli.engineer")
    auth.require(eli, "fault.inject")
    inventory_sim.set_fault(True, eli.username)
    report = traffic.generate(3, run_id=_run_id())
    _expect(all(k.startswith("checkout_5") for k in report["outcomes"]),
            f"Expected checkout failures, got {report['outcomes']}")
    return {"outcomes": report["outcomes"], "max_checkout_ms": report["max_checkout_ms"],
            "label": "Injected fault (demo)"}


def step_incident() -> dict:
    eli = _user("eli.engineer")
    result = system.open_incident_and_start(eli)
    _expect(result["incident"] is not None, result.get("message", "No incident opened"))
    state = kv_get(STATE_KEY, {})
    state["incident_id"] = result["incident"]["id"]
    kv_set(STATE_KEY, state)
    return {"incident_id": result["incident"]["id"], "checkout_5xx": result["stats"]["checkout_5xx"],
            "hypotheses": [h["id"] for h in result["incident"]["analysis"]["hypotheses"]]}


def step_rollback() -> dict:
    rina = _user("rina.release")
    deployment = delivery.rollback(rina, "Mitigate checkout incident")
    report = traffic.generate(1, run_id=_run_id())
    _expect(deployment["status"] == "healthy", "Rollback deployment unhealthy")
    _expect(report["outcomes"] == {"checkout_503": 1} and all(report["carts_preserved_after_failure"]),
            f"Expected graceful 503 on baseline under fault, got {report['outcomes']}")
    return {"rolled_back_to": deployment["release_id"], "revision": deployment["revision"][:10],
            "outcomes_under_fault": report["outcomes"], "max_checkout_ms": report["max_checkout_ms"]}


def step_approve_v2() -> dict:
    omar = _user("omar.product")
    run_id = _run_id()
    delivery.approve_requirement_set(run_id, 2, omar)
    flow = flows.advance(run_id, "incident", _incident_id())
    _expect(flow["state"] == "waiting", "Repair release did not reach approval")
    runs = rows(
        "SELECT id, status, purpose, revision FROM test_runs WHERE run_id = ? AND suite_version = 2"
        " ORDER BY started_at",
        (run_id,))
    _expect(runs[0]["status"] == "failed" and runs[-1]["status"] == "passed",
            "Expected the incident regression to fail on the released revision and pass on the repair")
    return {"test_runs": [{"id": r["id"], "status": r["status"], "purpose": r["purpose"],
                           "revision": r["revision"][:10]} for r in runs]}


def step_deploy_repair() -> dict:
    result = _approve_and_deploy()
    incident = incidents.get_incident(_incident_id())
    _expect(incident["status"] == "mitigated", f"Expected mitigated incident, got {incident['status']}")
    return result | {"incident_status": incident["status"]}


def step_clear_fault() -> dict:
    eli = _user("eli.engineer")
    inventory_sim.set_fault(False, eli.username)
    flow = flows.advance(_run_id(), "incident", _incident_id())
    incident = incidents.get_incident(_incident_id())
    _expect(incident["status"] == "resolved", f"Recovery not verified (incident {incident['status']})")
    return {"flow": flow["state"], "incident_status": incident["status"]}


STEPS: list[tuple[str, str, str, Callable[[], dict]]] = [
    ("brief", "Marketing submits the Ontario brief", "Maya (marketing)", step_submit_brief),
    ("gate", "Implementation is blocked until decisions are recorded", "Eli (engineer)", step_blocked_implementation),
    ("decide", "Record the seeded demo decisions", "Maya (marketing)", step_decide),
    ("requirements", "Approve requirements: faulty test fails, then repaired test passes", "Omar (product owner)",
     step_approve_requirements),
    ("unauthorized", "Engineer's release approval is rejected (403)", "Eli (engineer)", step_unauthorized_approval),
    ("deploy", "Approve the exact manifest and deploy locally", "Rina (release approver)", step_approve_and_deploy),
    ("shop", "Shopper buys 2 and gets 1 free on the live storefront", "Synthetic shopper", step_shopper),
    ("fault", "Inject inventory timeout (demo fault) and send traffic", "Eli (engineer)", step_inject_fault),
    ("incident", "Open incident from recorded telemetry", "Eli (engineer)", step_incident),
    ("rollback", "Roll back to last-known-good release", "Rina (release approver)", step_rollback),
    ("requirements2", "Approve REQ-9: regression fails on release, passes on repair", "Omar (product owner)",
     step_approve_v2),
    ("repair", "Approve and deploy the reviewed repair release", "Rina (release approver)", step_deploy_repair),
    ("recover", "Clear the fault and verify recovery", "Eli (engineer)", step_clear_fault),
]


def describe() -> dict:
    state = kv_get(STATE_KEY, {})
    results = state.get("results", {})
    return {
        "status": state.get("status", "idle"),
        "run_id": state.get("run_id"),
        "incident_id": state.get("incident_id"),
        "pause_requested": state.get("pause_requested", False),
        "job_id": state.get("job_id"),
        "steps": [{"id": sid, "title": title, "actor": actor, **results.get(sid, {"status": "pending"})}
                  for sid, title, actor, _ in STEPS],
    }


def _execute() -> dict:
    state = kv_get(STATE_KEY, {})
    results = state.setdefault("results", {})
    for sid, _title, _actor, fn in STEPS:
        if results.get(sid, {}).get("status") == "done":
            continue
        state = kv_get(STATE_KEY, {})
        if state.get("pause_requested"):
            state.update(status="paused", pause_requested=False)
            kv_set(STATE_KEY, state)
            return describe()
        results = state.setdefault("results", {})
        results[sid] = {"status": "running", "started_at": now_iso()}
        kv_set(STATE_KEY, state)
        try:
            outcome = fn()
        except (StepFailed, PlatformError) as exc:
            message = exc.message if isinstance(exc, PlatformError) else str(exc)
            state = kv_get(STATE_KEY, {})
            state["results"][sid] = {"status": "failed", "error": message, "finished_at": now_iso()}
            state["status"] = "failed"
            kv_set(STATE_KEY, state)
            return describe()
        state = kv_get(STATE_KEY, {})
        state["results"][sid] = {"status": "done", "result": outcome, "finished_at": now_iso()}
        kv_set(STATE_KEY, state)
    state = kv_get(STATE_KEY, {})
    state["status"] = "done"
    kv_set(STATE_KEY, state)
    return describe()


def run_or_continue() -> str:
    state = kv_get(STATE_KEY, {})
    if state.get("status") == "running":
        raise PlatformError("Guided demo is already running")
    if state.get("status") == "done":
        raise PlatformError("Guided demo finished. Reset Demo to run it again")
    if state.get("status") == "failed":
        failed = next((k for k, v in state.get("results", {}).items() if v.get("status") == "failed"), None)
        if failed:
            state["results"].pop(failed)
    state.update(status="running", pause_requested=False)
    kv_set(STATE_KEY, state)
    job_id = jobs.submit("guided_demo", state.get("run_id"), _execute, lock_key="guided-demo")
    state = kv_get(STATE_KEY, {})
    state["job_id"] = job_id
    kv_set(STATE_KEY, state)
    return job_id


def request_pause() -> dict:
    state = kv_get(STATE_KEY, {})
    if state.get("status") != "running":
        raise PlatformError("Guided demo is not running")
    state["pause_requested"] = True
    kv_set(STATE_KEY, state)
    return describe()
