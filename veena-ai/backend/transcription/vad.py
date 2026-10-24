"""Voice activity detection.

Silero VAD runs through the ONNX model that ships with faster-whisper, so it
needs no torch install. If onnxruntime is missing, an energy-based detector is
used instead and reported as such.
"""

from __future__ import annotations

import numpy as np

WINDOW = 512  # samples per Silero decision at 16 kHz (32 ms)


class SileroVAD:
    name = "silero"

    def __init__(self) -> None:
        from faster_whisper.vad import get_vad_model

        self._model = get_vad_model()
        self._tail = np.zeros(WINDOW, dtype=np.float32)

    def reset(self) -> None:
        self._tail = np.zeros(WINDOW, dtype=np.float32)

    def probabilities(self, block: np.ndarray) -> np.ndarray:
        """Speech probability per 512-sample window. len(block) % 512 == 0."""
        if block.size == 0:
            return np.zeros(0, dtype=np.float32)
        # Prepend the previous window so the model sees context across blocks,
        # then drop that window's output.
        audio = np.concatenate([self._tail, block.astype(np.float32)])
        out = self._model(audio, num_samples=WINDOW)
        self._tail = block[-WINDOW:].astype(np.float32)
        return np.asarray(out).reshape(-1)[1:]


class EnergyVAD:
    name = "energy"

    def __init__(self, threshold: float = 0.015) -> None:
        self.threshold = threshold

    def reset(self) -> None:
        pass

    def probabilities(self, block: np.ndarray) -> np.ndarray:
        frames = block.reshape(-1, WINDOW)
        energy = np.sqrt(np.mean(frames**2, axis=1))
        return np.clip(energy / (2 * self.threshold), 0.0, 1.0)


def make_vad():
    try:
        return SileroVAD()
    except Exception:  # noqa: BLE001 - fall back rather than lose audio
        return EnergyVAD()
