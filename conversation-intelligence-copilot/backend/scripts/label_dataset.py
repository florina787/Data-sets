"""Label unique messages with Gemini (resumable). Then rebuild with LABEL_SOURCE=gemini.

Usage (from backend/):
    uv run python -m scripts.label_dataset [--batch-size 25] [--max-items 100]
"""

from __future__ import annotations

import argparse
import json

from app.analytics.db import get_db
from app.config import get_settings
from app.labeling.gemini_labeler import run_labelling
from app.labeling.store import LabelStore
from app.llm.gemini_client import get_llm


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--max-items", type=int, default=None)
    args = ap.parse_args()
    s = get_settings()
    llm = get_llm()
    if not llm.available():
        print(json.dumps({"status": "skipped", "reason": llm.status()["reason"]}, indent=2))
        return
    report = run_labelling(get_db(), llm, LabelStore(s.labels_database_path), args.batch_size, args.max_items,
                           progress=lambda p: print(f"  {p['processed']}/{p['of']} labelled={p['labelled']} failed={p['failed']}", flush=True))
    s.manifests_dir.mkdir(parents=True, exist_ok=True)
    (s.manifests_dir / "labelling_coverage.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
