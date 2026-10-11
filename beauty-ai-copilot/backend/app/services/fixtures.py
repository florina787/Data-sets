"""Loading and digesting fixture files (models, datasets, configs, policies)."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.errors import NotFound


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def canonical_digest(obj) -> str:
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode())


def file_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def synthetic_dir() -> Path:
    return get_settings().data_dir / "synthetic"


@lru_cache(maxsize=8)
def _json(path: str) -> dict:
    return json.loads(Path(path).read_text())


def load_json(path: Path) -> dict:
    return _json(str(path))


def models_file() -> dict:
    return load_json(synthetic_dir() / "models.json")


def model_spec(model_id: str) -> dict:
    for m in models_file()["models"]:
        if m["model_id"] == model_id:
            return m
    raise NotFound("model_not_found", f"Model {model_id} not in fixture registry")


def predictions_path(model_id: str) -> Path:
    return synthetic_dir() / "predictions" / f"{model_id}.json"


def compute_artifact_digest(model_id: str) -> str:
    """Digest over the artifact contents (fixture predictions) and its configuration. Recomputed from
    files at evaluation and release time, so a modified artifact is detected as a mismatch."""
    spec = model_spec(model_id)
    lpm = models_file()["lighting_profile_maps"][spec["lighting_profile_map"]]
    return canonical_digest({
        "predictions": file_digest(predictions_path(model_id)),
        "preprocessing": spec["preprocessing"],
        "lighting_profile_map": lpm,
        "catalogue_version": "CAT-2026.1",
        "code_revision": spec["code_revision"],
    })


def dataset_file() -> dict:
    return load_json(synthetic_dir() / "dataset_snapshot.json")


def dataset_digest() -> str:
    return file_digest(synthetic_dir() / "dataset_snapshot.json")


def eval_config(config_id: str) -> tuple[dict, str]:
    p = get_settings().eval_config_dir / f"{config_id}.json"
    if not p.exists():
        raise NotFound("evaluation_config_missing", f"Evaluation config {config_id} not found")
    return json.loads(p.read_text()), file_digest(p)


def policy() -> tuple[dict, str]:
    p = get_settings().policy_dir / "release-policy-v2.1.json"
    if not p.exists():
        raise NotFound("policy_missing", "Release policy configuration missing")
    return json.loads(p.read_text()), file_digest(p)


def demo_clarifications() -> dict:
    return load_json(synthetic_dir() / "demo_clarifications.json")["answers"]


def clear_caches() -> None:
    _json.cache_clear()
