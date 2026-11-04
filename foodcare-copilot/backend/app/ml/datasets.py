"""Labelled datasets: synthetic renders and imported COCO-format photo sets.

Governance built in:
* a licence and a source are required for every dataset;
* images are referenced by path and SHA-256 (not copied into SQLite) and verified when used;
* splits are made per acquisition group (batch, session, or filename prefix), never per image;
* near-duplicate images (64-bit difference hash, Hamming distance <= 5) are merged into one group
  before splitting, so the same scene cannot appear in both training and test data;
* a leakage check after splitting reports any remaining cross-split duplicates (expected: zero).
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

from app.errors import PlatformError
from app.memory.store import get_store
from app.ml import registry
from app.vision import synthetic

GRADES = ("Good", "Moderate", "Not Good")
SPLIT_FRACTIONS = (("train", 0.70), ("val", 0.15), ("test", 0.15))
NEAR_DUPLICATE_BITS = 5


def dhash(data: bytes) -> str:
    """64-bit difference hash of an image (robust to resizing and recompression)."""
    with Image.open(io.BytesIO(data)) as img:
        small = np.asarray(img.convert("L").resize((9, 8), Image.Resampling.BILINEAR), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _group_of(image: dict) -> str:
    for key in ("group", "batch", "session", "acquisition_session"):
        if image.get(key):
            return str(image[key])
    stem = Path(image["file_name"]).stem
    return re.split(r"[_-](?=[^_-]*$)", stem)[0] if re.search(r"[_-]", stem) else stem


def _split(items: list[dict]) -> dict:
    """Merge near-duplicate groups, then assign whole groups to train/val/test."""
    parent = {it["group_key"]: it["group_key"] for it in items}

    def find(g: str) -> str:
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    merged = 0
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if find(a["group_key"]) != find(b["group_key"]) and (
                    a["sha256"] == b["sha256"] or hamming(a["dhash"], b["dhash"]) <= NEAR_DUPLICATE_BITS):
                parent[find(b["group_key"])] = find(a["group_key"])
                merged += 1
    groups: dict[str, list[dict]] = {}
    for it in items:
        it["group_key"] = find(it["group_key"])
        groups.setdefault(it["group_key"], []).append(it)
    order = sorted(groups, key=lambda g: hashlib.sha256(g.encode()).hexdigest())
    total, done, k = len(items), 0, 0
    bounds = np.cumsum([f for _, f in SPLIT_FRACTIONS])
    for g in order:
        frac = done / total if total else 0
        while k < len(bounds) - 1 and frac >= bounds[k]:
            k += 1
        for it in groups[g]:
            it["split"] = SPLIT_FRACTIONS[k][0]
        done += len(groups[g])
    if len(order) >= 3 and not any(it["split"] == "test" for it in items):  # tiny sets: keep a test group
        for it in groups[order[-1]]:
            it["split"] = "test"
    cross = sum(1 for i, a in enumerate(items) for b in items[i + 1:]
                if a["split"] != b["split"] and (a["sha256"] == b["sha256"]
                                                 or hamming(a["dhash"], b["dhash"]) <= NEAR_DUPLICATE_BITS))
    counts = {name: sum(1 for it in items if it["split"] == name) for name, _ in SPLIT_FRACTIONS}
    return {"counts": counts, "groups": len(groups), "near_duplicate_merges": merged,
            "cross_split_near_duplicates": cross,
            "method": f"group-aware split 70/15/15 by acquisition group; dHash Hamming <= {NEAR_DUPLICATE_BITS} merged"}


def _store_items(dataset_id: str, items: list[dict]) -> None:
    get_store().write([("DELETE FROM ml_dataset_items WHERE dataset_id = ?", (dataset_id,))] + [(
        "INSERT INTO ml_dataset_items (dataset_id, image_id, file_ref, sha256, width, height, split, group_key, dhash,"
        " annotations_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (dataset_id, it["image_id"], it["file_ref"], it["sha256"], it["width"], it["height"], it["split"],
         it["group_key"], it["dhash"], json.dumps(it["annotations"]))) for it in items])


def ensure_synthetic(n: int = 20, first_seed: int = 1000) -> str:
    """Register the rendered SYNTHETIC evaluation set (all images in the test split)."""
    name, version = "synthetic-potatoes", f"v1-{n}x{first_seed}"
    dataset_id = f"{name}@{version}"
    if get_store().query("SELECT 1 FROM ml_datasets WHERE id = ?", (dataset_id,)):
        return dataset_id
    items = []
    for seed in range(first_seed, first_seed + n):
        png, truth = synthetic.render(seed=seed)
        items.append({"image_id": f"seed-{seed}", "file_ref": f"synthetic:seed={seed}",
                      "sha256": hashlib.sha256(png).hexdigest(), "width": 960, "height": 720, "split": "test",
                      "group_key": f"seed-{seed}", "dhash": dhash(png),
                      "annotations": [{"bbox": t["bbox"], "label": "potato", "grade": t["grade"], "kind": t["kind"]}
                                      for t in truth]})
    registry.register_dataset(
        name, version, "detection+counting+grading", "Rendered by app/vision/synthetic.py (drawn ellipses)",
        "Generated by this project; no third-party content", True,
        {"potato": "drawn potato-shaped ellipse", "grades": list(GRADES)}, len(items),
        sum(len(i["annotations"]) for i in items), {"test": len(items)},
        {"note": "SYNTHETIC: drawn shapes on a plain background. Scores on it say nothing about real potatoes."})
    _store_items(dataset_id, items)
    return dataset_id


def import_coco(folder: Path, name: str, version: str, license: str, source: str, created_by: str = "cli") -> dict:
    """Import ``folder/annotations.json`` (COCO) and its images by reference."""
    if not license.strip() or not source.strip():
        raise PlatformError("A dataset licence and source are required")
    ann_path = folder / "annotations.json"
    if not ann_path.exists():
        raise PlatformError("annotations.json not found", folder=str(folder))
    coco = json.loads(ann_path.read_text())
    categories = {c["id"]: c["name"] for c in coco.get("categories", [])}
    by_image: dict = {}
    for a in coco.get("annotations", []):
        x, y, w, h = a["bbox"]
        label = categories.get(a.get("category_id"), "potato")
        grade = (a.get("attributes") or {}).get("grade") or (label if label in GRADES else None)
        by_image.setdefault(a["image_id"], []).append(
            {"bbox": [x, y, x + w, y + h], "label": "potato" if label in GRADES else label, "grade": grade})
    items = []
    for image in coco.get("images", []):
        path = (folder / image["file_name"]).resolve()
        if folder.resolve() not in path.parents:
            raise PlatformError("Image path escapes the dataset folder", file=image["file_name"])
        data = path.read_bytes()
        items.append({"image_id": str(image["id"]), "file_ref": str(path), "sha256": hashlib.sha256(data).hexdigest(),
                      "width": image.get("width"), "height": image.get("height"), "group_key": _group_of(image),
                      "dhash": dhash(data), "annotations": by_image.get(image["id"], [])})
    if not items:
        raise PlatformError("The dataset has no images")
    governance = _split(items)
    dataset_id = registry.register_dataset(
        name, version, "detection+counting+grading", source, license, False,
        {"categories": sorted(set(categories.values())), "grades": list(GRADES)}, len(items),
        sum(len(i["annotations"]) for i in items), governance["counts"], governance, created_by)
    _store_items(dataset_id, items)
    return {"dataset_id": dataset_id, **governance}


def load_items(dataset_id: str, split: str) -> list[tuple[dict, bytes]]:
    rows = get_store().query("SELECT * FROM ml_dataset_items WHERE dataset_id = ? AND split = ? ORDER BY image_id",
                             (dataset_id, split))
    out = []
    for r in rows:
        if r["file_ref"].startswith("synthetic:seed="):
            data, _ = synthetic.render(seed=int(r["file_ref"].split("=", 1)[1]))
        else:
            data = Path(r["file_ref"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != r["sha256"]:
            raise PlatformError("Dataset image changed since import (checksum mismatch)", image=r["image_id"])
        r["annotations"] = json.loads(r.pop("annotations_json"))
        out.append((r, data))
    return out
