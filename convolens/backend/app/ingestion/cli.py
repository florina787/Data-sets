"""Command-line import and analysis.

    python -m app.ingestion.cli kaggle [--seed 20240601] [--sample-size 3000]   # download with kagglehub, then import
    python -m app.ingestion.cli file /path/to/twcs.csv [--seed N]                # import a local CSV
    python -m app.ingestion.cli analyze <dataset_id> [--limit 200]              # connected model analysis (needs a model)
    python -m app.ingestion.cli embed <dataset_id> [--max-texts 700]          # cache Gemini embeddings of customer messages (capped)
    python -m app.ingestion.cli export-labels out.jsonl                       # model labels by content hash (portable)
    python -m app.ingestion.cli import-labels <dataset_id> in.jsonl          # reuse them on any dataset with the same threads
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
    an.add_argument("--max-requests", type=int, default=None, help="stop after this many model requests (cached batches are free)")
    an.add_argument("--batch-size", type=int, default=15, help="conversations per model request (fewer requests on free tiers)")
    em = sub.add_parser("embed")
    em.add_argument("dataset_id")
    em.add_argument("--max-texts", type=int, default=700, help="texts to embed in this run (free tier bills each text)")
    ex = sub.add_parser("export-labels")
    ex.add_argument("path")
    im = sub.add_parser("import-labels")
    im.add_argument("dataset_id")
    im.add_argument("path")
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
        quota_stops = requests = 0
        t0 = time.time()
        for i in range(0, len(ids), args.batch_size):
            if args.max_requests is not None and requests >= args.max_requests:
                print(f"\nRequest cap of {args.max_requests} reached - stopping. Re-run later to continue.")
                break
            r = analyze_batch(ids[i:i + args.batch_size], model=model)
            requests += int(r["ok"] + r["failed"] > 0)
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
        print(f"\nDone in {time.time() - t0:.0f}s: {requests} model requests, newly labelled {ok}, cached {cached}, failed {failed}")
        if ok + cached == len(ids):
            print("Activation:", activate_llm_analysis(args.dataset_id, EXTRACT_BATCH_VERSION))
        else:
            print(f"Not activated: {ok + cached} of {len(ids)} conversations have model labels. Re-run to finish (cached work is reused).")
    elif args.cmd == "embed":
        from app.models.orm import Message
        from app.retrieval.gemini_embed import GeminiEncoder
        with session_scope() as s:
            texts = s.scalars(select(Message.text).where(Message.dataset_id == args.dataset_id,
                                                         Message.role.in_(GeminiEncoder.roles)).order_by(Message.id)).all()
        enc = GeminiEncoder(max_requests=args.max_texts)
        r = enc.fill(list(texts), pace_s=62)
        print(f"{len(texts)} customer messages: {r['cached_before']} already cached, {r['embedded']} embedded now, "
              f"{r['remaining']} remaining")
    elif args.cmd == "export-labels":
        import json
        from app.models.orm import Analysis
        seen, n = set(), 0
        with session_scope() as s, open(args.path, "w", encoding="utf-8") as fh:
            for a in s.scalars(select(Analysis).where(Analysis.method == "llm", Analysis.status == "ok",
                                                      Analysis.source_text == "original").order_by(Analysis.id)):
                k = (a.content_hash, a.model_id, a.prompt_version)
                if k in seen:
                    continue
                seen.add(k)
                fh.write(json.dumps({"content_hash": a.content_hash, "model_id": a.model_id, "prompt_version": a.prompt_version,
                                     "fields": a.fields}, ensure_ascii=False, sort_keys=True) + "\n")
                n += 1
        print(f"Exported {n} model label sets to {args.path}")
    elif args.cmd == "import-labels":
        import json
        from app.models.orm import Analysis, Conversation
        added = 0
        with session_scope() as s, open(args.path, encoding="utf-8") as fh:
            by_hash: dict[str, list] = {}
            for c in s.scalars(select(Conversation).where(Conversation.dataset_id == args.dataset_id)):
                by_hash.setdefault(c.content_hash, []).append(c)
            for line in fh:
                r = json.loads(line)
                for c in by_hash.get(r["content_hash"], []):
                    exists = s.scalar(select(Analysis.id).where(Analysis.conversation_id == c.id, Analysis.method == "llm",
                                                               Analysis.model_id == r["model_id"], Analysis.prompt_version == r["prompt_version"],
                                                               Analysis.content_hash == r["content_hash"], Analysis.source_text == "original"))
                    if not exists:
                        s.add(Analysis(conversation_id=c.id, method="llm", model_id=r["model_id"], prompt_version=r["prompt_version"],
                                       content_hash=r["content_hash"], source_text="original", fields=r["fields"], status="ok"))
                        added += 1
        print(f"Imported {added} label sets into {args.dataset_id} (existing ones skipped)")
    else:
        with session_scope() as s:
            for d in s.scalars(select(Dataset)):
                print(f"{d.id}  {d.kind:24} {d.status:9} selected={(d.manifest or {}).get('sampling', {}).get('selected')}  {d.name}")


if __name__ == "__main__":
    main()
