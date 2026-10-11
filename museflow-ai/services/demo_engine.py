"""Per-session façade over the LangGraph workflow.

A ``DemoEngine`` owns everything mutable for one visitor: stores, audit log, checkpointer,
compiled graph and run registry. Streamlit keeps one engine per browser session.
"""
from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from time import perf_counter
from typing import Any

from langgraph.types import Command

from services import scenario_loader as fixtures
from services.audit_logger import AuditLogger
from services.memory_store import SessionStores
from services.tool_registry import ToolRegistry
from services.validation import MAX_REQUEST_CHARS, ValidationError, clean_text
from workflows.checkpoints import SessionCheckpointStore
from workflows.context import MuseContext
from workflows.graph import build_graph
from workflows.params import validate_params
from workflows.state import MuseState

DECISIONS = ("approved", "rejected", "cancelled")


@dataclass
class RunRecord:
    run_id: str
    scenario_id: str
    request: str
    params: dict[str, Any]
    created_at: str
    thread_id: str
    status: str = "running"
    values: dict[str, Any] = field(default_factory=dict)
    pending: dict[str, Any] | None = None
    wall_ms: float = 0.0
    invocations: int = 0

    @property
    def trace(self) -> list[dict[str, Any]]:
        return list(self.values.get("trace", []))

    @property
    def agent_events(self) -> list[dict[str, Any]]:
        return [e for e in self.trace if e.get("kind") == "agent"]

    @property
    def outputs(self) -> dict[str, Any]:
        return dict(self.values.get("outputs") or {})

    @property
    def final_response(self) -> str:
        return self.values.get("final_response", "")

    @property
    def title(self) -> str:
        sid = self.values.get("scenario_id") or self.scenario_id
        return fixtures.get_scenario(sid).title if sid else "Unsupported request"

    @property
    def emoji(self) -> str:
        sid = self.values.get("scenario_id") or self.scenario_id
        return fixtures.get_scenario(sid).emoji if sid else "❔"


class DemoEngine:
    def __init__(self, session_id: str | None = None, *, stores: SessionStores | None = None,
                 tools: ToolRegistry | None = None, today: date | None = None) -> None:
        self.session_id = session_id or uuid.uuid4().hex
        self.stores = stores or SessionStores()
        self.tools = tools or ToolRegistry()
        self.audit = AuditLogger()
        self.today = today or date.today()
        self.checkpoints = SessionCheckpointStore(self.session_id)
        self.graph = build_graph(self.checkpoints.saver)
        self.runs: dict[str, RunRecord] = {}
        self._counter = itertools.count(1)

    # -- helpers ------------------------------------------------------------------------
    def context(self) -> MuseContext:
        return MuseContext(session_id=self.session_id, stores=self.stores, tools=self.tools, audit=self.audit, today=self.today)

    def rebuild_graph(self) -> None:
        """Recompile the graph against the same checkpointer (proves resumes come from checkpoints)."""
        self.graph = build_graph(self.checkpoints.saver)

    def _invoke(self, run: RunRecord, payload: Any) -> RunRecord:
        config = self.checkpoints.config_for(run.run_id)
        t0 = perf_counter()
        self.graph.invoke(payload, config, context=self.context())
        run.wall_ms += (perf_counter() - t0) * 1000
        run.invocations += 1
        snapshot = self.graph.get_state(config)
        run.values = dict(snapshot.values)
        interrupts = [i for task in snapshot.tasks for i in task.interrupts]
        if interrupts:
            run.status, run.pending = "awaiting_approval", dict(interrupts[0].value)
        else:
            run.status, run.pending = run.values.get("status", "completed"), None
        return run

    # -- public API ---------------------------------------------------------------------
    def start(self, scenario_id: str | None = None, params: dict[str, Any] | None = None, request: str | None = None) -> RunRecord:
        if not scenario_id and not request:
            raise ValidationError("Provide a scenario or a request.")
        if request:
            request = clean_text(request, max_chars=MAX_REQUEST_CHARS, field="Request")
        if scenario_id:
            validate_params(scenario_id, params)  # fail fast in the UI; the graph validates again
        run_id = f"R{next(self._counter):03d}-{uuid.uuid4().hex[:6]}"
        run = RunRecord(
            run_id=run_id, scenario_id=scenario_id or "", request=request or "", params=dict(params or {}),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            thread_id=self.checkpoints.thread_id(run_id),
        )
        self.runs[run_id] = run
        initial: MuseState = {
            "run_id": run_id, "session_id": self.session_id, "scenario_id": scenario_id or "",
            "request": request or "", "params": dict(params or {}), "queue": [], "outputs": {}, "trace": [],
            "errors": [], "retries": {}, "status": "running", "action": None, "governance": None,
            "approval": None, "action_result": None,
        }
        return self._invoke(run, initial)

    def resume(self, run_id: str, decision: str, note: str = "") -> RunRecord:
        run = self.runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} does not belong to this session.")
        if decision not in DECISIONS:
            raise ValidationError(f"Decision must be one of {DECISIONS}.")
        if run.status != "awaiting_approval":
            raise ValidationError(f"Run {run_id} is not awaiting approval (status: {run.status}).")
        note = clean_text(note, max_chars=200, field="Note", allow_empty=True)
        return self._invoke(run, Command(resume={"decision": decision, "note": note}))

    def pending(self) -> list[RunRecord]:
        return [r for r in self.runs.values() if r.status == "awaiting_approval"]

    def history(self) -> list[RunRecord]:
        return sorted(self.runs.values(), key=lambda r: r.run_id, reverse=True)

    def latest(self, scenario_id: str | None = None) -> RunRecord | None:
        for run in self.history():
            if scenario_id is None or run.values.get("scenario_id", run.scenario_id) == scenario_id:
                return run
        return None
