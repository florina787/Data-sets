import base64
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from backend.screen.frames import ChangeDetector, FrameError, decode_image, encode_png_b64, resize_max
from backend.vision.ocr import run_ocr, tesseract_available
from backend.vision.redact import redact_image


def text_image(lines: list[str], size=(900, 300)) -> Image.Image:
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 26)
    except OSError:
        font = ImageFont.load_default(size=26)
    for i, line in enumerate(lines):
        d.text((20, 20 + i * 45), line, fill="black", font=font)
    return img


def test_decode_roundtrip_and_resize():
    img = Image.new("RGB", (3000, 1000), "white")
    b64 = encode_png_b64(img)
    out = decode_image("data:image/png;base64," + b64)
    assert out.size == (3000, 1000)
    assert resize_max(out, 1280).size == (1280, 426)


@pytest.mark.parametrize("bad", ["not-base64!!", base64.b64encode(b"GIF89a....").decode(), "data:text/html;base64,PGh0bWw+"])
def test_decode_rejects_bad_input(bad):
    with pytest.raises(FrameError):
        decode_image(bad)


def test_decode_rejects_gif():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="GIF")
    with pytest.raises(FrameError):
        decode_image(base64.b64encode(buf.getvalue()).decode())


def test_change_detector_skips_identical_frames():
    det = ChangeDetector()
    a = text_image(["def add(a, b):", "    return a + b"])
    assert det.changed(a)[0]
    assert not det.changed(a.copy())[0]
    b = text_image(["Traceback (most recent call last):", "KeyError: 'user'", "something else entirely"], size=(900, 300))
    b = b.transpose(Image.FLIP_TOP_BOTTOM)
    assert det.changed(b)[0]


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")
def test_ocr_reads_code():
    res = run_ocr(text_image(["KeyError: 'user_id'", "def load_user(data):"]))
    assert res.available and "KeyError" in res.text and "load_user" in res.text


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")
def test_redaction_paints_labelled_password():
    img = text_image(["Username: asha", "Password: Tr0ub4dor&3xyz", "Welcome back"])
    ocr = run_ocr(img)
    red, text, report = redact_image(img, ocr)
    assert report.sensitive and report.boxes >= 1
    assert "Tr0ub4dor" not in text and "asha" in text
    # The painted box must change the pixels where the password was.
    assert red.tobytes() != img.tobytes()
