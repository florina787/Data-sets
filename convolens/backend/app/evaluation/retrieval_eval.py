"""Retrieval quality on real data: keyword vs semantic vs hybrid, on a fixed set of paraphrased questions.

    python -m app.evaluation.retrieval_eval --dataset <id> [--k 5] [--out report.json]

Relevance = the hit conversation's primary topic equals the question's target topic, using the dataset's ACTIVE labels.
On a Gemini-labelled dataset these are SILVER judgments (model labels, not human ground truth); the report says which.
Recall@k and full nDCG use the number of conversations with the target topic as the relevant total.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.db import init_db, session_scope
from app.evaluation.metrics import ranking_report
from app.models.orm import Conversation, Dataset
from app.retrieval.index import search, semantic_status

QUESTIONS = Path(__file__).parent / "datasets" / "retrieval_real.jsonl"


def evaluate(dataset_id: str, k: int = 5, modes=("keyword", "semantic", "hybrid")) -> dict:
    qs = [json.loads(l) for l in QUESTIONS.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = {"dataset": dataset_id, "k": k, "questions": len(qs), "modes": {}, "per_query": []}
    with session_scope() as db:
        ds = db.get(Dataset, dataset_id)
        out["judgments"] = ("silver: active labels " + ds.active_analysis) if ds.active_analysis.startswith("llm") \
            else ("rules labels " + ds.active_analysis + " (weak proxy)")
        topic_totals = dict(db.execute(select(Conversation.primary_topic, func.count()).where(
            Conversation.dataset_id == dataset_id).group_by(Conversation.primary_topic)).all())
        out["semantic"] = semantic_status()
        for mode in modes:
            runs, totals = [], []
            for q in qs:
                r = search(db, dataset_id, q["query"], None, k=k, mode=mode)
                if mode != "keyword" and "semantic_faiss" not in r["methods_used"]:
                    out["modes"][mode] = {"unavailable": r.get("semantic_unavailable_reason")}
                    break
                rels = [h["primary_topic"] == q["relevant_topic"] for h in r["hits"]]
                runs.append(rels)
                totals.append(topic_totals.get(q["relevant_topic"], 0))
                out["per_query"].append({"mode": mode, "id": q["id"], "query": q["query"], "target": q["relevant_topic"],
                                         "hits": [{"conversation": h["conversation_key"], "message": h["message_id"],
                                                   "topic": h["primary_topic"], "relevant": rel, "text": h["text"][:140]}
                                                  for h, rel in zip(r["hits"], rels)]})
            else:
                out["modes"][mode] = ranking_report(runs, k, totals)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", required=True)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    init_db()
    rep = evaluate(a.dataset, a.k)
    print(f"Dataset {rep['dataset']} · {rep['questions']} questions · judgments: {rep['judgments']}")
    for mode, m in rep["modes"].items():
        print(f"  {mode:9} {json.dumps(m)}")
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Report written to", a.out)


if __name__ == "__main__":
    main()
