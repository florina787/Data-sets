# Model evaluation

## What is measured
| Task | Metrics | Implementation |
|---|---|---|
| Detection | mAP@50, mAP@50:95 (COCO 101-point), precision, recall, TP/FP/FN | `backend/app/ml/metrics.py: detection_metrics` |
| Counting | MAE, RMSE, mean relative error, exact-count accuracy, overcount / undercount rates | `counting_metrics` |
| Grading / classification | accuracy, per-class precision/recall/F1, macro F1, confusion matrix | `classification_metrics` |
| Segmentation | IoU, Dice | `mask_iou`, `dice` |
| Probabilities | Brier score, expected calibration error | `brier_score`, `expected_calibration_error` |

The metric code is checked against hand-computed cases in `backend/tests/test_ml.py`.

Every evaluation is stored in `ml_evaluations` with the **model version, dataset version, split, sample size, method, duration, user and date**. It appears in the **Model Evaluation Lab** page.

## Current results (2026-11-04)
Classical detector `potato-detector-classical@1.0` and rules `potato-grader-rules@1.0` on `synthetic-potatoes@v1-20x1000`, test split (20 images, 240 drawn potatoes):

| Metric | Value |
|---|---|
| mAP@50 / mAP@50:95 | 1.000 / 1.000 |
| Precision / recall (IoU 0.5) | 1.000 / 1.000 |
| Counting MAE / exact-count accuracy | 0.0 / 100% |
| Grading accuracy / macro F1 | 99.17% / 0.997 (2 of 240 left "not graded") |
| Inference time | ~125 ms per 960 × 720 image (4-core CPU, no GPU) |

**Interpretation:** these numbers only show that the pipeline and the metric code work end to end. The images are clean drawn shapes, so perfect scores are expected and **say nothing about real potatoes**. No real labelled dataset has been evaluated.

## How to run
```bash
.venv/bin/python scripts/eval_vision.py --synthetic 20
.venv/bin/python scripts/eval_vision.py --dataset path/to/folder --name farm-photos --version 1 --license "..." --source "..."
```
Or use **Run evaluation on the synthetic set** in the Model Evaluation Lab (engineer, product owner or release approver).

## Licence scan
```bash
.venv/bin/python - <<'PY'
from importlib import metadata as m
for d in m.distributions():
    md = d.metadata
    print(md["Name"], d.version, md.get("License-Expression") or md.get("License", "")[:40],
          [c for c in md.get_all("Classifier") or [] if c.startswith("License")])
PY
```
