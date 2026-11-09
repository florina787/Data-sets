"""Local speech recognition with faster-whisper (CTranslate2)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v3", "distil-large-v3")


AUTO_LANGUAGE_MIN_P = 0.5


@dataclass
class ASRResult:
    text: str
    language: str | None
    language_probability: float | None
    segments: list[dict[str, Any]]


def _device() -> tuple[str, str]:
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:  # noqa: BLE001, S110 - no CUDA runtime: use the CPU
        pass
    return "cpu", "int8"


class WhisperTranscriber:
    """Thread-safe wrapper. Model weights download from Hugging Face on first
    load (free, no account) and are cached locally after that."""

    def __init__(self, model_size: str = "base", language: str | None = None, cpu_threads: int = 0):
        if model_size not in WHISPER_SIZES:
            raise ValueError(f"unknown whisper size {model_size!r}")
        self.model_size = model_size
        self.language = language
        self.fallback_language: str | None = "en"  # overridden per session from settings
        self.cpu_threads = cpu_threads
        self._model = None
        self._lock = threading.Lock()
        self.device, self.compute_type = _device()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                kw = {"device": self.device, "compute_type": self.compute_type, "cpu_threads": self.cpu_threads}
                try:
                    # Cached weights load without touching the network (offline use).
                    self._model = WhisperModel(self.model_size, local_files_only=True, **kw)
                except Exception:  # noqa: BLE001 - first run: download once
                    self._model = WhisperModel(self.model_size, **kw)

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        beam_size: int = 1,
        use_vad: bool = True,
        initial_prompt: str | None = None,
    ) -> ASRResult:
        self.load()
        result = self._run(audio, self.language, beam_size, use_vad, initial_prompt)
        # Language auto-detection is unreliable on short clips (measured: "What is
        # a hash map?" detected as Japanese at p=0.33). When it is unsure, use the
        # user's own language instead.
        fallback = self.fallback_language
        if self.language is None and fallback and result.language != fallback and result.language_probability < AUTO_LANGUAGE_MIN_P:
            result = self._run(audio, fallback, beam_size, use_vad, initial_prompt)
        return result

    def _run(self, audio: np.ndarray, language: str | None, beam_size: int, use_vad: bool, initial_prompt: str | None) -> ASRResult:
        with self._lock:
            segments, info = self._model.transcribe(
                audio.astype(np.float32),
                language=language,
                beam_size=beam_size,
                vad_filter=use_vad,
                condition_on_previous_text=False,
                initial_prompt=initial_prompt,
                without_timestamps=False,
            )
            segs = [{"start": s.start, "end": s.end, "text": s.text.strip(), "no_speech_prob": s.no_speech_prob} for s in segments]
        # Whisper hallucinates short phrases on near-silence; drop segments it
        # is itself confident contain no speech.
        kept = [s for s in segs if s["no_speech_prob"] < 0.6 and s["text"]]
        return ASRResult(
            text=" ".join(s["text"] for s in kept).strip(),
            language=info.language,
            language_probability=info.language_probability,
            segments=kept,
        )
