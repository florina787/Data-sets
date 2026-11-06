"""Metrics (hand-checked values), registry, dataset governance and recorded evaluations."""

from __future__ import annotations

import io
import json

import numpy as np
import pytest
from PIL import Image

from app.errors import PlatformError
from app.ml import datasets, evaluate, metrics, registry
from app.vision import synthetic


def test_detection_ap_hand_checked():
    truth = [{"bbox": [0, 0, 10, 10]}, {"bbox": [20, 20, 30, 30]}]
    # perfect: both found, one low-score false positive ranked last -> AP 1.0
    preds = [{"bbox": [0, 0, 10, 10], "score": 0.9}, {"bbox": [20, 20, 30, 30], "score": 0.8},
             {"bbox": [50, 50, 60, 60], "score": 0.1}]
    m = metrics.detection_metrics([(preds, truth)])
    assert m["map50"] == 1.0 and m["per_class"]["all"]["false_positives50"] == 1
    # false positive ranked first: precision 0, 1/2, 2/3 -> envelope 2/3 at every recall -> AP = 2/3
    preds[2]["score"] = 0.95
    assert metrics.detection_metrics([(preds, truth)])["map50"] == pytest.approx(0.6667, abs=1e-3)
    # one box shifted to IoU 0.6: counts at 0.50..0.60 (3 of 10 thresholds), not above
    shifted = [{"bbox": [0, 0, 10, 10], "score": 0.9}, {"bbox": [22.5, 20, 32.5, 30], "score": 0.8}]
    assert metrics.box_iou(shifted[1]["bbox"], truth[1]["bbox"]) == pytest.approx(0.6)
    m = metrics.detection_metrics([(shifted, truth)])
    assert m["map50"] == 1.0
    # thresholds 0.50-0.60 -> AP 1.0 (3x); 0.65-0.95 -> one of two found at full precision: AP ~0.5 (7x)
    assert m["map50_95"] == pytest.approx((3 * 1.0 + 7 * 0.5049) / 10, abs=1e-3)


def test_counting_and_classification_hand_checked():
    c = metrics.counting_metrics([(10, 10), (10, 12), (5, 4)])
    assert c["mae"] == 1.0 and c["rmse"] == pytest.approx(np.sqrt(5 / 3), abs=1e-4)
    assert c["exact_count_accuracy"] == pytest.approx(1 / 3, abs=1e-4)
    assert c["overcount_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert c["undercount_rate"] == pytest.approx(1 / 3, abs=1e-4)
    k = metrics.classification_metrics(["a", "a", "b", "b"], ["a", "b", "b", "b"], ["a", "b"])
    assert k["accuracy"] == 0.75 and k["confusion_matrix"] == [[1, 1], [0, 2]]
    assert k["per_class"]["a"] == {"precision": 1.0, "recall": 0.5, "f1": 0.6667, "support": 2}
    assert k["macro_f1"] == pytest.approx((0.6667 + 0.8) / 2, abs=1e-3)


def test_segmentation_and_probability_metrics():
    a = np.zeros((4, 4), bool)
    b = np.zeros((4, 4), bool)
    a[:2, :] = True  # 8 px
    b[1:3, :] = True  # 8 px, overlap 4
    assert metrics.mask_iou(a, b) == pytest.approx(4 / 12) and metrics.dice(a, b) == pytest.approx(0.5)
    assert metrics.brier_score([1, 0], [0.8, 0.4]) == pytest.approx(0.1)
    assert metrics.expected_calibration_error([1, 1, 0, 0], [1.0, 1.0, 0.0, 0.0]) == 0.0


def test_builtin_registry_never_marks_rules_as_trained(platform):
    registry.ensure_builtins()
    models = {m["id"]: m for m in registry.models()}
    assert models["potato-detector-classical@1.0"]["trained"] is False
    assert models["potato-defect-classifier-mobilenetv3@unavailable"]["status"] == "unavailable"


def test_synthetic_evaluation_is_recorded_with_provenance(platform):
    result = evaluate.run(datasets.ensure_synthetic(n=4, first_seed=1))
    assert result["detection"]["map50"] == 1.0 and result["detection"]["counting"]["mae"] == 0.0
    evs = registry.evaluations()
    assert {e["task"] for e in evs} == {"detection+counting", "grading"}
    for e in evs:
        assert e["dataset_synthetic"] and e["sample_size"] > 0 and e["method"] and e["created_at"]
        assert e["model_trained"] is False


def _write_coco(folder, entries):
    images, anns = [], []
    for i, (name, png, truth) in enumerate(entries, start=1):
        (folder / name).write_bytes(png)
        images.append({"id": i, "file_name": name, "width": 960, "height": 720})
        for t in truth:
            x0, y0, x1, y1 = t["bbox"]
            anns.append({"id": len(anns) + 1, "image_id": i, "category_id": 1, "bbox": [x0, y0, x1 - x0, y1 - y0],
                         "attributes": {"grade": t["grade"]}})
    (folder / "annotations.json").write_text(json.dumps(
        {"images": images, "annotations": anns, "categories": [{"id": 1, "name": "potato"}]}))


def test_import_merges_near_duplicates_and_splits_by_group(platform, tmp_path):
    entries = []
    for seed in range(1, 8):
        png, truth = synthetic.render(seed=seed)
        entries.append((f"session{seed}_a.png", png, truth))
    # a recompressed copy of session1 under a different session name: a near duplicate
    buf = io.BytesIO()
    Image.open(io.BytesIO(entries[0][1])).save(buf, format="JPEG", quality=80)
    entries.append(("session99_a.jpg", buf.getvalue(), entries[0][2]))
    _write_coco(tmp_path, entries)
    with pytest.raises(PlatformError, match="licence and source"):
        datasets.import_coco(tmp_path, "farm-photos", "1", "", "")
    report = datasets.import_coco(tmp_path, "farm-photos", "1", "CC-BY-4.0 (test)", "unit test")
    assert report["near_duplicate_merges"] >= 1 and report["cross_split_near_duplicates"] == 0
    assert sum(report["counts"].values()) == 8 and report["counts"]["test"] >= 1
    result = evaluate.run(report["dataset_id"], "test")
    assert result["detection"]["counting"]["n"] == report["counts"]["test"]
    (tmp_path / "session2_a.png").write_bytes(b"tampered")
    with pytest.raises(PlatformError, match="checksum mismatch"):  # images are verified on every use
        for split in ("train", "val", "test"):
            datasets.load_items(report["dataset_id"], split)


def test_roc_auc_and_average_precision_hand_checked():
    y, s = [0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]
    assert metrics.roc_auc(y, s) == 0.75  # 3 of 4 positive/negative pairs ranked correctly
    assert metrics.average_precision(y, s) == pytest.approx((1 / 1 + 2 / 3) / 2, abs=1e-4)
    assert metrics.roc_auc([1, 1], [0.2, 0.3]) is None
