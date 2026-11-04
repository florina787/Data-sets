"""Evaluation metrics for detection, counting, classification, segmentation and probabilities.

Pure numpy, following the usual definitions:
* detection AP uses COCO-style 101-point interpolated precision, greedy matching by score,
  one ground-truth box per prediction; mAP@50:95 averages IoU thresholds 0.50, 0.55, ..., 0.95;
* counting reports MAE, RMSE, mean relative error, exact-count accuracy and over/undercount rates;
* classification reports accuracy, per-class precision/recall/F1/support, macro F1 and a confusion matrix;
* segmentation reports IoU and Dice for boolean masks;
* probability quality reports the Brier score and expected calibration error (ECE).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

COCO_IOUS = tuple(round(0.5 + 0.05 * i, 2) for i in range(10))


def box_iou(a: Sequence[float], b: Sequence[float]) -> float:
    """IoU of two [x0, y0, x1, y1] boxes."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _ap_at(images: list[tuple[list[dict], list[dict]]], thr: float, label: str | None) -> tuple[float, int, int, int]:
    """AP for one class at one IoU threshold. Returns (ap, tp, fp, n_truth) at full recall of the ranking."""
    scored: list[tuple[float, int, int]] = []  # (score, image index, prediction index)
    n_truth = 0
    for i, (pred, truth) in enumerate(images):
        n_truth += sum(1 for t in truth if label is None or t.get("label") == label)
        scored += [(float(p.get("score", 1.0)), i, j) for j, p in enumerate(pred)
                   if label is None or p.get("label") == label]
    scored.sort(key=lambda x: -x[0])
    used: list[set[int]] = [set() for _ in images]
    hits = []
    for _, i, j in scored:
        pred, truth = images[i]
        best, best_k = thr, -1
        for k, t in enumerate(truth):
            if k in used[i] or (label is not None and t.get("label") != label):
                continue
            iou = box_iou(pred[j]["bbox"], t["bbox"])
            if iou >= best:
                best, best_k = iou, k
        if best_k >= 0:
            used[i].add(best_k)
        hits.append(best_k >= 0)
    if n_truth == 0:
        return (float("nan"), 0, len(hits), 0)
    tp = np.cumsum(hits, dtype=float)
    fp = np.cumsum([not h for h in hits], dtype=float)
    recall = tp / n_truth if len(hits) else np.array([])
    precision = tp / np.maximum(tp + fp, 1e-12) if len(hits) else np.array([])
    # precision envelope, then 101-point interpolation
    for k in range(len(precision) - 2, -1, -1):
        precision[k] = max(precision[k], precision[k + 1])
    points = np.linspace(0, 1, 101)
    interp = [float(precision[np.searchsorted(recall, r, side="left")]) if len(recall) and r <= recall[-1] else 0.0
              for r in points]
    return float(np.mean(interp)), int(tp[-1]) if len(hits) else 0, int(fp[-1]) if len(hits) else 0, n_truth


def detection_metrics(images: list[tuple[list[dict], list[dict]]], labels: Sequence[str] | None = None) -> dict:
    """``images``: per image (predictions with bbox/score[/label], ground truth with bbox[/label])."""
    classes = list(labels) if labels else [None]
    per_class = {}
    for label in classes:
        aps = {thr: _ap_at(images, thr, label) for thr in COCO_IOUS}
        ap50, tp, fp, n_truth = aps[0.5]
        per_class[label or "all"] = {
            "ap50": round(ap50, 4), "ap50_95": round(float(np.nanmean([a[0] for a in aps.values()])), 4),
            "precision50": round(tp / (tp + fp), 4) if tp + fp else 0.0,
            "recall50": round(tp / n_truth, 4) if n_truth else 0.0,
            "true_positives50": tp, "false_positives50": fp, "false_negatives50": n_truth - tp, "ground_truth": n_truth,
        }
    valid = [v for v in per_class.values() if not math.isnan(v["ap50"])]
    return {"map50": round(float(np.mean([v["ap50"] for v in valid])), 4) if valid else None,
            "map50_95": round(float(np.mean([v["ap50_95"] for v in valid])), 4) if valid else None,
            "per_class": per_class, "images": len(images), "interpolation": "COCO 101-point"}


def counting_metrics(pairs: Sequence[tuple[int, int]]) -> dict:
    """``pairs``: (true count, predicted count) per image or per video sequence."""
    if not pairs:
        return {"n": 0}
    t = np.array([p[0] for p in pairs], dtype=float)
    p = np.array([p[1] for p in pairs], dtype=float)
    err = p - t
    rel = np.abs(err)[t > 0] / t[t > 0]
    return {"n": len(pairs), "mae": round(float(np.mean(np.abs(err))), 4),
            "rmse": round(float(np.sqrt(np.mean(err ** 2))), 4),
            "mean_relative_error": round(float(np.mean(rel)), 4) if len(rel) else None,
            "exact_count_accuracy": round(float(np.mean(err == 0)), 4),
            "overcount_rate": round(float(np.mean(err > 0)), 4), "undercount_rate": round(float(np.mean(err < 0)), 4),
            "true_total": int(t.sum()), "predicted_total": int(p.sum())}


def classification_metrics(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]) -> dict:
    labels = list(labels)
    index = {lab: i for i, lab in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), dtype=int)
    skipped = 0
    for t, p in zip(y_true, y_pred, strict=True):
        if t in index and p in index:
            matrix[index[t], index[p]] += 1
        else:
            skipped += 1
    per_class, f1s = {}, []
    for i, lab in enumerate(labels):
        tp = matrix[i, i]
        fp = matrix[:, i].sum() - tp
        fn = matrix[i, :].sum() - tp
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        support = int(matrix[i, :].sum())
        per_class[lab] = {"precision": round(float(prec), 4), "recall": round(float(rec), 4),
                          "f1": round(float(f1), 4), "support": support}
        if support:
            f1s.append(f1)
    total = int(matrix.sum())
    return {"n": total, "skipped_unlabelled": skipped,
            "accuracy": round(float(np.trace(matrix) / total), 4) if total else None,
            "macro_f1": round(float(np.mean(f1s)), 4) if f1s else None,
            "per_class": per_class, "labels": labels, "confusion_matrix": matrix.tolist()}


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 1.0


def dice(a: np.ndarray, b: np.ndarray) -> float:
    total = a.sum() + b.sum()
    return float(2 * np.logical_and(a, b).sum() / total) if total else 1.0


def brier_score(y: Sequence[int], prob: Sequence[float]) -> float:
    y_arr, p_arr = np.asarray(y, dtype=float), np.asarray(prob, dtype=float)
    return round(float(np.mean((p_arr - y_arr) ** 2)), 4)


def expected_calibration_error(y: Sequence[int], prob: Sequence[float], bins: int = 10) -> float:
    y_arr, p_arr = np.asarray(y, dtype=float), np.asarray(prob, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (p_arr > lo) & (p_arr <= hi) if lo > 0 else (p_arr >= lo) & (p_arr <= hi)
        if mask.any():
            ece += mask.mean() * abs(p_arr[mask].mean() - y_arr[mask].mean())
    return round(float(ece), 4)
