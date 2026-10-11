"""Deterministic, local text analysis used by the Document Agent.

This is classic extractive processing (term frequency, regular expressions) — it does not
"understand" documents and makes no model calls.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

STOPWORDS = set(
    """a an and are as at be been but by can do does for from has have if in into is it its may
    must no not of on or our should so than that the their then there these they this to was we
    were will with you your which who when what while all any each more most other such only own
    same also up out over under again further once here both few very s t just don now unless""".split()
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_FIELD_LINE = re.compile(r"^\s*([A-Z][A-Za-z ]{1,30}):\s*(.+?)\s*$")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_PERCENT = re.compile(r"\b\d+(?:\.\d+)?%")


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'-]+", text.lower()) if w not in STOPWORDS]


def body_lines(text: str) -> list[tuple[int, str]]:
    return [(i + 1, line) for i, line in enumerate(text.splitlines())]


def sentences_with_lines(text: str) -> list[tuple[int, str]]:
    """Split prose (non-heading, non-field) lines into sentences, keeping line numbers."""
    result: list[tuple[int, str]] = []
    for number, line in body_lines(text):
        stripped = line.strip().lstrip("-• ").strip()
        if not stripped or stripped.startswith("#") or _FIELD_LINE.match(line):
            continue
        for sentence in _SENTENCE_SPLIT.split(stripped):
            if len(sentence.split()) >= 5:
                result.append((number, sentence.strip()))
    return result


def extractive_summary(text: str, max_sentences: int = 3) -> list[dict[str, Any]]:
    """Pick the highest-scoring sentences by normalised term frequency, in document order."""
    sentences = sentences_with_lines(text)
    if not sentences:
        return []
    freq = Counter(_words(" ".join(s for _, s in sentences)))
    top = max(freq.values()) if freq else 1
    scored = []
    for index, (line, sentence) in enumerate(sentences):
        words = _words(sentence)
        score = sum(freq[w] / top for w in words) / (len(words) or 1)
        scored.append((score, index, line, sentence))
    chosen = sorted(sorted(scored, key=lambda s: (-s[0], s[1]))[:max_sentences], key=lambda s: s[1])
    return [{"line": line, "sentence": sentence, "score": round(score, 3)} for score, _, line, sentence in chosen]


def extract_fields(text: str, wanted: list[str] | None = None) -> list[dict[str, Any]]:
    fields = []
    for number, line in body_lines(text):
        match = _FIELD_LINE.match(line)
        if not match:
            continue
        label, value = match.group(1).strip(), match.group(2).strip()
        if wanted is None or label in wanted:
            fields.append({"field": label, "value": value, "line": number})
    return fields


def extract_entities(text: str) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {"dates": [], "amounts": [], "percentages": []}
    for number, line in body_lines(text):
        for key, pattern in (("dates", _DATE), ("amounts", _MONEY), ("percentages", _PERCENT)):
            for match in pattern.findall(line):
                found[key].append({"value": match, "line": number})
    return found


def extract_sections(text: str) -> list[dict[str, Any]]:
    return [
        {"heading": line.lstrip("#").strip(), "line": number, "level": len(line) - len(line.lstrip("#"))}
        for number, line in body_lines(text)
        if line.startswith("#")
    ]


def extract_action_items(text: str) -> list[dict[str, Any]]:
    items = []
    for number, line in body_lines(text):
        stripped = line.strip().lstrip("-• ").strip()
        if stripped.lower().startswith(("action:", "decision:")):
            items.append({"kind": stripped.split(":", 1)[0].title(), "text": stripped.split(":", 1)[1].strip(), "line": number})
    return items


def top_keywords(text: str, limit: int = 8) -> list[tuple[str, int]]:
    return Counter(_words(text)).most_common(limit)


def find_terms(text: str, terms: list[str]) -> list[dict[str, Any]]:
    """Locate glossary terms (case-insensitive) and return the first line each appears on."""
    hits = []
    lowered = [(n, l.lower()) for n, l in body_lines(text)]
    for term in terms:
        for number, line in lowered:
            if term.lower() in line:
                hits.append({"term": term, "line": number})
                break
    return hits


def document_stats(text: str) -> dict[str, int]:
    words = re.findall(r"\S+", text)
    return {
        "characters": len(text),
        "words": len(words),
        "lines": len(text.splitlines()),
        "reading_minutes": max(1, round(len(words) / 200)),
    }
