"""Potato defect classifier: ImageNet-pretrained backbone + calibrated linear head (transfer learning).

* Backbones come from torchvision (BSD-3-Clause code; ImageNet-pretrained weights, see
  docs/MODEL_LICENSES.md for the unresolved question on their commercial use).
* The head is a logistic regression on pooled backbone features, trained on the
  Hybrid Potato Tuber Dataset (CC BY 4.0) with a leak-free group split, then
  temperature-scaled on the validation split so probabilities are calibrated.
* The saved file holds the full weights, so inference works offline. The model is
  loaded once, lazily, the first time an inspection needs it; torch is never
  imported when no model file exists.
* It answers one question for a single-potato crop: probability of a visible defect
  (cuts, sprouts or rot, as labelled in the dataset). It is NOT a detector.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path

from app.config import ROOT

MODEL_DIR = ROOT / "models" / "potato-defect-classifier"
CURRENT = MODEL_DIR / "current.pt"
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_extractor(backbone: str, pretrained: bool = True):
    """Return (feature extractor module, feature dimension, weights enum name)."""
    import torch.nn as nn
    from torchvision import models

    if backbone == "mobilenet_v3_large":
        weights = models.MobileNet_V3_Large_Weights.IMAGENET1K_V2 if pretrained else None
        net = models.mobilenet_v3_large(weights=weights)
        extractor = nn.Sequential(net.features, net.avgpool, nn.Flatten())
        return extractor, 960, "MobileNet_V3_Large_Weights.IMAGENET1K_V2"
    if backbone == "resnet18":
        weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        net = models.resnet18(weights=weights)
        net.fc = nn.Identity()
        return net, 512, "ResNet18_Weights.IMAGENET1K_V1"
    raise ValueError(f"Unknown backbone {backbone}")


def to_tensor_batch(images):
    """PIL images -> normalised float tensor (N, 3, 224, 224)."""
    import numpy as np
    import torch

    arrays = []
    for img in images:
        im = img.convert("RGB").resize((224, 224))
        a = (np.asarray(im, dtype=np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
        arrays.append(a.transpose(2, 0, 1))
    return torch.from_numpy(np.stack(arrays).astype("float32"))


@dataclass
class DefectClassifier:
    model_id: str
    backbone: str
    extractor: object
    weight: object  # (dim,) tensor
    bias: float
    mean: object  # feature standardisation
    std: object
    temperature: float
    threshold: float
    meta: dict

    def predict(self, images) -> list[float]:
        """Calibrated probability of a visible defect for each single-potato image."""
        import torch

        with torch.inference_mode():
            feats = self.extractor(to_tensor_batch(images))
            z = ((feats - self.mean) / self.std) @ self.weight + self.bias
            return torch.sigmoid(z / self.temperature).tolist()

    def save(self, path: Path) -> str:
        import torch

        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model_id": self.model_id, "backbone": self.backbone, "extractor": self.extractor.state_dict(),
                    "weight": self.weight, "bias": self.bias, "mean": self.mean, "std": self.std,
                    "temperature": self.temperature, "threshold": self.threshold, "meta": self.meta}, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".json").write_text(json.dumps({**self.meta, "sha256": digest}, indent=2))
        return digest


def load(path: Path) -> DefectClassifier:
    import torch

    blob = torch.load(path, map_location="cpu", weights_only=True)
    extractor, _, _ = build_extractor(blob["backbone"], pretrained=False)
    extractor.load_state_dict(blob["extractor"])
    extractor.eval()
    return DefectClassifier(blob["model_id"], blob["backbone"], extractor, blob["weight"], float(blob["bias"]),
                            blob["mean"], blob["std"], float(blob["temperature"]), float(blob["threshold"]),
                            blob["meta"])


_model: DefectClassifier | None = None
_lock = threading.Lock()
_load_error: str | None = None


def available() -> bool:
    return CURRENT.exists()


def get() -> DefectClassifier | None:
    """The trained classifier, loaded once on first use; None when no model file exists."""
    global _model, _load_error
    if not CURRENT.exists():
        return None
    with _lock:
        if _model is None and _load_error is None:
            try:
                import torch

                torch.set_num_threads(2)  # leave CPU for the rest of the app and the local LLM
                _model = load(CURRENT)
            except Exception as exc:  # noqa: BLE001 - reported in status, inspection continues without it
                _load_error = f"{type(exc).__name__}: {exc}"[:300]
        return _model


def status() -> dict:
    meta = {}
    if CURRENT.with_suffix(".json").exists():
        meta = json.loads(CURRENT.with_suffix(".json").read_text())
    return {"available": CURRENT.exists(), "loaded": _model is not None, "load_error": _load_error, "meta": meta}
