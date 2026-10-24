"""Process-wide services, created once per backend launch."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from fastapi import Request

from ..agents.engine import Engine, ModelCatalog
from ..agents.interview import InterviewCoach
from ..agents.question_detection import QuestionDetector
from ..analytics.metrics import Metrics
from ..config import Settings
from ..llm.ollama import OllamaClient
from ..memory.store import Store
from ..rag.service import KnowledgeBase
from ..transcription.asr import WhisperTranscriber


@dataclass
class AppState:
    settings: Settings
    store: Store
    llm: OllamaClient
    metrics: Metrics
    catalog: ModelCatalog
    kb: KnowledgeBase
    engine: Engine
    coach: InterviewCoach
    detector: QuestionDetector
    transcriber_factory: type = WhisperTranscriber
    _asr: dict[tuple[str, str | None], WhisperTranscriber] = field(default_factory=dict)
    _asr_lock: threading.Lock = field(default_factory=threading.Lock)

    def asr(self, size: str, language: str | None) -> WhisperTranscriber:
        """One shared model per (size, language): loading Whisper is the slow part."""
        key = (size, language)
        with self._asr_lock:
            if key not in self._asr:
                # Keep at most one size resident to bound memory.
                self._asr = {k: v for k, v in self._asr.items() if k[0] == size}
                self._asr[key] = self.transcriber_factory(size, language)
            return self._asr[key]

    def asr_status(self) -> list[dict]:
        return [{"model": k[0], "language": k[1], "loaded": v.loaded, "device": v.device} for k, v in self._asr.items()]


def get_state(request: Request) -> AppState:
    return request.app.state.veena
