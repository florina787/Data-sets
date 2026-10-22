"""Prepare the dataset: ingest, validate, normalize, label and build analytics.duckdb.

Usage (from backend/):  uv run python -m scripts.prepare_dataset
"""

from __future__ import annotations

import json

from app.data.pipeline import run


def main() -> None:
    result = run()
    m = result["manifest"]
    print(json.dumps({"tables": m["tables"], "label_coverage": m["label_coverage"], "duration_seconds": m["duration_seconds"]}, indent=2))
    print("Data quality:", result["quality"]["overall"])
    for c in result["quality"]["checks"]:
        if c["count"]:
            print(f"  [{c['severity']}] {c['check']}: {c['count']} / {c['total']}")


if __name__ == "__main__":
    main()
