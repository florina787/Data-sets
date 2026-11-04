"""Potato inspection batches: upload, detect, measure, grade, annotate, store and report.

Images are stored as files under ``var/memory/inspections/<batch>/``; SQLite keeps
only references, metadata and per-potato results. Jobs run through a bounded gate
(default: one image at a time, two waiting) so inspection never starves the rest
of the machine.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.config import get_settings
from app.db import new_id, now_iso
from app.errors import NotFound, PlatformError
from app.limits import BoundedGate
from app.memory.store import get_store
from app.vision import analyse
from app.vision.segment import Region, erode, segment

ACCEPTED = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
GRADE_COLOURS = {"Good": (47, 160, 90), "Moderate": (214, 158, 46), "Not Good": (214, 64, 64), None: (150, 150, 160)}


class Detector(Protocol):
    """A detector returns candidate regions for an RGB array. A trained instance-
    segmentation model can implement this; the classical one is the default."""
    name: str
    kind: str
    validated: bool

    def detect(self, rgb: np.ndarray) -> tuple[list[Region], dict]: ...


@dataclass
class ClassicalDetector:
    name: str = "classical-colour-segmentation-v1"
    kind: str = "classical image processing (no trained model)"
    validated: bool = False

    def detect(self, rgb: np.ndarray) -> tuple[list[Region], dict]:
        return segment(rgb)


DISCLOSURE = ("Detection uses classical colour segmentation, not a trained model. Size and shape are measured; "
              "dark and green areas are colour heuristics, not a validated defect classifier. Grades apply the "
              "batch thresholds to these measurements. Scores are heuristic, not calibrated probabilities.")

_gate: BoundedGate | None = None
_gate_lock = threading.Lock()


def gate() -> BoundedGate:
    global _gate
    s = get_settings()
    with _gate_lock:
        if _gate is None or (_gate.queue_size, _gate.wait_s) != (s.vision_queue_size, s.vision_queue_wait_s):
            _gate = BoundedGate("Potato inspection", s.vision_concurrency, s.vision_queue_size,
                                s.vision_queue_wait_s)
        return _gate


def detector() -> Detector:
    return ClassicalDetector()


def detector_status() -> dict:
    d = detector()
    return {"name": d.name, "kind": d.kind, "validated": d.validated, "disclosure": DISCLOSURE,
            "trained_model": {"available": False,
                              "reason": "No potato detection or segmentation weights are present in the repository "
                                        "or on this machine. Provide a model to enable trained instance "
                                        "segmentation and defect classification."}}


def _root() -> Path:
    return get_settings().memory_dir


def _dir(batch_id: str) -> Path:
    return _root() / "inspections" / batch_id


# --- batches --------------------------------------------------------------------------

def create_batch(username: str, title: str, supplier: str | None = None, lot_code: str | None = None,
                 mm_per_px: float | None = None, thresholds: dict | None = None,
                 conversation_id: str | None = None) -> dict:
    if mm_per_px is not None and not 0.001 <= mm_per_px <= 10:
        raise PlatformError("mm_per_px must be between 0.001 and 10")
    merged = _thresholds(thresholds)
    batch_id = new_id("INS")
    ts = now_iso()
    get_store().write([(
        "INSERT INTO inspection_batches (id, username, title, status, conversation_id, notes, created_at, supplier,"
        " lot_code, mm_per_px, thresholds_json, summary_json, detector, updated_at)"
        " VALUES (?, ?, ?, 'open', ?, NULL, ?, ?, ?, ?, ?, '{}', ?, ?)",
        (batch_id, username, title.strip()[:120] or "Inspection", conversation_id, ts, supplier, lot_code, mm_per_px,
         json.dumps(merged), detector().name, ts))])
    return get_batch(batch_id, username)


def _thresholds(overrides: dict | None) -> dict:
    base = {k: v for k, v in analyse.default_thresholds().items() if not k.startswith("_")}
    for key, value in (overrides or {}).items():
        if key not in base:
            raise PlatformError(f"Unknown threshold '{key}'", allowed=sorted(base))
        if not isinstance(value, (int, float)) or value < 0:
            raise PlatformError(f"Threshold '{key}' must be a non-negative number")
        base[key] = float(value)
    return base


def _batch_row(batch_id: str, username: str) -> dict:
    found = get_store().query("SELECT * FROM inspection_batches WHERE id = ? AND username = ?", (batch_id, username))
    if not found:
        raise NotFound("Inspection batch not found")
    b = found[0]
    b["thresholds"] = json.loads(b.pop("thresholds_json") or "{}")
    b["summary"] = json.loads(b.pop("summary_json") or "{}")
    return b


def get_batch(batch_id: str, username: str) -> dict:
    b = _batch_row(batch_id, username)
    b["images"] = get_store().query(
        "SELECT id, original_name, bytes, width, height, sha256, scale, duration_ms, created_at FROM inspection_items"
        " WHERE batch_id = ? ORDER BY created_at", (batch_id,))
    b["potatoes"] = potatoes(batch_id)
    b["detector_info"] = detector_status()
    return b


def potatoes(batch_id: str, grade: str | None = None) -> list[dict]:
    sql = "SELECT * FROM inspection_potatoes WHERE batch_id = ?"
    params: tuple = (batch_id,)
    if grade:
        sql += " AND COALESCE(corrected_grade, grade) = ?"
        params += (grade,)
    items = get_store().query(sql + " ORDER BY potato_no", params)
    for p in items:
        p["bbox"] = json.loads(p.pop("bbox_json"))
        p["reasons"] = json.loads(p.pop("reasons_json"))
        p["metrics"] = json.loads(p.pop("metrics_json"))
        p["edge"] = bool(p["edge"])
        p["model_grade"] = p["grade"]  # what the rules produced
        p["corrected"] = p["corrected_grade"] is not None
        p["grade"] = p["corrected_grade"] or p["grade"]  # effective grade: a human correction wins
    return items


def correct_potato(batch_id: str, username: str, potato_no: int, new_grade: str, reason: str) -> dict:
    """Record an inspector's correction (kept alongside the model grade, audited, summary updated)."""
    from app.records import audit

    batch = _batch_row(batch_id, username)
    if new_grade not in analyse.GRADES:
        raise PlatformError("Grade must be Good, Moderate or Not Good")
    reason = (reason or "").strip()
    if not 3 <= len(reason) <= 300:
        raise PlatformError("A reason of 3-300 characters is required for a correction")
    found = [p for p in potatoes(batch_id) if p["potato_no"] == potato_no]
    if not found:
        raise NotFound(f"Potato #{potato_no} not found in this batch")
    p = found[0]
    ts = now_iso()
    correction_id = new_id("COR")
    get_store().write([
        ("INSERT INTO inspection_corrections (id, batch_id, potato_no, model_grade, previous_grade, new_grade, reason,"
         " corrected_by, model_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
         (correction_id, batch_id, potato_no, p["model_grade"], p["grade"], new_grade, reason, username,
          batch["detector"], ts)),
        ("UPDATE inspection_potatoes SET corrected_grade = ?, corrected_by = ?, corrected_at = ?"
         " WHERE batch_id = ? AND potato_no = ?", (new_grade, username, ts, batch_id, potato_no)),
    ])
    audit(username, "inspection.correct", entity_type="inspection", entity_id=batch_id, potato_no=potato_no,
          model_grade=p["model_grade"], previous_grade=p["grade"], new_grade=new_grade, reason=reason)
    regrade(batch_id, username)
    return {"correction_id": correction_id, "batch": get_batch(batch_id, username)}


def corrections(batch_id: str, username: str) -> list[dict]:
    _batch_row(batch_id, username)
    return get_store().query("SELECT * FROM inspection_corrections WHERE batch_id = ? ORDER BY created_at",
                             (batch_id,))


def list_batches(username: str, limit: int = 50) -> list[dict]:
    items = get_store().query(
        "SELECT id, title, supplier, lot_code, status, created_at, updated_at, summary_json, conversation_id"
        " FROM inspection_batches WHERE username = ? ORDER BY created_at DESC LIMIT ?", (username, limit))
    for b in items:
        b["summary"] = json.loads(b.pop("summary_json") or "{}")
    return items


def delete_batch(batch_id: str, username: str) -> None:
    _batch_row(batch_id, username)
    get_store().write([("DELETE FROM inspection_batches WHERE id = ? AND username = ?", (batch_id, username))])
    folder = _dir(batch_id)
    if folder.exists():
        for f in folder.iterdir():
            f.unlink()
        folder.rmdir()


def link_conversation(batch_id: str, username: str, conversation_id: str) -> None:
    get_store().write([("UPDATE inspection_batches SET conversation_id = ? WHERE id = ? AND username = ?",
                        (conversation_id, batch_id, username))])


# --- inspection -----------------------------------------------------------------------

def _decode(data: bytes) -> tuple[Image.Image, str]:
    s = get_settings()
    if len(data) > s.vision_max_upload_mb * 1024 * 1024:
        raise PlatformError(f"Image is larger than {s.vision_max_upload_mb:g} MB")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            if fmt not in ACCEPTED:
                raise PlatformError("Only JPEG, PNG and WebP images are accepted", format=fmt)
            if probe.width * probe.height > s.vision_max_pixels:
                raise PlatformError("Image has too many pixels", pixels=probe.width * probe.height)
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise PlatformError("The file is not a readable image") from exc
    return img, fmt


def _timed(calls: list[dict], tool: str, fn: Callable, *args):
    started, t0 = now_iso(), time.perf_counter()
    try:
        result = fn(*args)
    except Exception as exc:
        calls.append({"tool": tool, "status": "error", "started_at": started, "error": str(exc)[:300],
                      "duration_ms": round((time.perf_counter() - t0) * 1000, 2)})
        raise
    calls.append({"tool": tool, "status": "ok", "started_at": started,
                  "duration_ms": round((time.perf_counter() - t0) * 1000, 2)})
    return result


def analyse_bytes(data: bytes, mm_per_px: float | None = None, thresholds: dict | None = None) -> list[dict]:
    """Detect, measure and grade one image without storing anything (used by evaluations).
    Boxes are in original-image pixels; grades use the same rules as stored batches."""
    img, _ = _decode(data)
    s = get_settings()
    work = img.copy()
    work.thumbnail((s.vision_working_px, s.vision_working_px))
    scale = img.width / work.width
    rgb = np.asarray(work, dtype=np.float32)
    regions, _ = detector().detect(rgb)
    rows = [analyse.measure(r, rgb, scale, mm_per_px) for r in regions]
    t = _thresholds(thresholds)
    gradable = [m["area_px"] for m in rows if not m["edge"]]
    median = float(np.median(gradable)) if gradable else 0.0
    for m in rows:
        cluster = round(m["area_px"] / median) if median and not m["edge"] and m["area_px"] > 1.8 * median \
            and m["solidity"] < 0.96 else None
        m["possible_cluster"] = cluster if cluster and cluster > 1 else None
        m["grade"], m["reasons"] = analyse.grade(m, t, median)
        m["score"] = m["detection_score"]
    return rows


def add_image(batch_id: str, username: str, data: bytes, filename: str | None = None) -> dict:
    batch = _batch_row(batch_id, username)
    calls: list[dict] = []
    started_at, t0 = now_iso(), time.perf_counter()
    with gate().slot():
        img, fmt = _timed(calls, "decode_image", _decode, data)
        s = get_settings()
        work = img.copy()
        work.thumbnail((s.vision_working_px, s.vision_working_px))
        scale = img.width / work.width
        rgb = np.asarray(work, dtype=np.float32)
        regions, diagnostics = _timed(calls, "detect_potatoes", detector().detect, rgb)
        mm = (batch["mm_per_px"] or None)
        measured = _timed(calls, "measure_potatoes", lambda: [analyse.measure(r, rgb, scale, mm) for r in regions])
        item_id = new_id("IMG")
        folder = _dir(batch_id)
        folder.mkdir(parents=True, exist_ok=True)
        original = folder / f"{item_id}{ACCEPTED[fmt]}"
        original.write_bytes(data)
        annotated_path = folder / f"{item_id}-annotated.png"
        existing = get_store().query("SELECT COALESCE(MAX(potato_no), 0) AS n FROM inspection_potatoes"
                                     " WHERE batch_id = ?", (batch_id,))[0]["n"]
        statements = [(
            "INSERT INTO inspection_items (id, batch_id, file_ref, sha256, bytes, mime, width, height, result_json,"
            " created_at, original_name, annotated_ref, scale, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, NULL)",
            (item_id, batch_id, str(original.relative_to(_root())), hashlib.sha256(data).hexdigest(), len(data),
             f"image/{fmt.lower()}", img.width, img.height, json.dumps({"diagnostics": diagnostics}), now_iso(),
             (filename or "")[:200], str(annotated_path.relative_to(_root())), scale))]
        for i, m in enumerate(measured, start=existing + 1):
            m["potato_no"] = i
            statements.append((
                "INSERT INTO inspection_potatoes (batch_id, potato_no, item_id, detection_score, length_mm, width_mm,"
                " area_px, elongation, solidity, dark_pct, green_pct, edge, bbox_json, metrics_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (batch_id, i, item_id, m["detection_score"], m.get("length_mm"), m.get("width_mm"), m["area_px"],
                 m["elongation"], m["solidity"], m["dark_pct"], m["green_pct"], int(m["edge"]),
                 json.dumps(m["bbox"]), json.dumps(m))))
        get_store().write(statements)
        _timed(calls, "grade_batch", regrade, batch_id, username)
        graded = {p["potato_no"]: p for p in potatoes(batch_id)}
        _timed(calls, "annotate_image", _annotate, work, regions, [graded[m["potato_no"]] for m in measured],
               annotated_path)
        duration = round((time.perf_counter() - t0) * 1000, 1)
        get_store().write([("UPDATE inspection_items SET duration_ms = ? WHERE id = ?", (duration, item_id))])
    get_store().record_agent_run({
        "id": new_id("AGR"), "agent": "vision.agent", "conversation_id": batch.get("conversation_id"),
        "status": "ok", "started_at": started_at, "finished_at": now_iso(), "duration_ms": duration,
        "input_summary": f"{filename or 'image'} ({len(data)} bytes) for batch {batch_id}",
        "output_summary": f"{len(measured)} potato region(s) detected",
        "detail": {"batch_id": batch_id, "item_id": item_id, "detector": detector().name, "username": username}},
        calls)
    return {"item_id": item_id, "detected": len(measured), "duration_ms": duration,
            "batch": get_batch(batch_id, username)}


def regrade(batch_id: str, username: str, thresholds: dict | None = None) -> dict:
    """Apply the batch thresholds (optionally replacing them) to the stored measurements."""
    batch = _batch_row(batch_id, username)
    t = _thresholds({**batch["thresholds"], **(thresholds or {})})
    rows = potatoes(batch_id)
    gradable = [p["metrics"]["area_px"] for p in rows if not p["edge"]]
    median = float(np.median(gradable)) if gradable else 0.0
    statements, graded_rows = [], []
    for p in rows:
        m = p["metrics"]
        cluster = round(m["area_px"] / median) if median and not m["edge"] and m["area_px"] > 1.8 * median \
            and m["solidity"] < 0.96 else None
        m["possible_cluster"] = cluster if cluster and cluster > 1 else None
        g, reasons = analyse.grade(m, t, median)
        graded_rows.append({**p, "grade": p["corrected_grade"] or g, "possible_cluster": m["possible_cluster"]})
        statements.append(("UPDATE inspection_potatoes SET grade = ?, reasons_json = ?, possible_cluster = ?,"
                           " metrics_json = ? WHERE batch_id = ? AND potato_no = ?",
                           (g, json.dumps(reasons), m["possible_cluster"], json.dumps(m), batch_id, p["potato_no"])))
    summary = _summary(graded_rows, t, batch["mm_per_px"])
    statements.append(("UPDATE inspection_batches SET thresholds_json = ?, summary_json = ?, updated_at = ?"
                       " WHERE id = ?", (json.dumps(t), json.dumps(summary), now_iso(), batch_id)))
    get_store().write(statements)
    return summary


def _summary(rows: list[dict], t: dict, mm_per_px: float | None) -> dict:
    counts = {g: sum(1 for p in rows if p["grade"] == g) for g in analyse.GRADES}
    not_graded = sum(1 for p in rows if p["grade"] is None)
    graded = sum(counts.values())
    lengths = [p["length_mm"] for p in rows if p["grade"] and p.get("length_mm")]
    return {
        "detected": len(rows), "graded": graded, "not_graded": not_graded, "counts": counts,
        "pct": {g: round(100 * c / graded, 1) if graded else 0.0 for g, c in counts.items()},
        "meets_spec": counts["Good"], "meets_spec_pct": round(100 * counts["Good"] / graded, 1) if graded else 0.0,
        "possible_clusters": sum(1 for p in rows if p.get("possible_cluster")),
        "corrected": sum(1 for p in rows if p.get("corrected_grade")),
        "dark_flagged": sum(1 for p in rows if p["grade"] and p["dark_pct"] > t["max_dark_pct_good"]),
        "green_flagged": sum(1 for p in rows if p["grade"] and p["green_pct"] > t["max_green_pct_good"]),
        "mean_length_mm": round(sum(lengths) / len(lengths), 1) if lengths else None,
        "scale_known": bool(mm_per_px),
    }


# --- images and reports ---------------------------------------------------------------

def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _annotate(work: Image.Image, regions: list[Region], rows: list[dict], path: Path) -> None:
    canvas = work.copy()
    pixels = np.asarray(canvas).copy()
    for region, p in zip(regions, rows, strict=True):
        x0, y0, x1, y1 = region.bbox
        outline = region.mask & ~erode(region.mask, 2)
        pixels[y0:y1 + 1, x0:x1 + 1][outline] = GRADE_COLOURS[p["grade"]]
    canvas = Image.fromarray(pixels)
    draw = ImageDraw.Draw(canvas)
    font = _font(max(14, work.width // 48))
    for region, p in zip(regions, rows, strict=True):
        x0, y0, _, _ = region.bbox
        label = f"#{p['potato_no']}"
        box = draw.textbbox((x0, y0), label, font=font)
        draw.rectangle((box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2), fill=(20, 18, 30))
        draw.text((x0, y0), label, fill=GRADE_COLOURS[p["grade"]], font=font)
    canvas.save(path, format="PNG", optimize=True)


def image_path(batch_id: str, username: str, item_id: str, annotated: bool) -> Path:
    _batch_row(batch_id, username)
    found = get_store().query("SELECT file_ref, annotated_ref FROM inspection_items WHERE id = ? AND batch_id = ?",
                              (item_id, batch_id))
    if not found:
        raise NotFound("Image not found")
    path = _root() / found[0]["annotated_ref" if annotated else "file_ref"]
    if not path.exists():
        raise NotFound("Image file is missing")
    return path


def potato_crop(batch_id: str, username: str, potato_no: int) -> bytes:
    _batch_row(batch_id, username)
    found = [p for p in potatoes(batch_id) if p["potato_no"] == potato_no]
    if not found:
        raise NotFound(f"Potato #{potato_no} not found in this batch")
    p = found[0]
    item = get_store().query("SELECT annotated_ref, scale FROM inspection_items WHERE id = ?", (p["item_id"],))[0]
    with Image.open(_root() / item["annotated_ref"]) as img:
        x0, y0, x1, y1 = (v / item["scale"] for v in p["bbox"])
        pad = 0.15 * max(x1 - x0, y1 - y0)
        crop = img.crop((max(0, int(x0 - pad)), max(0, int(y0 - pad)), min(img.width, int(x1 + pad)),
                         min(img.height, int(y1 + pad))))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
    return buf.getvalue()


REPORT_FIELDS = ["potato_no", "image", "grade", "detection_score", "length_mm", "width_mm", "area_px", "elongation",
                 "solidity", "dark_pct", "green_pct", "edge", "possible_cluster", "reasons"]


def report_csv(batch_id: str, username: str) -> str:
    b = get_batch(batch_id, username)
    names = {i["id"]: i["original_name"] or i["id"] for i in b["images"]}
    out = io.StringIO()
    out.write(f"# {b['title']} ({b['id']}), supplier {b['supplier'] or '-'}, lot {b['lot_code'] or '-'}\n")
    out.write(f"# {DISCLOSURE}\n")
    writer = csv.DictWriter(out, fieldnames=REPORT_FIELDS)
    writer.writeheader()
    for p in b["potatoes"]:
        writer.writerow({**{k: p.get(k) for k in REPORT_FIELDS}, "image": names.get(p["item_id"]),
                         "grade": p["grade"] or "Not graded", "reasons": "; ".join(p["reasons"])})
    return out.getvalue()


def report_json(batch_id: str, username: str) -> dict:
    b = get_batch(batch_id, username)
    return {"batch": {k: b[k] for k in ("id", "title", "supplier", "lot_code", "created_at", "mm_per_px",
                                        "thresholds", "summary")},
            "images": b["images"], "potatoes": b["potatoes"], "method": detector_status(), "generated_at": now_iso()}
