"""Ground-truth evaluation: detection precision/recall/F1 and grade agreement.

Works for any labelled set: synthetic renders in the tests, or real photos
annotated as ``{"potatoes": [{"bbox": [x0, y0, x1, y1], "grade": "Good"}]}`` per image.
"""

from __future__ import annotations

from collections import Counter

GRADES = ("Good", "Moderate", "Not Good")


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match(predicted: list[dict], truth: list[dict], threshold: float = 0.5) -> list[tuple[int, int, float]]:
    pairs = sorted(((iou(p["bbox"], t["bbox"]), i, j) for i, p in enumerate(predicted)
                    for j, t in enumerate(truth)), reverse=True)
    used_p, used_t, out = set(), set(), []
    for score, i, j in pairs:
        if score < threshold:
            break
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
            out.append((i, j, score))
    return out


def evaluate(images: list[tuple[list[dict], list[dict]]], threshold: float = 0.5) -> dict:
    """``images``: (predicted potatoes, ground-truth potatoes) per image."""
    tp = fp = fn = 0
    confusion: Counter = Counter()
    ious = []
    for predicted, truth in images:
        matches = match(predicted, truth, threshold)
        tp += len(matches)
        fp += len(predicted) - len(matches)
        fn += len(truth) - len(matches)
        for i, j, score in matches:
            ious.append(score)
            if truth[j].get("grade"):
                confusion[(truth[j]["grade"], predicted[i].get("grade") or "Not graded")] += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    graded = sum(confusion.values())
    agree = sum(v for (t, p), v in confusion.items() if t == p)
    return {"images": len(images), "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "mean_iou": round(sum(ious) / len(ious), 4) if ious else None, "iou_threshold": threshold,
            "grade_accuracy": round(agree / graded, 4) if graded else None,
            "confusion": {f"{t} -> {p}": v for (t, p), v in sorted(confusion.items())}}
