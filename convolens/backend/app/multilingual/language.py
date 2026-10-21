"""Message-level language identification (lingua, restricted language set, deterministic).

Labels are per message, never forced onto a whole conversation: an ISO 639-1 code, ``mixed``
(code-switching detected), a transliteration tag such as ``hi-Latn`` (Romanized Hindi), or ``unknown``.
Language is a property of text only; it is never used to infer nationality, ethnicity or location.
"""
from __future__ import annotations

import re
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

DETECTOR_VERSION = "lingua-2.2+rules-v1"
MIN_LETTERS = 12
MIN_CONFIDENCE = 0.40
MIN_MARGIN = 0.15
MIN_SEGMENT_LETTERS = 15
MIXED_MAX_WHOLE_CONFIDENCE = 0.90
SEGMENT_MIN_CONFIDENCE = 0.60

_LANGS = [Language.ENGLISH, Language.SPANISH, Language.FRENCH, Language.GERMAN, Language.PORTUGUESE, Language.ITALIAN,
          Language.DUTCH, Language.JAPANESE, Language.ARABIC, Language.TURKISH, Language.INDONESIAN, Language.HINDI,
          Language.KOREAN, Language.CHINESE, Language.RUSSIAN, Language.POLISH, Language.SWEDISH, Language.TAGALOG]
_PLACEHOLDER = re.compile(r"\[[A-Z_]+\]|@\S+|#\S+|https?://\S+")
_LETTERS = re.compile(r"[^\W\d_]", re.UNICODE)
_HINGLISH = {"hai", "nahi", "nahin", "kya", "mera", "meri", "mujhe", "kar", "raha", "rahi", "hua", "bhi", "aur",
             "tha", "thi", "kab", "kyun", "abhi", "paisa", "paise", "wapas", "bhai", "yaar", "kuch", "koi", "diya",
             "gaye", "hafte", "bahut", "karo", "aaya", "phir"}


@lru_cache(maxsize=1)
def _detector():
    return LanguageDetectorBuilder.from_languages(*_LANGS).with_preloaded_language_models().build()


def _code(lang: Language) -> str:
    return lang.iso_code_639_1.name.lower()


def _letters(s: str) -> int:
    return len(_LETTERS.findall(s))


def detect_language(text: str) -> dict:
    """Return {language, confidence, detail}."""
    clean = re.sub(r"\s+", " ", _PLACEHOLDER.sub(" ", text or "")).strip()
    detail: dict = {"method": DETECTOR_VERSION}
    if _letters(clean) < MIN_LETTERS:
        return {"language": "unknown", "confidence": None, "detail": {**detail, "reason": "too_short"}}
    words = re.findall(r"[a-z]+", clean.lower())
    hits = sum(1 for w in words if w in _HINGLISH)
    if hits >= 3:
        detail.update(transliteration="hi-Latn", hinglish_markers=hits)
        english = sum(1 for w in words if w in {"refund", "still", "not", "please", "internet", "slow", "the", "my", "is", "works", "thank", "you"})
        if english >= 2:
            return {"language": "mixed", "confidence": None, "detail": {**detail, "components": ["en", "hi-Latn"], "reason": "code_switching_lexicon"}}
        return {"language": "hi-Latn", "confidence": None, "detail": {**detail, "reason": "romanized_lexicon"}}
    det = _detector()
    segs = [(r.language, clean[r.start_index:r.end_index]) for r in det.detect_multiple_languages_of(clean)]
    seg_langs = set()
    for _, seg in segs:
        if _letters(seg) >= MIN_SEGMENT_LETTERS:
            sc = det.compute_language_confidence_values(seg)
            if sc and sc[0].value >= SEGMENT_MIN_CONFIDENCE:
                seg_langs.add(_code(sc[0].language))
    seg_langs = sorted(seg_langs)
    conf = det.compute_language_confidence_values(clean)
    top = conf[0]
    if len(seg_langs) >= 2 and top.value < MIXED_MAX_WHOLE_CONFIDENCE:
        return {"language": "mixed", "confidence": None, "detail": {**detail, "components": seg_langs, "reason": "segment_disagreement"}}
    second = conf[1].value if len(conf) > 1 else 0.0
    if top.value < MIN_CONFIDENCE or top.value - second < MIN_MARGIN:
        return {"language": "unknown", "confidence": round(top.value, 3),
                "detail": {**detail, "reason": "low_confidence", "candidate": _code(top.language)}}
    return {"language": _code(top.language), "confidence": round(top.value, 3), "detail": detail}
