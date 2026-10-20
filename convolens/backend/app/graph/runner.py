"""Executes Flo graph runs, streams real execution events and records each run."""
from __future__ import annotations

import logging
import secrets
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from langgraph.types import Command
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.graph.builder import build_graph, sqlite_checkpointer
from app.llm.provider import provider_status
from app.models.orm import Dataset, Run
from app.models.schemas import Filters
from app.observability import tracing

log = logging.getLogger(__name__)


class RunError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class FloRunner:
    def __init__(self, checkpoint_path=None):
        s = get_settings()
        self.saver = sqlite_checkpointer(checkpoint_path or s.checkpoint_path)
        self.graph = build_graph(self.saver)
        self._cancel: dict[str, threading.Event] = {}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def thread_id(session_id: str, request_id: str) -> str:
        return f"{session_id}/{request_id}"

    def _config(self, session_id: str, request_id: str, ls_run_id: str, meta: dict) -> dict:
        ev = self._cancel.setdefault(request_id, threading.Event())
        cfg = {"configurable": {"thread_id": self.thread_id(session_id, request_id), "cancel_check": ev.is_set},
               "recursion_limit": 40, "run_name": "flo", "run_id": uuid.UUID(ls_run_id),
               "metadata": {"request_id": request_id, "session_id": session_id, **meta}, "tags": ["convolens", meta.get("mode", "")]}
        tr = tracing.tracer()
        if tr is not None:
            cfg["callbacks"] = [tr]
        return cfg

    def cancel(self, session_id: str, request_id: str) -> bool:
        with session_scope() as db:
            run = db.get(Run, request_id)
            if run is None or run.session_id != session_id:
                raise RunError(404, "Run not found for this session")
        self._cancel.setdefault(request_id, threading.Event()).set()
        return True

    def _history(self, session_id: str) -> list[dict]:
        with session_scope() as db:
            runs = db.scalars(select(Run).where(Run.session_id == session_id, Run.status.in_(["completed", "awaiting_approval"]))
                              .order_by(Run.started_at.desc()).limit(3)).all()
            hist = []
            for r in reversed(runs):
                hist.append({"role": "user", "content": r.question})
                hist.append({"role": "assistant", "content": (r.response or {}).get("finding") or ""})
            return hist

    def _stream(self, inp, cfg: dict, request_id: str) -> Iterator[dict]:
        t0 = time.perf_counter()
        nodes: list[dict] = []
        tools: list[dict] = []
        final_state = None
        try:
            for mode, chunk in self.graph.stream(inp, cfg, stream_mode=["custom", "updates"]):
                if mode == "custom":
                    if chunk.get("type") == "node":
                        nodes.append({"node": chunk["node"], "status": chunk["status"], "t_ms": round((time.perf_counter() - t0) * 1000)})
                    if chunk.get("type") == "tool" and chunk.get("status") not in ("running",):
                        tools.append({k: chunk.get(k) for k in ("step", "tool", "purpose", "status", "summary", "filters", "evidence_ids")})
                    yield chunk
                elif mode == "updates" and "__interrupt__" in chunk:
                    intr = chunk["__interrupt__"]
                    val = intr[0].value if intr else {}
                    nodes.append({"node": "request_action_approval", "status": "awaiting_approval", "t_ms": round((time.perf_counter() - t0) * 1000)})
                    yield {"type": "node", "node": "request_action_approval", "status": "awaiting_approval"}
                    yield {**val, "type": "approval_required"}
            final_state = self.graph.get_state(cfg).values
        except Exception as exc:  # graph-level failure (should be rare: nodes convert errors to state)
            log.exception("Graph failure")
            yield {"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:300]}"}
            self._finish(request_id, "failed", nodes, tools, None, t0, error=str(exc))
            return
        snapshot = self.graph.get_state(cfg)
        waiting = bool(snapshot.next) and any(t.interrupts for t in snapshot.tasks)
        if waiting and not any(n["status"] == "awaiting_approval" for n in nodes):
            val = next(i.value for t in snapshot.tasks for i in t.interrupts)
            nodes.append({"node": "request_action_approval", "status": "awaiting_approval", "t_ms": round((time.perf_counter() - t0) * 1000)})
            yield {"type": "node", "node": "request_action_approval", "status": "awaiting_approval"}
            yield {**val, "type": "approval_required"}
        resp = (final_state or {}).get("response")
        status = "awaiting_approval" if waiting else {"cancelled": "cancelled", "error": "failed"}.get((resp or {}).get("kind"), "completed")
        self._finish(request_id, status, nodes, tools, final_state, t0)
        yield {"type": "answer", "request_id": request_id, "status": status, "response": resp,
               "visited": (final_state or {}).get("visited", []),
               "usage": {"input_tokens": (final_state or {}).get("tokens_in", 0), "output_tokens": (final_state or {}).get("tokens_out", 0)}}
        tracing.flush()

    def _finish(self, request_id: str, status: str, nodes, tools, st, t0, error: str | None = None):
        with session_scope() as db:
            run = db.get(Run, request_id)
            if run is None:
                return
            run.status = status
            run.nodes = (run.nodes or []) + nodes
            run.tool_calls = (run.tool_calls or []) + tools
            if st:
                run.question_type = st.get("question_type")
                run.response = st.get("response")
                run.evidence_ids = st.get("evidence_ids", [])
                run.input_tokens = st.get("tokens_in", 0)
                run.output_tokens = st.get("tokens_out", 0)
                run.prompt_versions = st.get("prompt_versions", {})
                errs = [e for e in st.get("errors", []) if e["type"] not in ("note", "policy")]
                run.error = "; ".join(e["message"] for e in errs)[:2000] or None
            if error:
                run.error = error[:2000]
            run.latency_ms = (run.latency_ms or 0) + round((time.perf_counter() - t0) * 1000)
            run.ended_at = datetime.now(timezone.utc)
        self._cancel.pop(request_id, None) if status != "awaiting_approval" else None

    # ------------------------------------------------------------------ public API
    def start(self, *, session_id: str, question: str, dataset_id: str, mode: str, page: str | None,
              filters: dict | None) -> Iterator[dict]:
        if mode not in ("demo", "connected"):
            raise RunError(400, "mode must be 'demo' or 'connected'")
        f = Filters(**(filters or {}))
        with session_scope() as db:
            ds = db.get(Dataset, dataset_id)
            if ds is None or ds.status != "ready":
                raise RunError(404, "Dataset not found or not ready")
            if mode == "demo" and not ds.synthetic:
                raise RunError(409, "Demonstration mode only analyses synthetic demonstration datasets. Switch to Connected analysis.")
            if mode == "connected" and ds.synthetic:
                raise RunError(409, "Connected analysis requires an imported (non-synthetic) dataset. Import Kaggle data or switch to Demonstration.")
        request_id = "req_" + secrets.token_hex(10)
        ls_run_id = str(uuid.uuid4())
        model_id = provider_status()["model_id"] if mode == "connected" else None
        with session_scope() as db:
            db.add(Run(id=request_id, session_id=session_id, dataset_id=dataset_id, mode=mode, question=question[:2000],
                       model_id=model_id, langsmith_run_id=ls_run_id if tracing.status()["configured"] else None))
        hist = self._history(session_id)
        inp = {"request_id": request_id, "session_id": session_id, "dataset_id": dataset_id, "mode": mode, "page": page or "",
               "active_filters": f.model_dump(mode="json", exclude_defaults=True), "question": question.strip()[:2000],
               "messages": hist + [{"role": "user", "content": question[:2000]}], "started_at": time.time(),
               "model_id": model_id, "visited": [], "tokens_in": 0, "tokens_out": 0}
        cfg = self._config(session_id, request_id, ls_run_id, {"dataset_id": dataset_id, "mode": mode, "page": page or ""})
        yield {"type": "run_started", "request_id": request_id, "mode": mode, "dataset_id": dataset_id,
               "method": "rules (demonstration)" if mode == "demo" else f"model {model_id}",
               "tracing": tracing.status()["configured"]}
        yield from self._stream(inp, cfg, request_id)

    def resume(self, *, session_id: str, request_id: str, decision: dict) -> Iterator[dict]:
        with session_scope() as db:
            run = db.get(Run, request_id)
            if run is None or run.session_id != session_id:
                raise RunError(404, "Run not found for this session")
            ls_id = run.langsmith_run_id or str(uuid.uuid4())
            mode, dsid = run.mode, run.dataset_id
        cfg = self._config(session_id, request_id, str(uuid.uuid4()), {"dataset_id": dsid, "mode": mode, "resume_of": ls_id})
        snap = self.graph.get_state(cfg)
        if not (snap.next and any(t.interrupts for t in snap.tasks)):
            rec = (snap.values or {}).get("action_record_id")
            raise RunError(409, f"No approval is pending for this run" + (f"; action #{rec} was already saved." if rec else "."))
        with session_scope() as db:
            db.get(Run, request_id).status = "running"
        yield {"type": "run_resumed", "request_id": request_id}
        yield from self._stream(Command(resume=decision), cfg, request_id)

    def pending_state(self, session_id: str, request_id: str) -> dict:
        cfg = {"configurable": {"thread_id": self.thread_id(session_id, request_id)}}
        snap = self.graph.get_state(cfg)
        return {"next": list(snap.next), "values": snap.values}


_runner: FloRunner | None = None


def get_runner() -> FloRunner:
    global _runner
    if _runner is None:
        _runner = FloRunner()
    return _runner


def reset_runner(path=None) -> FloRunner:
    global _runner
    _runner = FloRunner(path)
    return _runner
