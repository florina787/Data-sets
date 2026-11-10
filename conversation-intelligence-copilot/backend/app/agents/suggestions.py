"""Nudges: the answerable questions closest to what the analyst asked.

When a question cannot be answered from the dataset (a refusal, a clarification, or a model's
general-knowledge answer), the reply ends with up to three questions the copilot *can* answer.
They are chosen by MiniLM similarity between the analyst's question (plus, with less weight,
their recent questions in the session) and the labelled intent examples, then mapped to one
canonical phrasing per analysis. Every canonical question is routed by a high-precision rule
(tests/unit/test_suggestions.py checks this), so a suggestion always runs a real analysis.
"""

from __future__ import annotations

import numpy as np

from app.agents.semantic_intent import get_semantic_index, normalise

CANONICAL = {
    "negative_topics": "What were the top 5 topics most associated with negative sentiment last month?",
    "leadership_priorities": "Which recurring customer concerns should leadership review first?",
    "agent_coaching": "Which support agents may benefit from coaching on empathy?",
    "root_cause": "Why is duplicate charge so negative?",
    "sentiment_distribution": "What is the overall sentiment mix across conversations?",
    "sentiment_trend": "Show the sentiment trend over time.",
    "topic_frequency": "What are the most common topics customers contact support about?",
    "resolution_quality": "Does the agent's closing action fit the customer's issue, by topic?",
    "sentiment_trajectory": "How did customer sentiment change in conversation C0000479?",
    "conversation_xray": "X-ray conversation C0000479",
    "similar_conversations": "Find conversations similar to C0000479.",
    "compare_topics": "Compare duplicate charge and coupon not applying.",
    "dataset_overview": "What does the dataset cover?",
}
DEFAULT = ["What were the top 5 topics most associated with negative sentiment last month?",
           "Which recurring customer concerns should leadership review first?",
           "How did customer sentiment change in conversation C0000479?"]
HISTORY_WEIGHT = 0.3  # the current question dominates; recent questions only break ties


def suggest(question: str, history: list[str] | None = None, k: int = 3) -> list[str]:
    idx = get_semantic_index()
    if idx is None:
        return DEFAULT[:k]
    texts = [question] + [h for h in (history or [])[-2:] if h and h != question]
    vecs = idx._encode([normalise(t) for t in texts])
    sims = idx.matrix @ vecs[0]
    if len(texts) > 1:
        sims = sims + HISTORY_WEIGHT * np.mean(idx.matrix @ np.asarray(vecs[1:]).T, axis=1)
    best: dict[str, float] = {}
    for lab, s in zip(idx.labels, sims):
        if lab in CANONICAL and s > best.get(lab, -9.0):
            best[lab] = float(s)
    ranked = sorted(best, key=lambda lab: -best[lab])
    return [CANONICAL[lab] for lab in ranked[:k]] or DEFAULT[:k]
