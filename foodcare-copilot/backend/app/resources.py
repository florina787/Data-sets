"""Lightweight resource monitoring: CPU, RAM, this backend process and work queues.

One non-blocking psutil sample per request (no background sampler thread). CPU
percentages are measured since the previous call, so the first reading after start
is primed at import time.
"""

from __future__ import annotations

import os
import threading
import time

import psutil

_process = psutil.Process(os.getpid())
_lock = threading.Lock()
_MIN_WINDOW_S = 2.0  # several pollers (header, observability page) must not shrink the sample window
_last: dict = {"at": time.monotonic(), "cpu": 0.0, "proc": 0.0}
psutil.cpu_percent(interval=None)
_process.cpu_percent(interval=None)


def snapshot() -> dict:
    with _lock:
        if time.monotonic() - _last["at"] >= _MIN_WINDOW_S:
            _last.update(at=time.monotonic(), cpu=psutil.cpu_percent(interval=None),
                         proc=_process.cpu_percent(interval=None))
        cpu, proc_cpu = _last["cpu"], _last["proc"]
    vm = psutil.virtual_memory()
    rss = _process.memory_info().rss
    try:
        load = [round(v, 2) for v in os.getloadavg()]
    except (AttributeError, OSError):  # Windows
        load = None
    return {
        "measured_at": time.time(),
        "cpu_percent": round(cpu, 1), "cpu_count": psutil.cpu_count(logical=True), "load_avg": load,
        "ram_percent": round(vm.percent, 1), "ram_used_gb": round((vm.total - vm.available) / 1e9, 2),
        "ram_total_gb": round(vm.total / 1e9, 2),
        "process": {"pid": _process.pid, "cpu_percent": round(proc_cpu, 1), "rss_mb": round(rss / 1e6, 1),
                    "threads": _process.num_threads()},
        "source": "psutil (measured on the machine running the backend)",
    }
