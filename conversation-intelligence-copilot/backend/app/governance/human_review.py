"""Blind human review of message labels and agreement metrics.

Reviewers see a seeded, stratified sample of PII-masked messages without the
system's label, choose a sentiment, and the system computes accuracy, per-class
precision/recall/F1, a confusion matrix and Cohen's kappa against the active
labeller. When two reviewers label the same message, inter-annotator agreement
is reported too. Nothing here is pre-filled: metrics exist only once people
have submitted labels.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sklearn.metrics import cohen_kappa_score, confusion_matrix, precision_recall_fscore_support

from app.analytics.db import AnalyticsDB
from app.config import get_settings

LABELS = ["positive", "neutral", "negative", "mixed"]


class ReviewStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with sqlite3.connect(path) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS review_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT, reviewer TEXT, sentiment TEXT, empathy INTEGER,
                note TEXT, created_at TEXT, UNIQUE(message_id, reviewer))""")

    def add(self, message_id: str, reviewer: str, sentiment: str, empathy: bool | None, note: str | None) -> None:
        if sentiment not in LABELS:
            raise ValueError(f"sentiment must be one of {LABELS}")
        with self._lock, sqlite3.connect(self.path) as c:
            c.execute("INSERT OR REPLACE INTO review_labels (message_id,reviewer,sentiment,empathy,note,created_at) VALUES (?,?,?,?,?,?)",
                      (message_id, reviewer[:40], sentiment, None if empathy is None else int(empathy), (note or "")[:300], datetime.now(UTC).isoformat()))

    def all(self) -> list[dict]:
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT * FROM review_labels ORDER BY id").fetchall()]

    def reviewed_ids(self, reviewer: str) -> set[str]:
        with sqlite3.connect(self.path) as c:
            return {r[0] for r in c.execute("SELECT message_id FROM review_labels WHERE reviewer=?", (reviewer,)).fetchall()}


def sample(db: AnalyticsDB, store: ReviewStore, reviewer: str, n: int = 10, seed: int = 42) -> list[dict]:
    """Stratified by (role, system sentiment) so rare classes are reviewed too. System labels are not returned."""
    done = store.reviewed_ids(reviewer)
    df = db.query(
        """SELECT message_id, speaker_role, masked_text AS text, conversation_id, turn_index FROM (
             SELECT m.*, l.sentiment, ROW_NUMBER() OVER (PARTITION BY m.speaker_role, l.sentiment ORDER BY hash(m.message_id || ?)) AS rn
             FROM messages m JOIN message_labels l USING (message_id) WHERE m.dataset_source='original') WHERE rn <= ?
           ORDER BY hash(message_id || ?)""", [str(seed), max(5, n), str(seed)])
    rows = [r for r in df.to_dict("records") if r["message_id"] not in done]
    return rows[:n]


def metrics(db: AnalyticsDB, store: ReviewStore) -> dict:
    reviews = store.all()
    if not reviews:
        return {"reviews": 0, "status": "no_reviews", "note": "No human labels submitted yet. Use the Governance → Human review panel."}
    ids = sorted({r["message_id"] for r in reviews})
    sys = db.query(f"SELECT message_id, sentiment, empathy, method FROM message_labels WHERE message_id IN ({','.join('?' * len(ids))})", ids)
    sys_map = {r["message_id"]: r for r in sys.to_dict("records")}
    pairs = [(r["sentiment"], sys_map[r["message_id"]]["sentiment"]) for r in reviews if r["message_id"] in sys_map]
    human, system = [p[0] for p in pairs], [p[1] for p in pairs]
    labels = [lab for lab in LABELS if lab in human or lab in system]
    p, rc, f1, sup = precision_recall_fscore_support(human, system, labels=labels, zero_division=0)
    by_msg: dict[str, list[str]] = {}
    for r in reviews:
        by_msg.setdefault(r["message_id"], []).append(r["sentiment"])
    multi = [v[:2] for v in by_msg.values() if len(v) >= 2]
    iaa = None
    if len(multi) >= 5:
        iaa = {"items": len(multi), "percent_agreement": round(sum(a == b for a, b in multi) / len(multi), 4),
               "cohen_kappa": round(float(cohen_kappa_score([a for a, _ in multi], [b for _, b in multi])), 4)}
    disagreements = [{"message_id": r["message_id"], "human": r["sentiment"], "system": sys_map[r["message_id"]]["sentiment"], "reviewer": r["reviewer"]}
                     for r in reviews if r["message_id"] in sys_map and r["sentiment"] != sys_map[r["message_id"]]["sentiment"]]
    return {
        "reviews": len(reviews), "reviewers": len({r["reviewer"] for r in reviews}), "messages": len(ids), "status": "ok",
        "accuracy": round(sum(h == s for h, s in pairs) / len(pairs), 4) if pairs else None,
        "cohen_kappa_vs_system": round(float(cohen_kappa_score(human, system)), 4) if len(set(human + system)) > 1 else None,
        "per_class": [{"label": lab, "precision": round(float(a), 4), "recall": round(float(b), 4), "f1": round(float(c), 4), "support": int(d)}
                      for lab, a, b, c, d in zip(labels, p, rc, f1, sup)],
        "confusion_matrix": {"labels": labels, "rows_human_cols_system": confusion_matrix(human, system, labels=labels).tolist()},
        "inter_annotator": iaa, "disagreements": disagreements[:25],
        "note": "Metrics compare human labels with the active labeller. Sample is small; treat as indicative.",
    }


@lru_cache
def get_review_store() -> ReviewStore:
    return ReviewStore(get_settings().memory_database_path.parent / "human_review.sqlite")
