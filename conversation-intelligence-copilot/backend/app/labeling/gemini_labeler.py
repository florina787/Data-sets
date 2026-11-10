"""Resumable batch labelling with Gemini (the specialised analytical agent).

Labels each *unique* PII-masked (text, role, is_opening) once, in bounded batches,
saving after every batch. Re-running skips texts that already have a valid label
for the current model/prompt/taxonomy versions and retries failed ones up to a
limit. Coverage is reported honestly: fully labelled, failed, and unlabelled.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

from app.analytics.db import AnalyticsDB
from app.labeling.store import LabelStore, text_key
from app.labeling.taxonomy import TOPICS
from app.llm.gemini_client import LLMClient, LLMUnavailable
from app.llm.structured_output import ClassificationBatch
from app.prompts.registry import get_prompt

MAX_ATTEMPTS = 3
CONFIDENCE = {"high": 0.9, "medium": 0.7, "low": 0.4}


def unique_texts(db: AnalyticsDB) -> list[dict]:
    df = db.query(
        """SELECT masked_text AS text, speaker_role AS role, (speaker_role='customer' AND turn_index=0) AS is_opening, COUNT(*) AS occurrences
           FROM messages WHERE dataset_source='original' GROUP BY 1, 2, 3 ORDER BY occurrences DESC, text""")
    return df.to_dict("records")


def to_label(item) -> dict:
    return {
        "act": item.act, "sentiment": item.sentiment, "sentiment_score": float(item.sentiment_score), "empathy": bool(item.empathy),
        "courtesy": bool(item.courtesy), "resolution": None if item.resolution == "none" else item.resolution, "language": item.language,
        "topic": item.topic, "product": item.product, "confidence": CONFIDENCE[item.confidence],
    }


def run_labelling(db: AnalyticsDB, llm: LLMClient, store: LabelStore, batch_size: int = 25, max_items: int | None = None,
                  progress: Callable[[dict], None] | None = None) -> dict:
    prompt = get_prompt("message_classification")
    texts = unique_texts(db)
    todo = []
    already = 0
    exhausted = 0
    for t in texts:
        key = text_key(t["text"], t["role"], bool(t["is_opening"]))
        existing = store.get(key, llm.model, prompt.version)
        if existing and existing["status"] == "valid":
            already += 1
        elif existing and existing["attempts"] >= MAX_ATTEMPTS:
            exhausted += 1
        else:
            todo.append({**t, "key": key})
    if max_items is not None:
        todo = todo[:max_items]
    taxonomy = ", ".join(TOPICS)
    done = failed = 0
    stopped_reason = None
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        payload = json.dumps([{"index": j, "role": b["role"], "is_opening": bool(b["is_opening"]), "text": b["text"]} for j, b in enumerate(batch)],
                             ensure_ascii=False)
        try:
            res = llm.generate_json(prompt, prompt.render(taxonomy=taxonomy, messages=payload), ClassificationBatch, purpose="labelling")
            items = {it.index: it for it in res.parsed.items}  # type: ignore[union-attr]
            for j, b in enumerate(batch):
                if j in items:
                    store.put(b["key"], llm.model, prompt.version, b["text"], b["role"], bool(b["is_opening"]), to_label(items[j]))
                    done += 1
                else:
                    store.put(b["key"], llm.model, prompt.version, b["text"], b["role"], bool(b["is_opening"]), None, "missing from batch output")
                    failed += 1
        except LLMUnavailable as e:
            for b in batch:
                store.put(b["key"], llm.model, prompt.version, b["text"], b["role"], bool(b["is_opening"]), None, str(e)[:300])
            failed += len(batch)
            if not llm.available():
                stopped_reason = f"Stopped: model unavailable ({e})"
                break
        if progress:
            progress({"processed": min(i + batch_size, len(todo)), "of": len(todo), "labelled": done, "failed": failed})
    total = len(texts)
    valid_now = already + done
    occ_total = sum(t["occurrences"] for t in texts)
    valid_keys = set(store.valid_labels())
    occ_valid = sum(t["occurrences"] for t in texts if text_key(t["text"], t["role"], bool(t["is_opening"])) in valid_keys)
    return {
        "run_at": datetime.now(UTC).isoformat(), "model": llm.model, "prompt_version": prompt.version,
        "unique_texts": total, "labelled_before_run": already, "labelled_this_run": done, "failed_this_run": failed,
        "exhausted_retries": exhausted, "unique_text_coverage": round(valid_now / total, 4) if total else 0.0,
        "message_coverage": round(occ_valid / occ_total, 4) if occ_total else 0.0,
        "status": "complete" if valid_now == total else "partial", "stopped_reason": stopped_reason,
    }
