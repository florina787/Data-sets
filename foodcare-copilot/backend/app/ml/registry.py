"""Registry of models, datasets and evaluation reports (memory database).

Every evaluation records which model version ran on which dataset version and
split, the sample size, the method and the date, so results can be compared
like for like. ``trained`` is false for rule-based components: the registry
never presents a classical pipeline as a trained model.
"""

from __future__ import annotations

import json

from app.db import new_id, now_iso
from app.errors import NotFound
from app.memory.store import get_store

BUILTIN_MODELS = [
    {"name": "potato-detector-classical", "version": "1.0", "task": "detection+counting", "kind": "classical",
     "framework": "numpy (colour segmentation)", "trained": False, "weights_ref": None,
     "license": "Project source code; no model weights",
     "notes": "Background colour model + Otsu threshold + connected components. Not a trained model."},
    {"name": "potato-grader-rules", "version": "1.0", "task": "grading", "kind": "rules",
     "framework": "python (threshold rules)", "trained": False, "weights_ref": None,
     "license": "Project source code; no model weights",
     "notes": "Good/Moderate/Not Good from size, shape and colour heuristics with configurable thresholds."},
    {"name": "potato-defect-classifier-mobilenetv3", "version": "unavailable", "task": "classification",
     "kind": "neural", "framework": "PyTorch / torchvision (not installed)", "trained": False, "weights_ref": None,
     "license": "Pending: torchvision code BSD-3-Clause; pretrained weight terms to be reviewed before download",
     "notes": "Blocked: needs approval to install PyTorch and a labelled potato defect dataset."},
    {"name": "potato-instance-segmentation-maskrcnn", "version": "unavailable", "task": "segmentation",
     "kind": "neural", "framework": "PyTorch / torchvision Mask R-CNN (not installed)", "trained": False,
     "weights_ref": None, "license": "Pending: COCO-pretrained weight terms to be reviewed before download",
     "notes": "Blocked: needs approval for PyTorch and pretrained weights, plus labelled potato masks."},
]


def _row(table: str, record_id: str) -> dict:
    found = get_store().query(f"SELECT * FROM {table} WHERE id = ?", (record_id,))  # table is a constant
    if not found:
        raise NotFound(f"{table[3:-1].capitalize()} not found", id=record_id)
    return found[0]


def register_model(name: str, version: str, task: str, kind: str, framework: str, trained: bool, license: str,
                   weights_ref: str | None = None, weights_sha256: str | None = None, notes: str | None = None) -> str:
    model_id = f"{name}@{version}"
    status = "unavailable" if version == "unavailable" else "active"
    get_store().write([(
        "INSERT INTO ml_models (id, name, version, task, kind, framework, trained, weights_ref, weights_sha256,"
        " license, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET task = excluded.task, kind = excluded.kind, framework = excluded.framework,"
        " trained = excluded.trained, license = excluded.license, status = excluded.status, notes = excluded.notes",
        (model_id, name, version, task, kind, framework, int(trained), weights_ref, weights_sha256, license, status,
         notes, now_iso()))])
    return model_id


def ensure_builtins() -> None:
    for m in BUILTIN_MODELS:
        register_model(**m)


def register_dataset(name: str, version: str, task: str, source: str, license: str, synthetic: bool,
                     label_definitions: dict, n_images: int, n_objects: int, splits: dict,
                     governance: dict | None = None, created_by: str | None = None) -> str:
    dataset_id = f"{name}@{version}"
    get_store().write([(
        "INSERT INTO ml_datasets (id, name, version, task, source, license, synthetic, label_definitions_json,"
        " n_images, n_objects, splits_json, governance_json, created_by, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET source = excluded.source, license = excluded.license,"
        " n_images = excluded.n_images, n_objects = excluded.n_objects, splits_json = excluded.splits_json,"
        " governance_json = excluded.governance_json, label_definitions_json = excluded.label_definitions_json",
        (dataset_id, name, version, task, source, license, int(synthetic), json.dumps(label_definitions),
         n_images, n_objects, json.dumps(splits), json.dumps(governance or {}), created_by, now_iso()))])
    return dataset_id


def record_evaluation(model_id: str, dataset_id: str, split: str, task: str, sample_size: int, metrics: dict,
                      method: str, duration_ms: float | None = None, created_by: str | None = None) -> str:
    _row("ml_models", model_id)
    _row("ml_datasets", dataset_id)
    eval_id = new_id("EVL")
    get_store().write([(
        "INSERT INTO ml_evaluations (id, model_id, dataset_id, split, task, sample_size, metrics_json, method,"
        " duration_ms, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (eval_id, model_id, dataset_id, split, task, sample_size, json.dumps(metrics), method, duration_ms,
         created_by, now_iso()))])
    return eval_id


def models() -> list[dict]:
    rows = get_store().query("SELECT * FROM ml_models ORDER BY kind, name")
    for r in rows:
        r["trained"] = bool(r["trained"])
    return rows


def datasets() -> list[dict]:
    rows = get_store().query("SELECT * FROM ml_datasets ORDER BY created_at DESC")
    for r in rows:
        r["synthetic"] = bool(r["synthetic"])
        r["label_definitions"] = json.loads(r.pop("label_definitions_json"))
        r["splits"] = json.loads(r.pop("splits_json"))
        r["governance"] = json.loads(r.pop("governance_json"))
    return rows


def evaluations(limit: int = 50, model_id: str | None = None) -> list[dict]:
    sql = ("SELECT e.*, d.synthetic AS dataset_synthetic, d.license AS dataset_license, m.trained AS model_trained,"
           " m.kind AS model_kind FROM ml_evaluations e JOIN ml_datasets d ON d.id = e.dataset_id"
           " JOIN ml_models m ON m.id = e.model_id")
    params: tuple = ()
    if model_id:
        sql += " WHERE e.model_id = ?"
        params = (model_id,)
    rows = get_store().query(sql + " ORDER BY e.created_at DESC LIMIT ?", params + (limit,))
    for r in rows:
        r["metrics"] = json.loads(r.pop("metrics_json"))
        r["dataset_synthetic"] = bool(r["dataset_synthetic"])
        r["model_trained"] = bool(r["model_trained"])
    return rows
