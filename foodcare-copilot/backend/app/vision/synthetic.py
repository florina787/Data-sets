"""Rendered test images with known ground truth (labelled SYNTHETIC everywhere they are used).

They test the pipeline end to end and give exact precision/recall on drawn shapes.
They are not photographs: a good score here says nothing about accuracy on real
potatoes, which needs labelled real images (see ``evaluate.py``).
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

KINDS = {
    # kind: (axis ratio range, scale, defect, defect area fraction, expected grade)
    "good": ((1.15, 1.5), 1.0, None, 0.0, "Good"),
    "mild_dark": ((1.15, 1.4), 1.0, "dark", 0.025, "Moderate"),
    "dark": ((1.15, 1.4), 1.0, "dark", 0.09, "Not Good"),
    "green": ((1.15, 1.4), 1.0, "green", 0.09, "Not Good"),
    "elongated": ((2.8, 3.0), 1.0, None, 0.0, "Not Good"),
    "small": ((1.15, 1.4), 0.5, None, 0.0, "Not Good"),
}


def _ellipse(xx, yy, cx, cy, a, b, angle, wobble=None):
    c, s = np.cos(angle), np.sin(angle)
    dx, dy = xx - cx, yy - cy
    u, v = (dx * c + dy * s) / a, (-dx * s + dy * c) / b
    r = u * u + v * v
    if wobble is not None:
        theta = np.arctan2(v, u)
        r = r / (1 + wobble[0] * np.sin(3 * theta + wobble[1])) ** 2
    return r <= 1.0


def render(seed: int = 7, kinds: list[str] | None = None, size: tuple[int, int] = (960, 720),
           touching: bool = False) -> tuple[bytes, list[dict]]:
    rng = np.random.default_rng(seed)
    kinds = kinds or ["good"] * 6 + ["mild_dark", "dark", "green", "elongated", "small", "good"]
    w, h = size
    img = np.empty((h, w, 3), dtype=float)
    img[:] = (58, 64, 76)
    img += rng.normal(0, 4, img.shape)
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    cols = 4
    rows = -(-len(kinds) // cols)
    cell_w, cell_h = w / cols, h / rows
    base = min(cell_w, cell_h) * 0.30
    truth = []
    for i, kind in enumerate(kinds):
        ratio_range, scale, defect, defect_frac, expected = KINDS[kind]
        ratio = rng.uniform(*ratio_range)
        b = base * scale * rng.uniform(0.9, 1.05)
        a = b * ratio
        if a > min(cell_w, cell_h) * 0.46:  # keep elongated potatoes inside their cell
            a = min(cell_w, cell_h) * 0.46
            b = a / ratio
        col, row = i % cols, i // cols
        cx = (col + 0.5) * cell_w + rng.uniform(-0.06, 0.06) * cell_w
        cy = (row + 0.5) * cell_h + rng.uniform(-0.06, 0.06) * cell_h
        angle = rng.uniform(0, np.pi)
        if touching and i in (0, 1):  # first two potatoes lie side by side and overlap slightly
            angle = 0.0
            if i == 1:
                cx = truth[0]["center"][0] + 0.85 * (truth[0]["axes"][0] + a)
                cy = truth[0]["center"][1]
        mask = _ellipse(xx, yy, cx, cy, a, b, angle, (0.03, rng.uniform(0, 6)))
        colour = np.array([196, 156, 98]) * rng.uniform(0.92, 1.05)
        shade = 1 - 0.18 * np.clip(((xx - cx) ** 2 + (yy - cy) ** 2) / (a * a), 0, 1)
        tex = rng.normal(0, 6, (h, w))
        for ch in range(3):
            img[..., ch] = np.where(mask, colour[ch] * shade + tex, img[..., ch])
        if defect:
            area = mask.sum() * defect_frac
            rb = np.sqrt(area / np.pi / 1.3)
            ox, oy = rng.uniform(-0.3, 0.3) * a, rng.uniform(-0.25, 0.25) * b
            spot = _ellipse(xx, yy, cx + ox, cy + oy, rb * 1.3, rb, rng.uniform(0, np.pi)) & mask
            tint = (70, 50, 35) if defect == "dark" else (120, 160, 72)
            for ch in range(3):
                img[..., ch] = np.where(spot, tint[ch] + tex * 0.5, img[..., ch])
        ys, xs = np.nonzero(mask)
        truth.append({"kind": kind, "grade": expected, "center": (cx, cy), "axes": (a, b),
                      "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]})
    buf = io.BytesIO()
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(buf, format="PNG")
    return buf.getvalue(), truth
