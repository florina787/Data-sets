"""Event-driven streaming transcription.

    audio frames -> bounded queue -> VAD state machine -> ASR worker -> events

* Audio frames enter a bounded queue. If ASR falls behind, the oldest frames
  are dropped and counted (backpressure), so memory never grows without limit.
* VAD splits speech into utterances. While an utterance is open, partial
  transcripts are produced at most every ``partial_interval_ms``; a partial is
  skipped if the ASR worker is still busy (partials are best-effort).
* When ``silence_ms`` of silence follows speech, the utterance is finalised.
  Final jobs are never dropped. A final replaces every partial with the same
  utterance id, and late partials for a finalised utterance are discarded
  (transcript reconciliation).
"""

from __future__ import annotations

import asyncio
import itertools
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..audio.pcm import SAMPLE_RATE
from .vad import WINDOW

EventSink = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class StreamConfig:
    speech_threshold: float = 0.5
    silence_ms: int = 700
    min_speech_ms: int = 250
    partial_interval_ms: int = 900
    max_utterance_s: float = 20.0
    preroll_ms: int = 300
    queue_frames: int = 400  # ~ 400 * 64 ms = 25 s of audio at the renderer's frame size


@dataclass
class _Utterance:
    id: int
    start_sample: int
    chunks: list[np.ndarray] = field(default_factory=list)
    samples: int = 0
    voiced: int = 0  # samples in windows VAD marked as speech
    last_partial_at: float = 0.0
    finalised: bool = False

    def audio(self) -> np.ndarray:
        return np.concatenate(self.chunks) if self.chunks else np.zeros(0, dtype=np.float32)


class StreamingTranscriber:
    def __init__(self, asr, vad, sink: EventSink, config: StreamConfig | None = None, metrics=None):
        self.asr = asr
        self.vad = vad
        self.sink = sink
        self.cfg = config or StreamConfig()
        self.metrics = metrics
        self.frames: asyncio.Queue[tuple[float, np.ndarray] | None] = asyncio.Queue(maxsize=self.cfg.queue_frames)
        self.jobs: asyncio.Queue[tuple[str, _Utterance, np.ndarray] | None] = asyncio.Queue()
        self.dropped_frames = 0
        self.paused = False
        self._ids = itertools.count(1)
        self._pending = np.zeros(0, dtype=np.float32)
        self._preroll: deque[np.ndarray] = deque(maxlen=max(1, self.cfg.preroll_ms * SAMPLE_RATE // 1000 // WINDOW))
        self._utt: _Utterance | None = None
        self._silence_samples = 0
        self._total_samples = 0
        self._asr_busy = False
        self._last_final_text = ""
        self._finalised_ids: set[int] = set()
        self._tasks: list[asyncio.Task] = []

    # ---------- lifecycle ----------
    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._consume()), asyncio.create_task(self._asr_worker())]

    async def stop(self) -> None:
        """Flush the open utterance, finish pending finals, stop workers."""
        await self.frames.put(None)
        await self._tasks[0]
        await self.jobs.put(None)
        await self._tasks[1]

    def submit(self, ts_ms: float, pcm: np.ndarray) -> None:
        """Called by the transport for each frame. Never blocks."""
        if self.paused:
            return
        if self.frames.full():
            try:
                self.frames.get_nowait()
                self.dropped_frames += 1
            except asyncio.QueueEmpty:
                pass
        self.frames.put_nowait((ts_ms, pcm))

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    # ---------- VAD state machine ----------
    async def _consume(self) -> None:
        while True:
            item = await self.frames.get()
            if item is None:
                if self._utt is not None:
                    await self._finalise()
                return
            ts_ms, pcm = item
            if self.metrics is not None:
                self.metrics.record("audio.capture_delay_ms", time.time() * 1000 - ts_ms, persist=False)
            await self._process(pcm)

    async def _process(self, pcm: np.ndarray) -> None:
        buf = np.concatenate([self._pending, pcm])
        n = (buf.size // WINDOW) * WINDOW
        self._pending = buf[n:]
        if n == 0:
            return
        block = buf[:n]
        probs = self.vad.probabilities(block)
        for i, p in enumerate(probs):
            win = block[i * WINDOW : (i + 1) * WINDOW]
            self._total_samples += WINDOW
            speech = p >= self.cfg.speech_threshold
            if self._utt is None:
                if speech:
                    pre = list(self._preroll)
                    self._utt = _Utterance(id=next(self._ids), start_sample=self._total_samples - WINDOW * (len(pre) + 1))
                    self._utt.chunks.extend(pre)
                    self._utt.samples += WINDOW * len(pre)
                    self._utt.last_partial_at = time.perf_counter()
                    self._silence_samples = 0
                    await self.sink({"type": "vad", "speaking": True, "utterance_id": self._utt.id})
                else:
                    self._preroll.append(win)
                    continue
            utt = self._utt
            utt.chunks.append(win)
            utt.samples += WINDOW
            if speech:
                utt.voiced += WINDOW
            self._silence_samples = 0 if speech else self._silence_samples + WINDOW
            if self._silence_samples * 1000 / SAMPLE_RATE >= self.cfg.silence_ms:
                await self._finalise()
            elif utt.samples / SAMPLE_RATE >= self.cfg.max_utterance_s:
                await self._finalise()
        utt = self._utt
        if (
            utt is not None
            and not self._asr_busy
            and (time.perf_counter() - utt.last_partial_at) * 1000 >= self.cfg.partial_interval_ms
            and utt.samples * 1000 / SAMPLE_RATE >= 600
        ):
            utt.last_partial_at = time.perf_counter()
            await self.jobs.put(("partial", utt, utt.audio()))

    async def _finalise(self) -> None:
        utt, self._utt = self._utt, None
        self._preroll.clear()
        if utt is None:
            return
        utt.finalised = True
        await self.sink({"type": "vad", "speaking": False, "utterance_id": utt.id})
        speech_ms = utt.voiced * 1000 / SAMPLE_RATE
        self._silence_samples = 0
        if speech_ms < self.cfg.min_speech_ms:
            await self.sink({"type": "discard", "utterance_id": utt.id, "reason": "too short"})
            return
        await self.jobs.put(("final", utt, utt.audio()))

    # ---------- ASR worker ----------
    async def _asr_worker(self) -> None:
        while True:
            job = await self.jobs.get()
            if job is None:
                return
            kind, utt, audio = job
            if kind == "partial" and utt.finalised:
                continue  # its final is already queued behind this job
            self._asr_busy = True
            t0 = time.perf_counter()
            try:
                result = await asyncio.to_thread(
                    self.asr.transcribe,
                    audio,
                    beam_size=1 if kind == "partial" else 3,
                    use_vad=False,
                    initial_prompt=self._last_final_text[-200:] or None,
                )
            except Exception as e:  # noqa: BLE001 - keep the stream alive
                await self.sink({"type": "error", "where": "asr", "message": str(e)})
                continue
            finally:
                self._asr_busy = False
            ms = (time.perf_counter() - t0) * 1000
            audio_s = audio.size / SAMPLE_RATE
            if kind == "partial":
                # A final for this utterance may have been produced while the
                # partial was running; never let the stale partial overwrite it.
                if utt.id in self._finalised_ids:
                    continue
                if self.metrics is not None:
                    self.metrics.record("asr.partial_ms", ms, persist=False)
            else:
                self._finalised_ids.add(utt.id)
                if result.text:
                    self._last_final_text = result.text
                if self.metrics is not None:
                    self.metrics.record("asr.final_ms", ms)
                    if audio_s:
                        self.metrics.record("asr.real_time_factor", (ms / 1000) / audio_s, unit="ratio")
            start_s = utt.start_sample / SAMPLE_RATE
            await self.sink(
                {
                    "type": kind,
                    "utterance_id": utt.id,
                    "text": result.text,
                    "start_s": round(max(0.0, start_s), 2),
                    "end_s": round(max(0.0, start_s) + audio_s, 2),
                    "language": result.language,
                    "latency_ms": round(ms, 1),
                    "dropped_frames": self.dropped_frames,
                }
            )
