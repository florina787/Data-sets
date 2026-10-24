"""PCM helpers for the audio WebSocket protocol.

Wire format of one binary frame from the renderer:
    bytes 0..8   float64 little-endian, capture wall-clock time in ms (Date.now())
    bytes 8..    int16 little-endian mono PCM at 16 kHz
"""

from __future__ import annotations

import struct

import numpy as np

SAMPLE_RATE = 16000
HEADER = struct.Struct("<d")


class FrameError(ValueError):
    pass


def decode_frame(data: bytes) -> tuple[float, np.ndarray]:
    if len(data) < HEADER.size + 2:
        raise FrameError("frame too short")
    payload = data[HEADER.size :]
    if len(payload) % 2:
        raise FrameError("PCM payload must be whole int16 samples")
    if len(payload) > SAMPLE_RATE * 2 * 2:  # more than 2 s in one frame
        raise FrameError("frame too large")
    (ts,) = HEADER.unpack_from(data)
    pcm = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
    return ts, pcm


def encode_frame(ts_ms: float, audio: np.ndarray) -> bytes:
    pcm = np.clip(audio, -1.0, 1.0)
    return HEADER.pack(ts_ms) + (pcm * 32767).astype("<i2").tobytes()


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
