"""Small text helpers shared by the RAG pipeline, the offline synthesizer and guardrails."""

from __future__ import annotations

import re

STOPWORDS: frozenset[str] = frozenset(
    """a about above after again against all am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers him his how i if in into is it its itself just
    me more most my no nor not of off on once only or other our ours out over own same she should
    so some such than that the their theirs them then there these they this those through to too
    under until up very was we were what when where which while who whom why will with would you
    your yours tell show give please current currently major main any whats what's us let""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def stem(token: str) -> str:
    """Very light suffix stripping so 'risks'/'risk' and 'blocking'/'blocker' align."""
    if token.isdigit():
        return token
    if len(token) > 5 and token.endswith(("sses", "xes", "ches", "shes")):
        return token[:-2]
    for suffix in ("ations", "ation", "ings", "ing", "ers", "er", "ies", "ed", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return token


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    """Lower-case word tokens (optionally without stopwords), lightly stemmed."""
    tokens = _TOKEN_RE.findall(text.lower())
    out: list[str] = []
    for tok in tokens:
        tok = tok.strip(".-")
        # Keep hyphenated identifiers (PHX-214) and also index their parts (RISK-01 -> risk).
        parts = [tok, *tok.split("-")] if "-" in tok else [tok]
        for part in parts:
            if not part or (not keep_stopwords and part in STOPWORDS):
                continue
            out.append(stem(part))
    return out


def content_tokens(text: str) -> set[str]:
    """Set of meaningful tokens used for overlap scoring."""
    return {t for t in tokenize(text) if len(t) > 2 or t.isdigit()}


def split_sentences(text: str) -> list[str]:
    """Split prose and bullet lists into individual sentences/statements."""
    sentences: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        line = re.sub(r"^[-*•]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        for part in _SENTENCE_RE.split(line):
            part = part.strip()
            if part:
                sentences.append(part)
    return sentences


def extract_numbers(text: str) -> set[str]:
    """Numeric literals in a text (used to detect unsupported figures)."""
    out: set[str] = set()
    for n in _NUMBER_RE.findall(text):
        if "." in n:
            n = n.rstrip("0").rstrip(".")  # 5.0 -> 5, 72.50 -> 72.5
        out.add(n)
    return out


def overlap_score(query: str, text: str) -> float:
    """Fraction of query content tokens present in ``text``."""
    q = content_tokens(query)
    if not q:
        return 0.0
    return len(q & content_tokens(text)) / len(q)
