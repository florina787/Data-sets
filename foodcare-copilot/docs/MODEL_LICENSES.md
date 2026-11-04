# Model licences

Status on 2026-11-04. Nothing in this table has been downloaded unless it says **in use**.

## Models in use

| Model (registry id) | What it is | Trained? | Weights | Licence |
|---|---|---|---|---|
| `potato-detector-classical@1.0` | Colour segmentation + connected components (numpy) | **No**: rules, no learning | none | Project source code |
| `potato-grader-rules@1.0` | Good/Moderate/Not Good from configurable thresholds | **No** | none | Project source code |
| Your local Qwen (via Ollama / LM Studio) | Writes prose for LIVE answers from cited facts | Pretrained by its publisher; not fine-tuned here | on your machine, never downloaded by this app | Depends on the exact variant you run. **Check it:** many Qwen2.5 sizes are Apache-2.0, but some sizes ship under the Qwen licence with extra terms. |

## Candidate models (blocked until approved)

| Candidate | Code licence | Pretrained weights | Unresolved question | Decision |
|---|---|---|---|---|
| MobileNetV3 / ResNet18 classifier (torchvision) | BSD-3-Clause | ImageNet-pretrained | ImageNet's terms of access restrict use to non-commercial research. Whether that binds weights trained on it is legally unsettled. | Needs your approval. Option: train from scratch, or document the risk |
| Faster R-CNN / Mask R-CNN (torchvision) | BSD-3-Clause | COCO-pretrained | COCO annotations are CC BY 4.0; the images are from Flickr under various licences | Needs your approval |
| Detectron2 | Apache-2.0 | Model zoo, mostly COCO-pretrained (same question) | Hard to install on macOS. torchvision offers the same architectures | Not preferred |
| ByteTrack | MIT | none needed | none | Re-implement an IoU tracker in the project (no dependency) |
| Ultralytics YOLOv8/YOLO11 | **AGPL-3.0** | AGPL-3.0 | AGPL obligations would extend to the application | **Excluded** |

## Rules
* No weights are downloaded without written approval, recorded here with the source URL, SHA-256 and licence.
* The model registry records `trained = false` for every rule-based component. The UI shows "not trained" next to it.
* A neural model is registered only after it has actually been trained, with its dataset version and evaluation.
