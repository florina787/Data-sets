"""Local OCR with Tesseract (free, offline)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from PIL import Image


@dataclass
class OCRWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    line_key: tuple[int, int, int]


@dataclass
class OCRResult:
    text: str
    words: list[OCRWord]
    available: bool
    error: str | None = None


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def run_ocr(img: Image.Image, lang: str = "eng") -> OCRResult:
    if not tesseract_available():
        return OCRResult("", [], available=False, error="Tesseract is not installed")
    import pytesseract

    try:
        data = pytesseract.image_to_data(img.convert("L"), lang=lang, output_type=pytesseract.Output.DICT, timeout=60)
    except Exception as e:  # noqa: BLE001
        return OCRResult("", [], available=True, error=str(e))
    words: list[OCRWord] = []
    for i, txt in enumerate(data["text"]):
        if not txt.strip():
            continue
        conf = float(data["conf"][i])
        if conf < 0:
            continue
        words.append(
            OCRWord(
                txt,
                data["left"][i],
                data["top"][i],
                data["width"][i],
                data["height"][i],
                conf,
                (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            )
        )
    lines: dict[tuple[int, int, int], list[str]] = {}
    for w in words:
        lines.setdefault(w.line_key, []).append(w.text)
    text = "\n".join(" ".join(ws) for _, ws in sorted(lines.items()))
    return OCRResult(text, words, available=True)
