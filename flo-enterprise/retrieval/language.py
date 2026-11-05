"""Lightweight language detection (script + stop-word heuristics) for en, fr, es, hi, ta, ko."""
from __future__ import annotations

import re

STOP = {
    "en": {"the", "and", "is", "of", "to", "what", "which", "why", "how", "for", "with", "are", "my", "our", "did"},
    "fr": {"le", "la", "les", "des", "est", "et", "pour", "quel", "quelle", "pourquoi", "avec", "une", "du", "aux", "nos"},
    "es": {"el", "la", "los", "las", "es", "y", "para", "qué", "por", "con", "una", "del", "cuál", "nuestros", "cómo"},
}


def detect_language(text: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if re.search(r"[஀-௿]", text):
        return "ta"
    if re.search(r"[가-힯ᄀ-ᇿ]", text):
        return "ko"
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    scores = {k: sum(w in v for w in words) for k, v in STOP.items()}
    if re.search(r"[¿¡ñ]", text):
        scores["es"] += 2
    if re.search(r"[çœèêë]", text):
        scores["fr"] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "en"
