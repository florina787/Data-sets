"""Evaluate the potato detector and grader, and record the result in the model registry.

Usage:
    .venv/bin/python scripts/eval_vision.py --synthetic 20
        rendered shapes (checks the pipeline; says nothing about real potatoes)
    .venv/bin/python scripts/eval_vision.py --dataset path/to/folder --name farm-photos --version 1 \\
        --license "CC-BY-4.0" --source "Own photos, line 2, March 2026"
        real labelled photos in COCO format: folder/annotations.json + images. Boxes are
        [x, y, width, height]; an optional per-box "attributes": {"grade": "Good|Moderate|Not Good"}
        enables grading metrics. Images may carry "batch" or "session" to keep groups together.

Splits are made per acquisition group (never per image) and near-duplicate photos are
merged before splitting. The test split is evaluated. Results appear in the Model Evaluation Lab.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ml import datasets, evaluate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--synthetic", type=int, metavar="N", help="evaluate on N rendered synthetic images")
    group.add_argument("--dataset", type=Path, help="folder with annotations.json (COCO) and images")
    parser.add_argument("--name", help="dataset name (with --dataset)")
    parser.add_argument("--version", default="1", help="dataset version (with --dataset)")
    parser.add_argument("--license", default="", help="dataset licence (required with --dataset)")
    parser.add_argument("--source", default="", help="where the images came from (required with --dataset)")
    args = parser.parse_args()
    if args.synthetic:
        dataset_id = datasets.ensure_synthetic(n=args.synthetic)
        report = {"dataset_id": dataset_id}
    else:
        report = datasets.import_coco(args.dataset, args.name or args.dataset.name, args.version, args.license,
                                      args.source)
        dataset_id = report["dataset_id"]
    result = evaluate.run(dataset_id, "test")
    print(json.dumps({"dataset": report, "detection": result["detection"], "grading": result["grading"]}, indent=2))


if __name__ == "__main__":
    main()
