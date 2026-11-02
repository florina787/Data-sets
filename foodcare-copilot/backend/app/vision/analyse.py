"""Per-potato measurements, visual indicators and threshold-based grading.

Size and shape are geometric measurements of the segmented region. The defect
indicators (dark area, green area) are colour heuristics, NOT a validated defect
classifier: dark patches can be rot, bruising, soil or shadow, and green can be
greening or lighting. Grades are a transparent rule over these numbers and the
configured thresholds; each grade lists the reasons behind it.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from app.config import FIXTURES
from app.vision.segment import Region, erode

GRADES = ("Good", "Moderate", "Not Good")


@lru_cache(maxsize=1)
def default_thresholds() -> dict:
    return json.loads((FIXTURES / "vision" / "thresholds.json").read_text())


def _hull_area(points: np.ndarray) -> float:
    """Convex hull (monotone chain) area of integer (x, y) points."""
    pts = sorted(set(map(tuple, points.tolist())))
    if len(pts) < 3:
        return float(len(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = np.array(lower[:-1] + upper[:-1], dtype=float)
    x, y = hull[:, 0], hull[:, 1]
    return abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2


def measure(region: Region, rgb: np.ndarray, scale: float, mm_per_px: float | None) -> dict:
    """``scale`` converts working-image pixels to original-image pixels."""
    x0, y0, x1, y1 = region.bbox
    ys, xs = np.nonzero(region.mask)
    cov = np.cov(np.vstack([xs, ys]).astype(float)) if len(xs) > 2 else np.eye(2)
    eig = np.sort(np.clip(np.linalg.eigvalsh(cov), 1e-6, None))[::-1]
    major, minor = 4 * np.sqrt(eig[0]), 4 * np.sqrt(eig[1])
    # hull from the row extremes of the region (pixel corners included so a filled square has solidity 1)
    present = np.flatnonzero(region.mask.any(axis=1))
    width = region.mask.shape[1]
    lo = region.mask[present].argmax(axis=1)
    hi = width - 1 - region.mask[present][:, ::-1].argmax(axis=1)
    corners = np.concatenate([np.column_stack([lo, present]), np.column_stack([hi + 1, present]),
                              np.column_stack([lo, present + 1]), np.column_stack([hi + 1, present + 1])])
    hull = _hull_area(corners)
    solidity = min(1.0, region.area / hull) if hull else 0.0

    # colour indicators on the interior (the outer rim is excluded: edge shadows and background bleed)
    inner = erode(region.mask, 2) if min(region.mask.shape) > 8 else region.mask
    pix = rgb[y0:y1 + 1, x0:x1 + 1][inner]
    if len(pix) == 0:
        pix = rgb[y0:y1 + 1, x0:x1 + 1][region.mask]
    r, g, b = pix[:, 0], pix[:, 1], pix[:, 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    median = float(np.median(lum))
    dark = lum < 0.55 * median
    green = (g > r * 1.08) & (g > b * 1.15) & (g - np.minimum(r, b) > 18)
    px_scale = scale * scale
    out = {
        "bbox": [round(v * scale) for v in (x0, y0, x1 + 1, y1 + 1)],
        "area_px": round(region.area * px_scale),
        "length_px": round(float(major) * scale, 1), "width_px": round(float(minor) * scale, 1),
        "elongation": round(float(major / minor), 2) if minor > 0 else None,
        "solidity": round(solidity, 3),
        "dark_pct": round(float(dark.mean()) * 100, 2), "green_pct": round(float(green.mean()) * 100, 2),
        "median_luminance": round(median, 1),
        "edge": region.touches_edge,
        "detection_score": round(float(np.clip(0.5 * min(1.0, region.contrast / 2) + 0.5 * solidity, 0, 1)), 3),
    }
    if mm_per_px:
        out["length_mm"] = round(out["length_px"] * mm_per_px, 1)
        out["width_mm"] = round(out["width_px"] * mm_per_px, 1)
    return out


def _level(value: float | None, good: float, moderate: float, higher_is_better: bool = False) -> int:
    if value is None:
        return 0
    if higher_is_better:
        return 0 if value >= good else 1 if value >= moderate else 2
    return 0 if value <= good else 1 if value <= moderate else 2


def grade(m: dict, t: dict, median_area: float) -> tuple[str | None, list[str]]:
    """Return (grade or None when not gradable, reasons)."""
    if m["edge"]:
        return None, ["Not graded: cut off by the image edge"]
    if m.get("possible_cluster"):
        return None, [f"Not graded: region looks like {m['possible_cluster']} touching potatoes"]
    checks: list[tuple[int, str]] = []
    if "length_mm" in m:
        lo, hi = t["min_length_mm"], t["max_length_mm"]
        lvl = 0 if lo <= m["length_mm"] <= hi else 1 if lo * 0.85 <= m["length_mm"] <= hi * 1.15 else 2
        checks.append((lvl, f"length {m['length_mm']} mm (spec {lo}-{hi} mm)"))
    else:
        rel = m["area_px"] / median_area if median_area else 1
        lvl = 0 if rel >= t["min_relative_area_good"] else 1 if rel >= t["min_relative_area_moderate"] else 2
        checks.append((lvl, f"size {rel:.0%} of the batch median (no scale given)"))
    checks.append((_level(m["elongation"], t["max_elongation_good"], t["max_elongation_moderate"]),
                   f"elongation {m['elongation']} (good ≤ {t['max_elongation_good']})"))
    checks.append((_level(m["solidity"], t["min_solidity_good"], t["min_solidity_moderate"], True),
                   f"shape regularity (solidity) {m['solidity']} (good ≥ {t['min_solidity_good']})"))
    checks.append((_level(m["dark_pct"], t["max_dark_pct_good"], t["max_dark_pct_moderate"]),
                   f"dark area {m['dark_pct']}% (good ≤ {t['max_dark_pct_good']}%) — possible rot, bruise or soil"))
    checks.append((_level(m["green_pct"], t["max_green_pct_good"], t["max_green_pct_moderate"]),
                   f"green area {m['green_pct']}% (good ≤ {t['max_green_pct_good']}%) — possible greening"))
    worst = max(level for level, _ in checks)
    reasons = [text for level, text in checks if level == worst and level > 0] or ["all checks within the Good limits"]
    return GRADES[worst], reasons
