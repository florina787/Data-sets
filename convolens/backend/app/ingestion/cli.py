"""Command-line import and analysis.

    python -m app.ingestion.cli kaggle [--seed 20240601] [--sample-size 3000]   # download with kagglehub, then import
    python -m app.ingestion.cli file /path/to/twcs.csv [--seed N]                # import a local CSV
    python -m app.ingestion.cli analyze <dataset_id> [--limit 200]              # connected model analysis (needs a model)
    python -m app.ingestion.cli list                                            # datasets and actual counts
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import init_db, session_scope
from app.ingestion.importer import run_import
from app.ingestion.jobs import KAGGLE_DATASET
from app.models.orm import Dataset


def _progress(stage: str, p: float) -> None:
    sys.stdout.write(f"\r[{p * 100:5.1f}%] {stage:<60}")
    sys.stdout.flush()


def _import(path: Path, source: str, args) -> None:
    ds = run_import(path, kind="kaggle_twcs", name=args.name, source_label=source, synthetic=False, seed=args.seed,
                    sample_size=args.sample_size, progress=_progress)
    print()
    with session_scope() as s:
        m = s.get(Dataset, ds).manifest
    smp = m["sampling"]
    print(f"Dataset {ds}: selected {smp['selected']} of {smp['eligible']} eligible threads (requested {smp['requested']}, seed {smp['seed']})")
    print(f"Rows read {m['counts']['rows_read']}, unique messages {m['counts']['unique_messages']}, threads {m['counts']['threads_total']}")
    print("Exclusions:", ", ".join(f"{k}={v}" for k, v in m["exclusions"].items()))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("kaggle", "file"):
        sp = sub.add_parser(name)
        if name == "file":
            sp.add_argument("path")
        sp.add_argument("--seed", type=int, default=None)
        sp.add_argument("--sample-size", type=int, default=None)
        sp.add_argument("--name", default="Customer Support on Twitter (Kaggle)")
    an = sub.add_parser("analyze")
    an.add_argument("dataset_id")
    an.add_argument("--limit", type=int, default=None)
    an.add_argument("--batch-size", type=int, default=15, help="conversations per model request (fewer requests on free tiers)")
    sub.add_parser("list")
    args = p.parse_args()
    init_db()
    if args.cmd == "kaggle":
        import kagglehub
        root = Path(kagglehub.dataset_download(KAGGLE_DATASET))
        found = sorted(root.rglob("twcs.csv")) or sorted(root.rglob("*.csv"))
        if not found:
            sys.exit(f"No CSV found under {root}")
        print("Downloaded:", found[0])
        _import(found[0], f"kaggle:{KAGGLE_DATASET}", args)
    elif args.cmd == "file":
        _import(Path(args.path), f"local:{Path(args.path).name}", args)
    elif args.cmd == "analyze":
        import time
        from app.analytics.extractor import activate_llm_analysis, analyze_batch
        from app.graph.prompts import EXTRACT_BATCH_VERSION
        from app.llm.provider import get_chat_model
        from app.models.orm import Conversation
        model = get_chat_model()
        with session_scope() as s:
            ids = s.scalars(select(Conversation.id).where(Conversation.dataset_id == args.dataset_id).order_by(Conversation.key)).all()
        ids = ids[: args.limit] if args.limit else ids
        ok = failed = cached = 0
        quota_stops = 0
        t0 = time.time()
        for i in range(0, len(ids), args.batch_size):
            r = analyze_batch(ids[i:i + args.batch_size], model=model)
            ok, failed, cached = ok + r["ok"], failed + r["failed"], cached + r["cached"]
            err = r.get("error") or ""
            _progress(f"{min(i + args.batch_size, len(ids))}/{len(ids)} ok={ok} cached={cached} failed={failed}", min(i + args.batch_size, len(ids)) / len(ids))
            if "429" in err or "quota" in err.lower():
                quota_stops += 1
                print(f"\nQuota/rate limit hit: {err[:300]}")
                if "PerDay" in err or quota_stops >= 3:
                    print("Daily quota exhausted - stopping. Re-run later: cached conversations are skipped.")
                    break
                time.sleep(65)
        print(f"\nDone in {time.time() - t0:.0f}s: newly labelled {ok}, cached {cached}, failed {failed}")
        if ok + cached == len(ids):
            print("Activation:", activate_llm_analysis(args.dataset_id, EXTRACT_BATCH_VERSION))
        else:
            print(f"Not activated: {ok + cached} of {len(ids)} conversations have model labels. Re-run to finish (cached work is reused).")
    else:
        with session_scope() as s:
            for d in s.scalars(select(Dataset)):
                print(f"{d.id}  {d.kind:24} {d.status:9} selected={(d.manifest or {}).get('sampling', {}).get('selected')}  {d.name}")


if __name__ == "__main__":
    main()
