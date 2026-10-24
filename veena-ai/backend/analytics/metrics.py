"""Real instrumentation: every number shown in Analytics comes from here."""

from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import psutil

from ..memory.store import Store

# Metric names used across the app. Kept in one place so the UI and the
# recorders cannot drift apart.
ASR_PARTIAL = "asr.partial_ms"
ASR_FINAL = "asr.final_ms"
ASR_RTF = "asr.real_time_factor"
QUESTION_DETECT = "question.detect_ms"
RETRIEVAL = "rag.retrieval_ms"
FIRST_TOKEN = "llm.first_token_ms"  # noqa: S105 - metric name, not a secret
TOTAL_RESPONSE = "llm.total_ms"
TOKENS_PER_SEC = "llm.tokens_per_s"
SCREEN_ANALYSIS = "vision.analysis_ms"
OCR = "vision.ocr_ms"
AUDIO_DELAY = "audio.capture_delay_ms"
RETRIEVAL_TOP_SCORE = "rag.top_score"
PRACTICE_SCORE = "interview.score"


class Metrics:
    def __init__(self, store: Store, window: int = 500):
        self.store = store
        self._recent: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window))
        self._proc = psutil.Process()
        self._proc.cpu_percent(None)

    def record(self, name: str, value: float, unit: str = "ms", meta: dict | None = None, persist: bool = True) -> None:
        self._recent[name].append(value)
        if persist:
            self.store.record_metric(name, value, unit, meta)

    @contextmanager
    def timer(self, name: str, meta: dict | None = None) -> Iterator[dict[str, Any]]:
        box: dict[str, Any] = {}
        t0 = time.perf_counter()
        try:
            yield box
        finally:
            ms = (time.perf_counter() - t0) * 1000
            box["ms"] = ms
            self.record(name, ms, meta=meta)

    @staticmethod
    def _summary(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0}
        vs = sorted(values)
        p95 = vs[min(len(vs) - 1, int(round(0.95 * (len(vs) - 1))))]
        return {
            "count": len(vs),
            "mean": statistics.fmean(vs),
            "p50": statistics.median(vs),
            "p95": p95,
            "min": vs[0],
            "max": vs[-1],
        }

    def live(self) -> dict[str, Any]:
        return {name: self._summary(list(v)) for name, v in self._recent.items()}

    def history(self, days: int = 30) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)
        events = self.store.metric_events(since=since)
        grouped: dict[str, list[float]] = defaultdict(list)
        daily: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        per_model: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for e in events:
            grouped[e.name].append(e.value)
            daily[e.name][e.created_at.strftime("%Y-%m-%d")].append(e.value)
            if e.meta_json:
                model = json.loads(e.meta_json).get("model")
                if model:
                    per_model[model][e.name].append(e.value)
        return {
            "summary": {k: self._summary(v) for k, v in grouped.items()},
            "daily": {
                k: [{"day": d, "mean": statistics.fmean(v), "count": len(v)} for d, v in sorted(days_.items())]
                for k, days_ in daily.items()
            },
            "per_model": {m: {k: self._summary(v) for k, v in names.items()} for m, names in per_model.items()},
        }

    def resources(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        out: dict[str, Any] = {
            "system_cpu_percent": psutil.cpu_percent(None),
            "system_ram_used_gb": round((vm.total - vm.available) / 1e9, 2),
            "system_ram_total_gb": round(vm.total / 1e9, 2),
            "backend_rss_mb": round(self._proc.memory_info().rss / 1e6, 1),
            "backend_cpu_percent": self._proc.cpu_percent(None),
            "gpu": _gpu_usage(),
        }
        return out


def _gpu_usage() -> list[dict[str, Any]] | None:
    import shutil
    import subprocess

    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    gpus = []
    for line in out.strip().splitlines():
        name, util, used, total = [x.strip() for x in line.split(",")]
        gpus.append({"name": name, "util_percent": float(util), "mem_used_mb": float(used), "mem_total_mb": float(total)})
    return gpus
