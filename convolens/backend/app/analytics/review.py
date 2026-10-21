"""Human review queue and label accuracy.

Reviewers label conversations blind (no system labels shown), in a fixed pseudo-random order per dataset so the
reviewed set is an unbiased sample. Every stored analysis system (rules, each model and prompt version) is then
scored against those human labels, field by field, with Wilson 95% intervals.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.labels import CORRECTABLE
from app.evaluation.metrics import classification_report
from app.models.orm import Analysis, Conversation, ReviewLabel

FIELDS = ["primary_topic", "resolution_status", "sentiment_start", "sentiment_end", "escalation_requested"]
assert set(FIELDS) == CORRECTABLE
TARGET_REVIEWS = 100


def _order_key(dataset_id: str, conv_key: str) -> str:
    return hashlib.sha256(f"{dataset_id}:{conv_key}".encode()).hexdigest()


def next_items(db: Session, dataset_id: str, n: int = 1) -> list[Conversation]:
    reviewed = set(db.scalars(select(ReviewLabel.conversation_id).where(ReviewLabel.dataset_id == dataset_id)).all())
    convs = db.execute(select(Conversation.id, Conversation.key).where(Conversation.dataset_id == dataset_id)).all()
    todo = sorted((c for c in convs if c.id not in reviewed), key=lambda c: _order_key(dataset_id, c.key))[:n]
    return [db.get(Conversation, c.id) for c in todo]


def reviewed_count(db: Session, dataset_id: str) -> int:
    return db.scalar(select(func.count(func.distinct(ReviewLabel.conversation_id))).where(ReviewLabel.dataset_id == dataset_id)) or 0


def system_labels(db: Session, conv: Conversation) -> dict[str, dict]:
    """Latest successful analysis per system, with the same post-processing activation applies."""
    out: dict[str, dict] = {}
    rows = db.scalars(select(Analysis).where(Analysis.conversation_id == conv.id, Analysis.status == "ok",
                                             Analysis.source_text == "original").order_by(Analysis.id)).all()
    for a in rows:
        name = "rules:" + a.prompt_version if a.method == "rules" else f"llm:{a.model_id}:{a.prompt_version}"
        f = {k: a.fields.get(k) for k in FIELDS}
        if a.method == "llm" and conv.customer_turns < 2:
            f["sentiment_end"] = "unknown"
        if f.get("escalation_requested") in (True, False):
            f["escalation_requested"] = "yes" if f["escalation_requested"] else "no"
        out[name] = f
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def accuracy(db: Session, dataset_id: str) -> dict:
    reviews = db.scalars(select(ReviewLabel).where(ReviewLabel.dataset_id == dataset_id).order_by(ReviewLabel.id)).all()
    # One gold label set per conversation: the earliest review. Later reviews of the same conversation measure
    # inter-reviewer agreement instead.
    gold: dict[int, dict] = {}
    second: list[tuple[dict, dict]] = []
    for r in reviews:
        if r.conversation_id in gold:
            second.append((gold[r.conversation_id], r.labels))
        else:
            gold[r.conversation_id] = r.labels
    stats: dict[str, dict[str, dict]] = defaultdict(dict)
    agg: dict[tuple[str, str], Counter] = defaultdict(Counter)
    pairs: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    confusion: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for cid, labels in gold.items():
        conv = db.get(Conversation, cid)
        for sys_name, pred in system_labels(db, conv).items():
            for f in FIELDS:
                h, p = labels.get(f), pred.get(f)
                if h is None:
                    continue
                c = agg[(sys_name, f)]
                pairs[(sys_name, f)].append((h, p or "missing"))
                c["n"] += 1
                c["agree"] += int(h == p)
                if p == "unknown":
                    c["abstained"] += 1
                else:
                    c["answered"] += 1
                    c["answered_agree"] += int(h == p)
                if h != p:
                    confusion[(sys_name, f)][f"{p} → {h}"] += 1
    for (sys_name, f), c in agg.items():
        stats[sys_name][f] = {
            "n": c["n"], "agree": c["agree"], "accuracy": round(c["agree"] / c["n"], 3) if c["n"] else None,
            "ci95": wilson(c["agree"], c["n"]), "abstained": c["abstained"],
            "precision_when_answered": round(c["answered_agree"] / c["answered"], 3) if c["answered"] else None,
            "answered": c["answered"],
            "top_disagreements": [{"system_to_human": k, "count": v} for k, v in confusion[(sys_name, f)].most_common(3)],
            "classification": classification_report(pairs[(sys_name, f)]),  # human = gold, system = predicted
        }
    inter = None
    if second:
        pairs = [(a.get(f), b.get(f)) for a, b in second for f in FIELDS if a.get(f) is not None and b.get(f) is not None]
        inter = {"pairs": len(pairs), "agreement": round(sum(x == y for x, y in pairs) / len(pairs), 3) if pairs else None}
    return {"reviewed": len(gold), "target": TARGET_REVIEWS, "fields": FIELDS, "systems": dict(stats),
            "inter_reviewer": inter,
            "definitions": {
                "accuracy": "share of reviewed conversations where the system label equals the human label ('unknown' counts as a label)",
                "precision_when_answered": "accuracy restricted to conversations where the system gave a label other than 'unknown'",
                "abstained": "system said 'unknown'",
                "ci95": "Wilson score interval; wide intervals mean too few reviews to compare systems",
                "classification": "per-class precision, recall and F1 with the human label as gold; macro and weighted F1; "
                                  "confusion[gold][predicted]. 'unknown' is a class like any other.",
            }}
