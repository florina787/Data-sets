"""Classical foreground segmentation for potatoes on a plain, contrasting background.

This is image processing, not a trained model: the background colour is estimated
from the image border, pixels far from it (Otsu threshold on colour distance) are
foreground, small gaps are closed, holes are filled and connected regions become
candidate potatoes. It works on photos with one plain background colour and
separated potatoes. Touching potatoes merge into one region (flagged as a possible
cluster); busy backgrounds, conveyors and heavy shadows are not supported. A
trained detector can replace it through the ``Detector`` interface in
``service.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Region:
    label: int
    area: int
    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1 (inclusive) in working-image pixels
    touches_edge: bool
    mask: np.ndarray  # bool, cropped to bbox
    contrast: float  # mean colour distance from background / threshold


def otsu(values: np.ndarray) -> float:
    hist, edges = np.histogram(values, bins=256, range=(0.0, float(values.max()) + 1e-6))
    centers = (edges[:-1] + edges[1:]) / 2
    weight = np.cumsum(hist)
    total = weight[-1]
    mean = np.cumsum(hist * centers)
    w0, w1 = weight[:-1], total - weight[:-1]
    valid = (w0 > 0) & (w1 > 0)
    between = np.zeros_like(w0, dtype=float)
    m0 = mean[:-1][valid] / w0[valid]
    m1 = (mean[-1] - mean[:-1][valid]) / w1[valid]
    between[valid] = w0[valid] * w1[valid] * (m0 - m1) ** 2
    return float(centers[int(np.argmax(between))])


def _shift_or(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    for _ in range(iterations):
        mask = _shift_or(mask)
    return mask


def erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    for _ in range(iterations):
        mask = ~_shift_or(~mask)
    return mask


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """8-connected labelling over row runs with union-find (fast without scipy)."""
    h, w = mask.shape
    padded = np.zeros((h, w + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    diff = np.diff(padded, axis=1)
    run_rows, run_starts, run_ends = [], [], []
    for y in range(h):
        starts = np.flatnonzero(diff[y] == 1)
        ends = np.flatnonzero(diff[y] == -1) - 1
        run_rows.extend([y] * len(starts))
        run_starts.extend(starts.tolist())
        run_ends.extend(ends.tolist())
    n = len(run_starts)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    prev_lo = prev_hi = 0  # run index range of the previous row
    i = 0
    while i < n:
        y = run_rows[i]
        j = i
        while j < n and run_rows[j] == y:
            j += 1
        if i > 0 and run_rows[i - 1] == y - 1:
            k = prev_lo
            for r in range(i, j):
                while k < prev_hi and run_ends[k] < run_starts[r] - 1:
                    k += 1
                m = k
                while m < prev_hi and run_starts[m] <= run_ends[r] + 1:
                    a, b = find(r), find(m)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
                    m += 1
        prev_lo, prev_hi = i, j
        i = j
    labels = np.zeros((h, w), dtype=np.int32)
    ids: dict[int, int] = {}
    for r in range(n):
        root = find(r)
        lab = ids.setdefault(root, len(ids) + 1)
        labels[run_rows[r], run_starts[r]:run_ends[r] + 1] = lab
    return labels, len(ids)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    labels, count = label_components(~mask)
    if count == 0:
        return mask
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    holes = ~np.isin(labels, border) & (labels > 0)
    return mask | holes


def segment(rgb: np.ndarray, min_area_frac: float = 0.0008) -> tuple[list[Region], dict]:
    """Return candidate regions and diagnostics for an RGB float array (H, W, 3) in 0..255."""
    h, w, _ = rgb.shape
    strip = max(2, int(min(h, w) * 0.03))
    border = np.concatenate([rgb[:strip].reshape(-1, 3), rgb[-strip:].reshape(-1, 3),
                             rgb[:, :strip].reshape(-1, 3), rgb[:, -strip:].reshape(-1, 3)])
    background = np.median(border, axis=0)
    distance = np.sqrt(((rgb - background) ** 2).sum(axis=2))
    threshold = max(otsu(distance), 30.0)
    mask = distance > threshold
    mask = erode(dilate(mask, 2), 2)  # close small gaps
    mask = dilate(erode(mask, 1), 1)  # remove speckle
    mask = fill_holes(mask)
    labels, count = label_components(mask)
    min_area = max(30, int(min_area_frac * h * w))
    regions = []
    for lab in range(1, count + 1):
        ys, xs = np.nonzero(labels == lab)
        if len(ys) < min_area:
            continue
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        sub = labels[y0:y1 + 1, x0:x1 + 1] == lab
        regions.append(Region(
            label=lab, area=int(len(ys)), bbox=(x0, y0, x1, y1),
            touches_edge=x0 <= 1 or y0 <= 1 or x1 >= w - 2 or y1 >= h - 2, mask=sub,
            contrast=float(distance[ys, xs].mean() / threshold)))
    regions.sort(key=lambda r: (r.bbox[1] // max(1, h // 12), r.bbox[0]))  # reading order: rows, then left to right
    return regions, {"background_rgb": [round(float(v), 1) for v in background],
                     "threshold": round(threshold, 1), "foreground_frac": round(float(mask.mean()), 4)}
