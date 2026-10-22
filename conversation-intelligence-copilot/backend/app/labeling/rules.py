"""Deterministic, versioned labeller.

1. Exact template match against the taxonomy (method="template", confidence 1.0
   *for the mapping*, which is still an analytical judgement; see EVALUATION.md).
2. Otherwise a small lexicon heuristic (method="lexicon", low confidence) so
   appended data with unseen phrasing still gets a provisional label that is
   clearly marked as such.

Conversation-level aggregation rules live here too so the same definitions are
used whichever labeller (rules or Gemini) produced the message labels.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from app.labeling import taxonomy as tx

LABELER_VERSION = "rules-1.0"


@dataclass
class MessageLabel:
    act: str
    sentiment: str
    sentiment_score: float
    empathy: bool
    courtesy: bool
    resolution: str | None
    language: str
    topic: str | None
    product: str | None
    method: str
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


def detect_language(text: str) -> str:
    return "hinglish" if tx.HINGLISH_MARKERS.search(text) else "english"


def parse_opening(text: str) -> tuple[str, str | None, str] | None:
    for topic, language, pattern in tx.OPENING_PATTERNS:
        m = pattern.fullmatch(text.strip())
        if m:
            product = m.group(1) if m.groups() else None
            return topic, product, language
    return None


def label_message(clean_text: str, role: str, turn_index: int) -> MessageLabel:
    text = clean_text.strip()
    if role == "customer" and turn_index == 0:
        parsed = parse_opening(text)
        if parsed:
            topic, product, language = parsed
            sentiment, score = tx.OPENING_SENTIMENT.get(topic, tx.DEFAULT_OPENING_SENTIMENT)
            return MessageLabel("issue_report", sentiment, score, False, False, None, language, topic, product, "template", 1.0)
    act = tx.FOLLOWUP_ACTS.get(text)
    if act and act.role == role:
        return MessageLabel(act.id, act.sentiment, act.score, act.empathy, act.courtesy, act.resolution, act.language, None, None, "template", 1.0)
    return _lexicon_label(text, role, turn_index)


def _lexicon_label(text: str, role: str, turn_index: int) -> MessageLabel:
    neg = len(tx.NEGATIVE_WORDS.findall(text))
    pos = len(tx.POSITIVE_WORDS.findall(text))
    empathy = bool(tx.EMPATHY_WORDS.search(text)) and role == "agent"
    if role == "customer":
        if pos and not neg:
            sentiment, score = "positive", 0.6
        elif neg and not pos:
            sentiment, score = "negative", -0.6
        elif pos and neg:
            sentiment, score = "mixed", 0.0
        else:
            sentiment, score = "neutral", 0.0
    else:
        sentiment, score = "neutral", 0.0
    act = "issue_report" if role == "customer" and turn_index == 0 else ("empathy_acknowledgement" if empathy else "unknown")
    topic = "other" if act == "issue_report" else None
    return MessageLabel(act, sentiment, score, empathy, False, None, detect_language(text), topic, None, "lexicon", 0.4)


# ---------------------------------------------------------------------------
# Conversation-level aggregation
# ---------------------------------------------------------------------------

NEGATIVE_THRESHOLD = -0.25
POSITIVE_THRESHOLD = 0.25


def conversation_sentiment(scores: list[float], sentiments: list[str]) -> str:
    """Conversation label from customer message labels.

    mean <= -0.25 -> negative; mean >= 0.25 -> positive; otherwise mixed when
    both positive and negative customer turns occur, else neutral.
    """
    if not scores:
        return "uncertain"
    mean = sum(scores) / len(scores)
    if mean <= NEGATIVE_THRESHOLD:
        return "negative"
    if mean >= POSITIVE_THRESHOLD:
        return "positive"
    if "positive" in sentiments and "negative" in sentiments:
        return "mixed"
    return "neutral"


def aggregate_conversation(turns: list[dict]) -> dict:
    """`turns`: dicts with speaker_role, turn_index, clean_text and the MessageLabel fields, sorted by turn_index."""
    customer = [t for t in turns if t["speaker_role"] == "customer"]
    agent = [t for t in turns if t["speaker_role"] == "agent"]
    opening = turns[0] if turns and turns[0]["speaker_role"] == "customer" else None
    topic = (opening or {}).get("topic") or "other"
    product = (opening or {}).get("product")

    c_scores = [t["sentiment_score"] for t in customer]
    c_sents = [t["sentiment"] for t in customer]
    followups = customer[1:]

    # Empathy after negative customer turns: does the very next agent turn acknowledge or apologise?
    neg_with_reply = 0
    empathic_replies = 0
    for i, t in enumerate(turns):
        if t["speaker_role"] == "customer" and t["sentiment"] == "negative":
            nxt = next((u for u in turns[i + 1 :] if u["speaker_role"] == "agent"), None)
            if nxt is not None:
                neg_with_reply += 1
                empathic_replies += int(bool(nxt["empathy"]))

    # Missing labels arrive from pandas as NaN (truthy), so test for a real string.
    agent_texts = [t["clean_text"] for t in agent if not isinstance(t.get("resolution"), str)]
    repeats = sum(c - 1 for c in Counter(agent_texts).values() if c > 1)
    resolutions = [t["resolution"] for t in agent if isinstance(t.get("resolution"), str)]
    final_resolution = resolutions[-1] if resolutions else None
    relevant_set = tx.RELEVANT_RESOLUTIONS.get(topic)
    resolution_relevant = None if (final_resolution is None or relevant_set is None) else final_resolution in relevant_set
    last_customer = customer[-1] if customer else None
    opening_lang = (opening or {}).get("language", "english")
    agent_hinglish = sum(1 for t in agent if t["language"] == "hinglish")

    empathy_turns = sum(1 for t in agent if t["empathy"])
    return {
        "topic": topic,
        "product": product,
        "domain": tx.PRODUCT_DOMAINS.get(product or "", "Unknown"),
        "opening_language": opening_lang,
        "sentiment": conversation_sentiment(c_scores, c_sents),
        "sentiment_score_mean": round(sum(c_scores) / len(c_scores), 4) if c_scores else None,
        "first_followup_score": followups[0]["sentiment_score"] if followups else None,
        "last_customer_score": last_customer["sentiment_score"] if last_customer else None,
        "last_customer_act": last_customer["act"] if last_customer else None,
        "negative_turns": sum(1 for s in c_sents if s == "negative"),
        "positive_turns": sum(1 for s in c_sents if s == "positive"),
        "negative_share": round(sum(1 for s in c_sents if s == "negative") / len(c_sents), 4) if c_sents else None,
        "escalation_requests": sum(1 for t in customer if t["act"] == "escalation_request"),
        "urgency_signals": sum(1 for t in customer if t["act"] == "urgency"),
        "confirmed_fixed": any(t["act"] == "confirms_fixed" for t in customer),
        "empathy_turns": empathy_turns,
        "empathy_rate": round(empathy_turns / len(agent), 4) if agent else None,
        "negative_turns_with_reply": neg_with_reply,
        "empathic_replies": empathic_replies,
        "empathy_response_rate": round(empathic_replies / neg_with_reply, 4) if neg_with_reply else None,
        "repeated_agent_phrases": repeats,
        "agent_hinglish_turns": agent_hinglish,
        "final_resolution": final_resolution,
        "resolution_relevant": resolution_relevant,
        "ends_negative": bool(last_customer and last_customer["sentiment"] == "negative"),
        "label_methods": ",".join(sorted({t["method"] for t in turns})),
        "min_label_confidence": min((t["confidence"] for t in turns), default=None),
    }
