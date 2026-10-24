"""Privacy redaction for screen frames.

Uses OCR word boxes: secret-looking tokens, and the values that follow labels
such as "Password:" on the same line, are painted over before the image
reaches the vision model. This is best-effort; it cannot see secrets OCR
misses, which the UI states plainly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from ..security.redact import redact_text
from .ocr import OCRResult, OCRWord

FILL = (44, 26, 18)  # espresso, so redactions are visibly deliberate
_LABEL = re.compile(r"^(password|passwd|pwd|passcode|pin|secret|token|api[_-]?key|apikey|otp|cvv|cvc|ssn)[:=]?$", re.I)
_MASKED = re.compile(r"^[•*●·]{4,}$")


@dataclass
class RedactionReport:
    boxes: int = 0
    kinds: list[str] = field(default_factory=list)
    sensitive: bool = False


def _secretish(word: str) -> str | None:
    _, kinds = redact_text(word)
    if kinds:
        return kinds[0]
    if len(word) >= 24 and re.fullmatch(r"[A-Za-z0-9_\-+/=]+", word) and re.search(r"\d", word) and re.search(r"[A-Za-z]", word):
        return "high_entropy_token"
    return None


def redact_image(img: Image.Image, ocr: OCRResult) -> tuple[Image.Image, str, RedactionReport]:
    report = RedactionReport()
    if not ocr.words:
        text, kinds = redact_text(ocr.text)
        report.kinds = kinds
        report.sensitive = bool(kinds)
        return img, text, report
    out = img.copy()
    draw = ImageDraw.Draw(out)
    by_line: dict[tuple, list[OCRWord]] = {}
    for w in ocr.words:
        by_line.setdefault(w.line_key, []).append(w)
    targets: list[OCRWord] = []
    for words in by_line.values():
        words.sort(key=lambda w: w.left)
        for i, w in enumerate(words):
            kind = _secretish(w.text)
            if kind:
                targets.append(w)
                report.kinds.append(kind)
            elif _MASKED.match(w.text):
                report.sensitive = True
            elif _LABEL.match(w.text.strip()):
                report.sensitive = True
                # Paint the value(s) to the right of the label on this line.
                for nxt in words[i + 1 : i + 4]:
                    if _LABEL.match(nxt.text):
                        break
                    targets.append(nxt)
                    report.kinds.append("labelled_secret")
    for w in targets:
        pad = 3
        draw.rectangle([w.left - pad, w.top - pad, w.left + w.width + pad, w.top + w.height + pad], fill=FILL)
    report.boxes = len(targets)
    report.sensitive = report.sensitive or bool(targets)
    hidden = {id(w) for w in targets}
    lines = []
    for _, words in sorted(by_line.items()):
        lines.append(" ".join("[REDACTED]" if id(w) in hidden else w.text for w in sorted(words, key=lambda w: w.left)))
    text, kinds = redact_text("\n".join(lines))
    report.kinds += kinds
    return out, text, report
