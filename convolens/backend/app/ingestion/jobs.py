"""Background jobs (imports, connected analysis, translation) with progress, cancellation and recovery.

Jobs run one at a time in a worker thread. On restart, jobs left running are marked ``interrupted``;
``resume`` re-queues them with the same parameters. Imports are idempotent (dataset id derives from file
hash + parameters, and partial datasets are removed before retrying).
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.ingestion import twcs
from app.ingestion.importer import run_import
from app.models.orm import Conversation, Dataset, ImportJob, Message, Translation
from app.retrieval.index import invalidate

log = logging.getLogger(__name__)
KAGGLE_DATASET = "thoughtvector/customer-support-on-twitter"


class JobManager:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="convolens-job")
        self._cancel: dict[str, threading.Event] = {}

    def recover(self) -> int:
        with session_scope() as s:
            rows = s.scalars(select(ImportJob).where(ImportJob.status.in_(["running", "queued"]))).all()
            for j in rows:
                j.status = "interrupted"
                j.error = "The server stopped while this job was running. Resume to restart it (imports are idempotent)."
            return len(rows)

    def submit(self, kind: str, params: dict) -> str:
        jid = "job_" + secrets.token_hex(8)
        with session_scope() as s:
            s.add(ImportJob(id=jid, kind=kind, params=params, status="queued", stage="queued"))
        self._cancel[jid] = threading.Event()
        self.pool.submit(self._run, jid)
        return jid

    def resume(self, jid: str) -> str:
        with session_scope() as s:
            j = s.get(ImportJob, jid)
            if j is None:
                raise KeyError(jid)
            if j.status not in ("interrupted", "failed", "cancelled"):
                raise ValueError(f"Job is {j.status}; only interrupted, failed or cancelled jobs can be resumed")
            j.status, j.stage, j.progress, j.error, j.cancel_requested = "queued", "queued (resumed)", 0.0, None, False
        self._cancel[jid] = threading.Event()
        self.pool.submit(self._run, jid)
        return jid

    def cancel(self, jid: str) -> None:
        with session_scope() as s:
            j = s.get(ImportJob, jid)
            if j is None:
                raise KeyError(jid)
            j.cancel_requested = True
        self._cancel.setdefault(jid, threading.Event()).set()

    def _progress(self, jid: str):
        last = [0.0]

        def fn(stage: str, p: float):
            now = time.time()
            if now - last[0] < 0.5 and p < 1.0:
                return
            last[0] = now
            with session_scope() as s:
                j = s.get(ImportJob, jid)
                j.stage, j.progress = stage[:80], round(float(p), 4)
        return fn

    def _run(self, jid: str) -> None:
        ev = self._cancel.setdefault(jid, threading.Event())
        with session_scope() as s:
            j = s.get(ImportJob, jid)
            if j.cancel_requested:
                j.status = "cancelled"
                return
            j.status = "running"
            kind, params = j.kind, dict(j.params)
        prog = self._progress(jid)
        try:
            if kind in ("upload", "local_path", "demo", "kaggle"):
                if kind == "kaggle":
                    prog("downloading from Kaggle (kagglehub)", 0.0)
                    import kagglehub
                    root = Path(kagglehub.dataset_download(params.get("dataset", KAGGLE_DATASET)))
                    found = sorted(root.rglob("twcs.csv")) or sorted(root.rglob("*.csv"))
                    if not found:
                        raise FileNotFoundError(f"No CSV found in the Kaggle download at {root}")
                    params["path"] = str(found[0])
                ds_id = run_import(Path(params["path"]), kind=params.get("dataset_kind", "kaggle_twcs"),
                                   name=params.get("name", "Customer Support on Twitter"),
                                   source_label=params.get("source_label", params["path"]),
                                   synthetic=bool(params.get("synthetic", False)), seed=params.get("seed"),
                                   sample_size=params.get("sample_size"), progress=prog, should_cancel=ev.is_set)
                invalidate(ds_id)
                result = {"dataset_id": ds_id}
            elif kind == "analysis":
                result = self._run_analysis(params, prog, ev)
            elif kind == "translation":
                result = self._run_translation(params, prog, ev)
            else:
                raise ValueError(f"Unknown job kind {kind}")
            with session_scope() as s:
                j = s.get(ImportJob, jid)
                j.status, j.progress, j.stage = "completed", 1.0, "completed"
                j.dataset_id = result.get("dataset_id")
                j.params = {**j.params, "result": result}
        except twcs.Cancelled:
            with session_scope() as s:
                j = s.get(ImportJob, jid)
                j.status, j.stage = "cancelled", "cancelled by user"
        except Exception as exc:
            log.exception("Job %s failed", jid)
            with session_scope() as s:
                j = s.get(ImportJob, jid)
                j.status, j.error = "failed", f"{type(exc).__name__}: {str(exc)[:1000]}"

    def _run_analysis(self, params: dict, prog, ev) -> dict:
        from app.analytics.extractor import activate_llm_analysis, analyze_conversation
        from app.llm.provider import get_chat_model
        ds_id = params["dataset_id"]
        model = get_chat_model()  # raises ModelNotConfigured -> job fails explicitly
        with session_scope() as s:
            ds = s.get(Dataset, ds_id)
            if ds is None or ds.synthetic:
                raise ValueError("Connected analysis runs only on imported (non-synthetic) datasets")
            ids = s.scalars(select(Conversation.id).where(Conversation.dataset_id == ds_id).order_by(Conversation.key)).all()
        limit = params.get("limit")
        ids = ids[:limit] if limit else ids
        ok = failed = 0
        for i, cid in enumerate(ids):
            if ev.is_set():
                raise twcs.Cancelled()
            a = analyze_conversation(cid, model=model)
            ok += a.status == "ok"
            failed += a.status != "ok"
            prog(f"analysed {i + 1}/{len(ids)} (failures {failed})", (i + 1) / max(len(ids), 1))
        result = {"dataset_id": ds_id, "analysed": ok, "failed": failed, "requested": len(ids)}
        if params.get("activate"):
            result["activation"] = activate_llm_analysis(ds_id)
        return result

    def _run_translation(self, params: dict, prog, ev) -> dict:
        from app.llm.provider import get_chat_model
        from app.multilingual.translation import translate
        model = get_chat_model()
        ds_id = params["dataset_id"]
        with session_scope() as s:
            msgs = s.execute(select(Message.id, Message.text).where(Message.dataset_id == ds_id,
                                                                     Message.language.notin_(["en", "unknown"]))).all()
        done = 0
        for i, (mid, text) in enumerate(msgs):
            if ev.is_set():
                raise twcs.Cancelled()
            r = translate(text, model=model)
            with session_scope() as s:
                s.add(Translation(message_id=mid, target_language="en", text=r["text"], method="llm", model_id=r["model_id"],
                                  prompt_version=r["prompt_version"], checks=r["checks"], needs_review=r["needs_review"]))
            done += 1
            prog(f"translated {i + 1}/{len(msgs)}", (i + 1) / max(len(msgs), 1))
        return {"dataset_id": ds_id, "translated": done}


_jobs: JobManager | None = None


def get_jobs() -> JobManager:
    global _jobs
    if _jobs is None:
        _jobs = JobManager()
    return _jobs
