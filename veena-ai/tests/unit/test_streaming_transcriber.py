"""Streaming pipeline tests with a SIMULATED ASR and the energy VAD on synthetic audio."""

import asyncio
import time

import numpy as np

from backend.audio.pcm import FrameError, decode_frame, encode_frame
from backend.transcription.streaming import StreamConfig, StreamingTranscriber
from backend.transcription.vad import EnergyVAD, make_vad
from tests.conftest import FakeASR

SR = 16000


def tone(seconds, amp=0.3):
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * 300 * t)).astype(np.float32)


def silence(seconds):
    return np.zeros(int(seconds * SR), np.float32)


async def run(audio, asr, cfg=None, frame=1024, paced=False):
    events = []

    async def sink(ev):
        events.append(ev)

    tr = StreamingTranscriber(asr, EnergyVAD(), sink, cfg or StreamConfig(partial_interval_ms=200))
    tr.start()
    for i in range(0, audio.size, frame):
        tr.submit(time.time() * 1000, audio[i : i + frame])
        await asyncio.sleep(frame / SR if paced else 0)
    await tr.stop()
    return events, tr


def test_frame_codec_roundtrip():
    a = tone(0.1)
    ts, b = decode_frame(encode_frame(123.5, a))
    assert ts == 123.5 and np.allclose(a, b, atol=1e-4)
    for bad in (b"", b"\x00" * 9):
        try:
            decode_frame(bad)
        except FrameError:
            continue
        raise AssertionError("expected FrameError")


async def test_two_utterances_finalised():
    audio = np.concatenate([silence(0.5), tone(1.0), silence(1.0), tone(0.8), silence(1.0)])
    events, _ = await run(audio, FakeASR(texts=["first question?"]))
    finals = [e for e in events if e["type"] == "final"]
    assert [f["utterance_id"] for f in finals] == [1, 2]
    assert finals[0]["start_s"] < finals[1]["start_s"]
    vad = [e["speaking"] for e in events if e["type"] == "vad"]
    assert vad == [True, False, True, False]


async def test_short_blip_discarded():
    audio = np.concatenate([silence(0.3), tone(0.1), silence(1.0)])
    events, _ = await run(audio, FakeASR())
    assert not [e for e in events if e["type"] == "final"]
    assert any(e["type"] == "discard" for e in events)


async def test_partials_then_final_and_no_stale_partials():
    audio = np.concatenate([tone(3.0), silence(1.0)])
    events, _ = await run(audio, FakeASR(texts=["partial", "final text"]), paced=True)
    kinds = [e["type"] for e in events if e["type"] in ("partial", "final")]
    assert "partial" in kinds and kinds[-1] == "final"
    final_idx = kinds.index("final")
    assert "partial" not in kinds[final_idx + 1 :]  # nothing for utterance 1 after its final


async def test_backpressure_drops_oldest_frames():
    events = []

    async def sink(ev):
        events.append(ev)

    tr = StreamingTranscriber(FakeASR(), EnergyVAD(), sink, StreamConfig(queue_frames=5))
    # Submitting without letting the consumer run fills the bounded queue.
    for _ in range(20):
        tr.submit(0, tone(0.064))
    assert tr.frames.qsize() == 5 and tr.dropped_frames == 15


async def test_pause_ignores_audio():
    events = []

    async def sink(ev):
        events.append(ev)

    tr = StreamingTranscriber(FakeASR(), EnergyVAD(), sink)
    tr.pause()
    tr.submit(0, tone(1.0))
    assert tr.frames.qsize() == 0


def test_silero_vad_loads_and_separates_speech_from_silence():
    vad = make_vad()
    assert vad.name == "silero"
    probs = vad.probabilities(silence(1.024))
    assert probs.shape == (32,) and float(probs.max()) < 0.5
