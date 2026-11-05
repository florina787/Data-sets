"""Background worker for long-running analytics jobs (DB-backed queue; run as `python -m backend.worker`).
Jobs execute with the requesting principal's identity re-resolved from the directory, so authorization is re-checked."""
from __future__ import annotations

import json
import logging
import threading

from datetime import datetime, timezone

from sqlalchemy import select

from backend import runtime as R
from backend.db import models as m
from backend.db.session import session_scope
from observability.telemetry import QUEUE_DEPTH

log = logging.getLogger("flo.worker")
PERMS = {"scenario_compare": "scenarios:run", "scenario_sensitivity": "scenarios:run", "data_quality": "aiops:read", "portfolio_metrics": "investment:read"}


def _run(kind: str, adapters, params: dict) -> dict:
    from analytics import data_quality, service
    from scenarios import engine as E
    if kind == "scenario_compare":
        return E.compare(adapters)
    if kind == "scenario_sensitivity":
        return E.sensitivity(adapters)
    if kind == "data_quality":
        return data_quality.run_checks(adapters)
    if kind == "portfolio_metrics":
        return service.portfolio_list(adapters)
    raise ValueError(kind)


def process_one() -> bool:
    with session_scope() as s:
        QUEUE_DEPTH.set(s.query(m.Job).filter(m.Job.status == "queued").count())
        j = s.scalar(select(m.Job).where(m.Job.status == "queued").order_by(m.Job.created_at).limit(1))
        if j is None:
            return False
        j.status, j.started_at = "running", datetime.now(timezone.utc).replace(tzinfo=None)
        jid = j.id
    with session_scope() as s:
        j = s.get(m.Job, jid)
        st = R.store(s)
        try:
            p = R.principal_for(st, j.requested_by)
            if not R.engine().authorize(p, PERMS[j.kind]).allowed:
                raise PermissionError("requester no longer authorized")
            from integrations.mock.adapters import Adapters
            j.result = json.loads(json.dumps(_run(j.kind, Adapters(st, p.tenant_id), j.params), default=str))
            j.status = "succeeded"
        except Exception as e:  # noqa: BLE001
            j.status, j.error = "failed", f"{e.__class__.__name__}: {e}"
        j.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return True


def loop(stop: threading.Event | None = None, idle_s: float = 0.5) -> None:
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            if not process_one():
                stop.wait(idle_s)
        except Exception:  # noqa: BLE001
            log.exception("worker iteration failed")
            stop.wait(2)


def start_in_process() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), daemon=True, name="flo-worker").start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("FLO worker started")
    loop()

