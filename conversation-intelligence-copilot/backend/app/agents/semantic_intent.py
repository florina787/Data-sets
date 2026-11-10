"""Semantic intent matching over a labelled example set (separate from the conversation index).

The examples are the *train* split of the intent benchmark (app/agents/data/intent_examples.json),
embedded with the same MiniLM model the retrieval layer uses, but held in their own small
in-memory matrix. Nothing here touches the customer-conversation FAISS index.

For a question we take, per intent, the highest cosine similarity to any of its examples, then
report the top candidates and the margin between the best and second-best *intent*. A match is
accepted only when similarity and margin both clear thresholds calibrated on the validation split
(app/agents/data/intent_router_config.json). Similarities are ranking scores, not probabilities;
they are never shown as confidence.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"
EXAMPLES = DATA / "intent_examples.json"
CONFIG = DATA / "intent_router_config.json"
_lock = threading.Lock()


def normalise(q: str) -> str:
    """Entity values carry no intent signal; replace them so 'C0000479' and 'C0001673' look the same."""
    q = re.sub(r"\bC\d{7}\b", "conversation", q, flags=re.I)
    q = re.sub(r"\bAgent[A-Za-z]{4}\b", "this agent", q)
    return " ".join(q.split())


@dataclass
class SemanticMatch:
    candidates: list[tuple[str, float]] = field(default_factory=list)  # (intent, best similarity), best first
    margin: float = 0.0
    accepted: bool = False
    thresholds: dict = field(default_factory=dict)
    nearest_example: str = ""
    available: bool = True
    note: str = ""

    @property
    def top(self) -> str | None:
        return self.candidates[0][0] if self.candidates else None

    @property
    def similarity(self) -> float:
        return self.candidates[0][1] if self.candidates else 0.0


class SemanticIntentIndex:
    def __init__(self, examples: list[dict], encoder):
        self.labels = [e["intent"] for e in examples]
        self.texts = [e["question"] for e in examples]
        self._encode = encoder
        self.matrix = encoder([normalise(t) for t in self.texts])
        self.intents = sorted(set(self.labels))

    def match(self, question: str, thresholds: dict) -> SemanticMatch:
        v = self._encode([normalise(question)])[0]
        sims = self.matrix @ v
        best: dict[str, tuple[float, int]] = {}
        for i, (lab, s) in enumerate(zip(self.labels, sims)):
            if lab not in best or s > best[lab][0]:
                best[lab] = (float(s), i)
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])
        cands = [(lab, round(s, 4)) for lab, (s, _) in ranked[:3]]
        margin = round(ranked[0][1][0] - ranked[1][1][0], 4) if len(ranked) > 1 else 1.0
        tau, mu = thresholds.get("min_similarity", 1.1), thresholds.get("min_margin", 1.1)
        return SemanticMatch(candidates=cands, margin=margin, accepted=cands[0][1] >= tau and margin >= mu,
                             thresholds={"min_similarity": tau, "min_margin": mu}, nearest_example=self.texts[ranked[0][1][1]])


def _encoder():
    from app.config import get_settings
    from app.retrieval.embeddings import SentenceTransformerEmbedder

    emb = SentenceTransformerEmbedder(get_settings().embedding_model)
    return emb.encode


def load_config() -> dict:
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {"min_similarity": 1.1, "min_margin": 1.1, "note": "not calibrated"}


@lru_cache
def get_semantic_index() -> SemanticIntentIndex | None:
    """None when the sentence-transformers model is unavailable (the router then skips this stage)."""
    with _lock:
        try:
            examples = json.loads(EXAMPLES.read_text())
            return SemanticIntentIndex(examples, _encoder())
        except Exception:  # noqa: BLE001 - missing model / package: semantic stage is optional
            return None


def semantic_match(question: str) -> SemanticMatch:
    idx = get_semantic_index()
    if idx is None:
        return SemanticMatch(available=False, note="sentence-transformers model unavailable")
    return idx.match(question, load_config())
