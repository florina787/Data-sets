# FoodCare architecture: vision, evaluation and governance

```mermaid
flowchart LR
    IMG[Photo upload] --> DEC[Decode and size limits]
    DEC --> DET[Detector interface<br/>today: classical segmentation]
    DET --> MEAS[Measure size, shape, colour]
    MEAS --> GRADE[Rules grade with batch thresholds]
    GRADE --> REVIEW{Inspector review}
    REVIEW -- correction with reason --> CORR[(inspection_corrections)]
    GRADE --> STORE[(inspection_batches / potatoes)]
    CORR --> STORE
    STORE --> JERRY[Jerry: cited answers]
    DS[(ml_datasets + items<br/>licence, splits, hashes)] --> EVAL[Evaluation runner]
    DET --> EVAL
    GRADE --> EVAL
    EVAL --> REP[(ml_evaluations)]
    REG[(ml_models<br/>trained flag, licence)] --> LAB[Model Evaluation Lab]
    REP --> LAB
```

| Layer | Where | Notes |
|---|---|---|
| Detector interface | `backend/app/vision/service.py` (`Detector`) | A trained model plugs in here without other changes |
| Storage-free analysis | `vision.service.analyse_bytes` | Same code path as stored batches; used by evaluations |
| Registry | `backend/app/ml/registry.py` | Models, datasets, evaluations; `trained` flag is explicit |
| Datasets | `backend/app/ml/datasets.py` | COCO import, licence required, group-aware split, near-duplicate merge, checksum verification |
| Metrics | `backend/app/ml/metrics.py` | Detection, counting, classification, segmentation, calibration |
| Human review | `vision.service.correct_potato` | The rules' grade is kept; the correction wins; audited; summary updated |
| Database | `var/memory/memory.db` (migrations 1-5) | Images stay as files; SQLite stores references |

## Not built yet (and what each needs)
| Capability | Needs |
|---|---|
| Neural classification (MobileNetV3 / ResNet18) | Approval to install PyTorch and torchvision (CPU), a decision on pretrained weights, and labelled potato defect photos |
| Detection / instance segmentation (Faster/Mask R-CNN) | The same as above, plus box and mask labels |
| Video counting with tracking | Video files of potatoes on a conveyor or table; an IoU tracker will be written in-project (no new dependency) |
| French-fries inspection | Labelled fries images; physical lengths need a calibration target |
| Predictions (rejection, yield, spoilage, demand) | Historical records with real outcomes. Demand forecasting can use the existing synthetic sales, clearly labelled |
| Financial intelligence | Verified unit costs and measured waste quantities. Demo figures will be labelled synthetic |
| Equipment anomaly detection | Sensor data. Without it, only an explicitly labelled simulation |
