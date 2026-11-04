"""Evaluate the potato detector and grader on a registered dataset split and record the results."""

from __future__ import annotations

import time

from app.ml import datasets, metrics, registry
from app.vision import evaluate as vmatch
from app.vision import service as vision

DETECTOR = "potato-detector-classical@1.0"
GRADER = "potato-grader-rules@1.0"
GRADE_LABELS = ["Good", "Moderate", "Not Good", "Not graded"]


def run(dataset_id: str, split: str = "test", user: str = "system") -> dict:
    registry.ensure_builtins()
    started = time.perf_counter()
    images, counts, y_true, y_pred = [], [], [], []
    inference_ms = 0.0
    for item, data in datasets.load_items(dataset_id, split):
        truth = item["annotations"]
        t0 = time.perf_counter()
        preds = vision.analyse_bytes(data)
        inference_ms += (time.perf_counter() - t0) * 1000
        images.append((preds, truth))
        counts.append((len(truth), len(preds)))
        for i, j, _ in vmatch.match(preds, truth, 0.5):
            if truth[j].get("grade"):
                y_true.append(truth[j]["grade"])
                y_pred.append(preds[i]["grade"] or "Not graded")
    if not images:
        raise ValueError(f"No images in split '{split}' of {dataset_id}")
    duration = round((time.perf_counter() - started) * 1000, 1)
    detection = {**metrics.detection_metrics(images), "counting": metrics.counting_metrics(counts),
                 "inference_ms_per_image": round(inference_ms / len(images), 1)}
    grading = metrics.classification_metrics(y_true, y_pred, GRADE_LABELS)
    method = (f"{len(images)} images from {dataset_id} split '{split}'; boxes matched at IoU >= 0.5 for grading; "
              "detection score = heuristic detection_score")
    det_id = registry.record_evaluation(DETECTOR, dataset_id, split, "detection+counting", len(images), detection,
                                        method, duration, user)
    grade_id = registry.record_evaluation(GRADER, dataset_id, split, "grading", grading["n"], grading,
                                          method + "; grades of matched potatoes only", duration, user)
    return {"detection_evaluation": det_id, "grading_evaluation": grade_id, "detection": detection,
            "grading": grading, "images": len(images), "duration_ms": duration}
