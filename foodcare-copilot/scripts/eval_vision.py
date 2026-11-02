"""Evaluate potato detection and grading against labelled images.

Usage:
    .venv/bin/python scripts/eval_vision.py --synthetic 20          # rendered shapes (pipeline check only)
    .venv/bin/python scripts/eval_vision.py --dataset path/to/dir   # real labelled photos

A dataset directory holds images plus ``labels.json``:
    {"images": [{"file": "a.jpg", "mm_per_px": 0.25,
                 "potatoes": [{"bbox": [x0, y0, x1, y1], "grade": "Good"}]}]}
Bounding boxes are in original-image pixels; "grade" is optional. Results are
printed and stored in the ``evaluations`` table of the memory database, labelled
with the data source, so synthetic and real results are never mixed up.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import new_id, now_iso  # noqa: E402
from app.memory.store import get_store  # noqa: E402
from app.vision import evaluate, service, synthetic  # noqa: E402


def run(samples: list[tuple[str, bytes, list[dict], float | None]], source: str) -> dict:
    pairs, timings = [], []
    for name, data, truth, mm in samples:
        batch = service.create_batch("eval", f"evaluation: {name}", mm_per_px=mm)
        t0 = time.perf_counter()
        result = service.add_image(batch["id"], "eval", data, name)
        timings.append((time.perf_counter() - t0) * 1000)
        pairs.append((result["batch"]["potatoes"], truth))
        service.delete_batch(batch["id"], "eval")
    report = evaluate.evaluate(pairs)
    report.update(source=source, detector=service.detector().name,
                  ms_per_image_mean=round(sum(timings) / len(timings), 1) if timings else None)
    get_store().write([(
        "INSERT INTO evaluations (id, kind, subject, metric, value, passed, detail_json, created_at)"
        " VALUES (?, 'vision.detection', ?, 'f1', ?, NULL, ?, ?)",
        (new_id("EVL"), f"{report['detector']} on {source}", report["f1"], json.dumps(report), now_iso()))])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--synthetic", type=int, metavar="N", help="evaluate on N rendered synthetic images")
    group.add_argument("--dataset", type=Path, help="directory with images and labels.json")
    args = parser.parse_args()
    if args.synthetic:
        samples = []
        for seed in range(args.synthetic):
            data, truth = synthetic.render(seed=1000 + seed)
            samples.append((f"synthetic-{seed}.png", data, truth, None))
        source = f"SYNTHETIC rendered shapes ({args.synthetic} images)"
    else:
        labels = json.loads((args.dataset / "labels.json").read_text())
        samples = [(i["file"], (args.dataset / i["file"]).read_bytes(), i["potatoes"], i.get("mm_per_px"))
                   for i in labels["images"]]
        source = f"labelled dataset {args.dataset.name} ({len(samples)} images)"
    print(json.dumps(run(samples, source), indent=2))


if __name__ == "__main__":
    main()
