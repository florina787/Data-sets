"""Background job execution for evaluations. HTTP requests only enqueue; clients poll run status."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from app.config import get_settings

_pool: ThreadPoolExecutor | None = None
_futures: dict[str, Future] = {}


def submit(run_id: str) -> None:
    from app.evaluation.runner import execute
    if get_settings().eval_execution == "inline":
        execute(run_id)
        return
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="eval")
    _futures[run_id] = _pool.submit(execute, run_id)


def wait(run_id: str, timeout: float = 60) -> None:
    f = _futures.get(run_id)
    if f is not None:
        f.result(timeout=timeout)


def recover() -> list[str]:
    from app.evaluation.runner import recover_jobs
    ids = recover_jobs()
    for rid in ids:
        submit(rid)
    return ids
