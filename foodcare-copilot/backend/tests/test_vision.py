"""Multi-potato inspection on SYNTHETIC rendered images with exact ground truth.

These tests check counting, IDs, measurements, grading rules, storage, reports and
limits. Scores on rendered shapes are not evidence of accuracy on real photos.
"""

from __future__ import annotations

import io
import threading

import pytest
from PIL import Image

from app import config
from app.errors import NotFound, Overloaded, PlatformError
from app.memory.store import SqliteMemoryStore, get_store
from app.vision import evaluate, service, synthetic


def inspect(png: bytes, **batch) -> dict:
    b = service.create_batch("val.viewer", "test", **batch)
    return service.add_image(b["id"], "val.viewer", png, "test.png")["batch"]


def test_counts_multiple_potatoes_with_unique_ids(platform):
    png, truth = synthetic.render(seed=3)
    batch = inspect(png)
    assert batch["summary"]["detected"] == len(truth) == 12
    numbers = [p["potato_no"] for p in batch["potatoes"]]
    assert numbers == list(range(1, 13))
    for p in batch["potatoes"]:
        assert p["grade"] in ("Good", "Moderate", "Not Good") and p["reasons"]
        assert 0 <= p["detection_score"] <= 1 and len(p["bbox"]) == 4


def test_ground_truth_detection_and_grading_on_synthetic_set(platform):
    pairs = []
    for seed in range(1, 6):
        png, truth = synthetic.render(seed=seed)
        pairs.append((inspect(png)["potatoes"], truth))
    result = evaluate.evaluate(pairs)
    assert result["true_positives"] == 60 and result["false_positives"] == 0
    assert result["precision"] == 1.0 and result["recall"] == 1.0 and result["f1"] == 1.0
    assert result["grade_accuracy"] >= 0.95, result["confusion"]


def test_defect_and_shape_reasons_are_explained(platform):
    png, truth = synthetic.render(seed=1)
    batch = inspect(png)
    by_kind = {truth[j]["kind"]: batch["potatoes"][i] for i, j, _ in evaluate.match(batch["potatoes"], truth)}
    assert by_kind["dark"]["grade"] == "Not Good" and "dark area" in by_kind["dark"]["reasons"][0]
    assert by_kind["green"]["grade"] == "Not Good" and "green area" in by_kind["green"]["reasons"][0]
    assert "elongation" in by_kind["elongated"]["reasons"][0]
    assert "batch median" in by_kind["small"]["reasons"][0]
    assert by_kind["mild_dark"]["grade"] == "Moderate"


def test_scale_gives_millimetres_and_size_spec(platform):
    png, _ = synthetic.render(seed=2)
    batch = inspect(png, mm_per_px=0.5)
    assert all(p["length_mm"] for p in batch["potatoes"])
    assert batch["summary"]["scale_known"] and batch["summary"]["mean_length_mm"]
    assert any("mm (spec" in r for p in batch["potatoes"] for r in p["reasons"]) or \
        all(p["grade"] == "Good" or "mm" not in p["reasons"][0] for p in batch["potatoes"])


def test_edge_and_touching_potatoes_are_not_graded(platform):
    png, _ = synthetic.render(seed=4, kinds=["good"] * 8, touching=True)
    batch = inspect(png)
    assert batch["summary"]["possible_clusters"] == 1
    cluster = next(p for p in batch["potatoes"] if p["possible_cluster"])
    assert cluster["grade"] is None and "touching" in cluster["reasons"][0]
    img = Image.open(io.BytesIO(synthetic.render(seed=5)[0]))
    cut = img.crop((120, 0, img.width, img.height))  # slices through the first column of potatoes
    buf = io.BytesIO()
    cut.save(buf, format="PNG")
    batch = inspect(buf.getvalue())
    edge = [p for p in batch["potatoes"] if p["edge"]]
    assert edge and all(p["grade"] is None for p in edge)
    assert batch["summary"]["not_graded"] == len(edge)


def test_thresholds_regrade_without_reprocessing(platform):
    png, _ = synthetic.render(seed=1)
    batch = inspect(png)
    before = batch["summary"]["counts"]
    service.regrade(batch["id"], "val.viewer", {"max_dark_pct_moderate": 50, "max_dark_pct_good": 50})
    after = service.get_batch(batch["id"], "val.viewer")["summary"]["counts"]
    assert after["Good"] > before["Good"]
    with pytest.raises(PlatformError, match="Unknown threshold"):
        service.regrade(batch["id"], "val.viewer", {"nonsense": 1})


def test_images_reports_and_persistence(platform):
    png, _ = synthetic.render(seed=2)
    batch = inspect(png, supplier="Synthetic farm A", lot_code="LOT-7")
    item = batch["images"][0]
    annotated = service.image_path(batch["id"], "val.viewer", item["id"], annotated=True)
    assert Image.open(annotated).size[0] <= config.get_settings().vision_working_px
    crop = Image.open(io.BytesIO(service.potato_crop(batch["id"], "val.viewer", 5)))
    assert crop.size[0] > 20
    csv_text = service.report_csv(batch["id"], "val.viewer")
    assert "not a validated defect classifier" in csv_text and csv_text.count("\n") >= 14
    report = service.report_json(batch["id"], "val.viewer")
    assert report["method"]["validated"] is False and report["batch"]["supplier"] == "Synthetic farm A"
    fresh = SqliteMemoryStore()  # another process opening the same file
    assert len(fresh.query("SELECT * FROM inspection_potatoes WHERE batch_id = ?", (batch["id"],))) == 12
    runs = get_store().query("SELECT id FROM agent_runs WHERE agent = 'vision.agent'")
    tools = [t["tool"] for t in get_store().tool_calls_for(runs[0]["id"])]
    assert tools == ["decode_image", "detect_potatoes", "measure_potatoes", "grade_batch", "annotate_image"]


def test_batches_are_private_and_deletable(platform):
    batch = inspect(synthetic.render(seed=1)[0])
    with pytest.raises(NotFound):
        service.get_batch(batch["id"], "maya.marketing")
    with pytest.raises(NotFound):
        service.potato_crop(batch["id"], "maya.marketing", 1)
    service.delete_batch(batch["id"], "val.viewer")
    assert service.list_batches("val.viewer") == []


def test_rejects_non_images_and_oversized_uploads(platform):
    b = service.create_batch("val.viewer", "bad")
    with pytest.raises(PlatformError, match="not a readable image"):
        service.add_image(b["id"], "val.viewer", b"not an image", "x.png")
    config.configure(vision_max_upload_mb=0.001)
    with pytest.raises(PlatformError, match="larger than"):
        service.add_image(b["id"], "val.viewer", synthetic.render(seed=1)[0], "x.png")


def test_vision_jobs_are_bounded(platform):
    config.configure(vision_concurrency=1, vision_queue_size=0, vision_queue_wait_s=1)
    gate = service.gate()
    entered, release = threading.Event(), threading.Event()

    def hold():
        with gate.slot():
            entered.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    entered.wait(5)
    b = service.create_batch("val.viewer", "busy")
    with pytest.raises(Overloaded):
        service.add_image(b["id"], "val.viewer", synthetic.render(seed=1)[0], "x.png")
    release.set()
    t.join()
    assert gate.status()["rejected"] == 1


def test_inspector_correction_keeps_model_grade_and_updates_summary(platform):
    batch = inspect(synthetic.render(seed=1)[0])
    bad = next(p for p in batch["potatoes"] if p["grade"] == "Not Good")
    before = batch["summary"]["counts"]
    with pytest.raises(PlatformError, match="reason"):
        service.correct_potato(batch["id"], "val.viewer", bad["potato_no"], "Good", "")
    with pytest.raises(NotFound):
        service.correct_potato(batch["id"], "maya.marketing", bad["potato_no"], "Good", "soil, not rot")
    out = service.correct_potato(batch["id"], "val.viewer", bad["potato_no"], "Good", "soil, not rot")["batch"]
    fixed = next(p for p in out["potatoes"] if p["potato_no"] == bad["potato_no"])
    assert fixed["grade"] == "Good" and fixed["model_grade"] == "Not Good" and fixed["corrected"]
    assert out["summary"]["counts"]["Good"] == before["Good"] + 1 and out["summary"]["corrected"] == 1
    service.regrade(batch["id"], "val.viewer", {"max_dark_pct_good": 0.5})  # re-grading keeps the correction
    again = next(p for p in service.potatoes(batch["id"]) if p["potato_no"] == bad["potato_no"])
    assert again["grade"] == "Good"
    log = service.corrections(batch["id"], "val.viewer")
    assert log[0]["model_grade"] == "Not Good" and log[0]["new_grade"] == "Good"
    assert log[0]["corrected_by"] == "val.viewer" and log[0]["model_version"] == service.detector().name
