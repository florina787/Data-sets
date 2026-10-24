"""Typed workflow engine: an explicit DAG state machine.

LangGraph is not required. This engine provides the same observable semantics
used by the UI: steps with dependencies, waves of parallel execution, per-step
timeouts, retries, cancellation, failure injection, checkpointing of the full
CaseState after every wave, and an event log with real timestamps. Nothing in
the timeline is animated or invented: each event is written when it happens.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.core import audit, db
from app.core.config import get_settings
from app.core.security import Actor
from app.core.util import now_iso


class CaseState(BaseModel):
    session_id: str | None = None
    run_id: str
    query: str
    persona: str
    actor: dict[str, Any]
    classification: str = "INTERNAL"
    workflow: str
    intent: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_docs: list[dict[str, Any]] = Field(default_factory=list)
    task_results: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    audit_event_ids: list[str] = Field(default_factory=list)
    policy_decisions: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "queued"
    errors: list[dict[str, Any]] = Field(default_factory=list)
    timing: dict[str, Any] = Field(default_factory=dict)
    costs: dict[str, Any] = Field(default_factory=lambda: {"paid_api_calls": 0, "llm_tokens": 0, "currency": "USD", "incremental_spend": 0.0})
    simulation: bool = True
    workspace: list[dict[str, Any]] = Field(default_factory=list)
    answer: str = ""
    assumptions: list[str] = Field(default_factory=list)


@dataclass
class StepContext:
    run_id: str
    human: Actor
    options: dict[str, Any]
    attempt: int
    lock: threading.Lock

    def cancelled(self) -> bool:
        r = db.query_one("SELECT status FROM workflow_runs WHERE id = ?", (self.run_id,))
        return bool(r and r["status"] == "cancelled")


StepFn = Callable[[CaseState, StepContext], dict[str, Any]]


@dataclass
class Step:
    name: str
    agent: str
    fn: StepFn
    deps: list[str] = field(default_factory=list)
    retries: int = 1
    timeout_s: float | None = None
    stop_on_fail: bool = True
    description: str = ""


@dataclass
class Graph:
    name: str
    steps: list[Step]

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "nodes": [{"id": s.name, "agent": s.agent, "deps": s.deps, "description": s.description} for s in self.steps]}


class InjectedFailure(Exception):
    pass


class StepHalt(Exception):
    """Raised by a step to end the workflow early in a controlled way (e.g. policy deny)."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


_semaphore = threading.BoundedSemaphore(get_settings().max_concurrent_workflows)


def _event(run_id: str, step: str, agent: str, status: str, attempt: int = 0, duration_ms: float | None = None,
           summary: str = "", detail: dict[str, Any] | None = None) -> None:
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO workflow_events (run_id, step, agent, status, ts, attempt, duration_ms, summary, detail_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, step, agent, status, now_iso(), attempt, duration_ms, summary[:2000], db.jdump(detail or {})),
        )


def checkpoint(state: CaseState) -> None:
    with db.session(write=True) as conn:
        current = conn.execute("SELECT status FROM workflow_runs WHERE id = ?", (state.run_id,)).fetchone()
        status = "cancelled" if current and current["status"] == "cancelled" else state.status
        state.status = status
        conn.execute("UPDATE workflow_runs SET status = ?, updated = ?, state_json = ? WHERE id = ?",
                     (status, now_iso(), state.model_dump_json(), state.run_id))


def run_graph(graph: Graph, state: CaseState, human: Actor, options: dict[str, Any]) -> CaseState:
    with _semaphore:
        return _run(graph, state, human, options)


def _run(graph: Graph, state: CaseState, human: Actor, options: dict[str, Any]) -> CaseState:
    started = time.perf_counter()
    lock = threading.Lock()
    done: set[str] = set()
    failed: set[str] = set()
    pending = {s.name: s for s in graph.steps}
    state.status = "running"
    checkpoint(state)
    _event(state.run_id, "workflow", "Supervisor Agent", "started", summary=f"Graph '{graph.name}' with {len(graph.steps)} steps",
           detail=graph.describe())
    inject = options.get("inject_failure")
    inject_permanent = bool(options.get("inject_failure_permanent"))
    pacing = min(float(options.get("step_delay_ms", 0) or 0), 1500.0) / 1000.0
    step_timeout = get_settings().workflow_step_timeout_s
    halted: StepHalt | None = None

    def execute(step: Step) -> tuple[str, dict[str, Any] | None, str | None]:
        attempts = step.retries + 1
        for attempt in range(1, attempts + 1):
            ctx = StepContext(state.run_id, human, options, attempt, lock)
            if ctx.cancelled():
                _event(state.run_id, step.name, step.agent, "cancelled", attempt)
                return step.name, None, "cancelled"
            _event(state.run_id, step.name, step.agent, "running", attempt)
            t0 = time.perf_counter()
            try:
                if pacing:
                    time.sleep(pacing)  # optional demo pacing, disclosed in the UI
                if inject == step.name and (inject_permanent or attempt == 1):
                    raise InjectedFailure(f"Injected failure in '{step.name}' (attempt {attempt}) for demo")
                ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    fut = ex.submit(step.fn, state, ctx)
                    out = fut.result(timeout=step.timeout_s or step_timeout)
                finally:
                    ex.shutdown(wait=False, cancel_futures=True)
                ms = (time.perf_counter() - t0) * 1000
                _event(state.run_id, step.name, step.agent, "completed", attempt, ms, out.get("summary", ""),
                       {"evidence": out.get("evidence", []), "tools": out.get("tools", []), "output_keys": sorted(k for k in out if k not in ("summary",))})
                return step.name, out, None
            except StepHalt:
                raise
            except Exception as err:  # noqa: BLE001 - recorded and retried
                ms = (time.perf_counter() - t0) * 1000
                last = attempt == attempts
                _event(state.run_id, step.name, step.agent, "failed" if last else "retrying", attempt, ms, str(err),
                       {"error": type(err).__name__, "trace": traceback.format_exc(limit=2)[-800:]})
                if last:
                    return step.name, None, str(err)
                time.sleep(0.05 * (2 ** attempt))  # exponential backoff
        return step.name, None, "exhausted"

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        while pending and not halted:
            if db.query_one("SELECT status FROM workflow_runs WHERE id = ?", (state.run_id,))["status"] == "cancelled":
                break
            ready = [s for s in pending.values() if all(d in done for d in s.deps)]
            blocked = [s for s in pending.values() if any(d in failed for d in s.deps)]
            for s in blocked:
                _event(state.run_id, s.name, s.agent, "skipped", summary="Upstream step failed")
                failed.add(s.name)
                pending.pop(s.name)
            if not ready:
                if not blocked:
                    break
                continue
            for s in ready:
                pending.pop(s.name)
                _event(state.run_id, s.name, s.agent, "queued")
            futures = {pool.submit(execute, s): s for s in ready}
            for fut in concurrent.futures.as_completed(futures):
                s = futures[fut]
                try:
                    name, out, err = fut.result()
                except StepHalt as h:
                    halted = h
                    _event(state.run_id, s.name, s.agent, "halted", summary=str(h))
                    failed.add(s.name)
                    continue
                if err:
                    failed.add(name)
                    state.errors.append({"step": name, "error": err})
                    if err == "cancelled":
                        state.status = "cancelled"
                else:
                    done.add(name)
                    with lock:
                        state.task_results[name] = {k: v for k, v in (out or {}).items() if k not in ("evidence",)}
                        state.evidence.extend(out.get("evidence", []) if out else [])
            checkpoint(state)

    for s in list(pending.values()):
        _event(state.run_id, s.name, s.agent, "skipped", summary="Workflow ended before this step")

    current = db.query_one("SELECT status FROM workflow_runs WHERE id = ?", (state.run_id,))["status"]
    if current == "cancelled":
        state.status = "cancelled"
    elif halted:
        state.status = halted.status
    elif failed:
        state.status = "failed" if not done else "completed_with_errors"
    elif state.approvals and any(a["status"] == "pending" for a in state.approvals):
        state.status = "awaiting_approval"
    else:
        state.status = "completed"
    state.timing = {"total_ms": round((time.perf_counter() - started) * 1000, 1), "steps_completed": len(done),
                    "steps_failed": len(failed), "demo_pacing_ms": pacing * 1000}
    state.audit_event_ids.append(audit.append(human.id, "workflow.finished", f"{graph.name} -> {state.status}",
                                              {"run_id": state.run_id, "status": state.status, "timing": state.timing}))
    _event(state.run_id, "workflow", "Supervisor Agent", state.status, summary=f"Finished in {state.timing['total_ms']} ms")
    checkpoint(state)
    return state


def events(run_id: str, after: int = 0) -> list[dict[str, Any]]:
    out = db.query("SELECT * FROM workflow_events WHERE run_id = ? AND id > ? ORDER BY id", (run_id, after))
    for e in out:
        e["detail"] = db.jload(e.pop("detail_json"), {})
    return out
