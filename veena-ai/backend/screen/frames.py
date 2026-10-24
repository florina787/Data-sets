"""Frame decoding, resizing and change detection for screen intelligence."""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

MAX_PIXELS = 40_000_000
MAX_BYTES = 25 * 2**20


class FrameError(ValueError):
    pass


def decode_image(b64: str) -> Image.Image:
    if b64.startswith("data:"):
        header, _, b64 = b64.partition(",")
        if not header.startswith(("data:image/png", "data:image/jpeg", "data:image/webp")):
            raise FrameError("unsupported image type")
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as e:  # noqa: BLE001
        raise FrameError("image is not valid base64") from e
    if len(raw) > MAX_BYTES:
        raise FrameError("image too large")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("PNG", "JPEG", "WEBP"):
            raise FrameError("unsupported image format")
        img.load()
    except FrameError:
        raise
    except Exception as e:  # noqa: BLE001 - includes decompression bombs
        raise FrameError(f"unreadable image: {e}") from e
    return img.convert("RGB")


def resize_max(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    scale = max_side / max(w, h)
    if scale >= 1:
        return img
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def encode_png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def dhash(img: Image.Image, size: int = 16) -> int:
    small = np.asarray(img.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class ChangeDetector:
    """Decides whether a sampled frame differs enough to be worth analysing."""

    def __init__(self, threshold_bits: int = 12):
        self.threshold = threshold_bits
        self.last: int | None = None

    def changed(self, img: Image.Image) -> tuple[bool, int]:
        h = dhash(img)
        if self.last is None:
            self.last = h
            return True, 256
        d = hamming(h, self.last)
        if d >= self.threshold:
            self.last = h
            return True, d
        return False, d

    def reset(self) -> None:
        self.last = None
