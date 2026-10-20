"""Rules-based conversation analysis (method = "rules", prompt_version = RULES_VERSION).

Transparent keyword/lexicon rules. Used for the Demonstration mode and as a labelled, inspectable
baseline on imported data. Every label carries exact evidence spans from the redacted text. Lexicons
cover en/es/fr/de only; messages in other languages receive ``unknown`` rather than a guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.analytics.taxonomy import OTHER, RULES_LANGUAGES, TOPICS, UNKNOWN

RULES_VERSION = "rules-v1"


@dataclass
class Msg:
    source_id: str
    role: str  # customer | support
    text: str
    language: str = "unknown"


def _rx(words: list[str]) -> re.Pattern:
    # Whole-word match; a trailing "*" marks a stem (prefix match), e.g. "overcharg*".
    parts = [re.escape(w[:-1]) + r"\w*" if w.endswith("*") else re.escape(w) for w in sorted(words, key=len, reverse=True)]
    return re.compile(r"(?<![\w])(" + "|".join(parts) + r")(?![\w])", re.IGNORECASE)


_TOPIC_RX = {k: _rx(v["keywords"]) for k, v in TOPICS.items()}
_SUB_RX = {k: {s: _rx(ws) for s, ws in v["subthemes"].items()} for k, v in TOPICS.items()}

_CONFIRM = _rx(["thanks, that worked", "that worked", "it worked", "works now", "working now", "all sorted", "sorted now",
                "fixed now", "it's fixed", "problem solved", "resolved", "all good now", "perfect, thank", "got it, thank",
                "received it", "refund arrived", "thank you so much", "thanks so much", "great, thanks", "thanks for the help",
                "thanks for your help", "gracias, ya funciona", "ya funciona", "merci, ça marche", "ça marche", "danke, es funktioniert",
                "funktioniert jetzt"])
_UNRESOLVED = _rx(["still not", "still no", "still waiting", "still having", "still doesn't", "still isn't", "still broken",
                   "not fixed", "not resolved", "didn't help", "did not help", "didn't work", "doesn't work", "does not work",
                   "same problem", "same issue", "nothing has changed", "no one has", "nobody has", "useless", "no response",
                   "haven't heard", "hasn't arrived", "never received", "sigue sin", "todavía no", "toujours pas",
                   "immer noch nicht", "funktioniert nicht", "no funciona", "ne fonctionne pas"])
_SOLUTION = _rx(["please try", "try restarting", "try to", "please update", "please reinstall", "please clear", "please check",
                 "please follow", "follow these steps", "here's how", "we've refunded", "we have refunded", "refund has been",
                 "we've processed", "has been processed", "we've issued", "we've sent", "we have sent", "we've fixed",
                 "has been fixed", "we've reset", "you can reset", "reset your", "go to settings", "visit", "rebooked",
                 "we've rebooked", "credit has been", "has been applied", "por favor intenta", "hemos procesado",
                 "veuillez essayer", "nous avons", "bitte versuchen", "wir haben"])
_CLARIFY = _rx(["dm us", "send us a dm", "send us a direct message", "can you dm", "please dm", "could you tell us",
                "can you confirm", "what is your", "which device", "can you share", "let us know", "follow and dm",
                "envíanos un dm", "envoyez-nous", "schick uns"])
_ESCALATE = _rx(["manager", "supervisor", "escalat*", "formal complaint", "file a complaint", "complaint",
                 "speak to someone", "speak to a human", "real person", "ombudsman", "legal action", "lawyer", "regulator",
                 "reclamación", "queja", "réclamation", "plainte", "beschwerde"])
_NEG = _rx(["terrible", "awful", "worst", "angry", "furious", "frustrated", "frustrating", "annoyed", "ridiculous", "unacceptable",
            "disappointed", "useless", "horrible", "hate", "fed up", "joke", "pathetic", "still waiting", "nobody", "never",
            "broken", "not working", "doesn't work", "rude", "scam", "ridiculous", "terrible", "frustrat*", "😡", "😠", "🙄", "😤",
            "terrible", "pésimo", "horrible", "nul", "inacceptable", "schrecklich", "unverschämt", "enttäuscht"])
_POS = _rx(["thanks", "thank you", "great", "awesome", "appreciate", "love", "perfect", "helpful", "amazing", "excellent",
            "brilliant", "happy", "glad", "works now", "😊", "🙏", "👍", "❤", "gracias", "genial", "merci", "super", "danke", "toll"])
_REFUND_INTENT = _rx(["refund", "money back", "reembolso", "remboursement", "rückerstattung"])
_STATUS_INTENT = _rx(["where is", "when will", "status", "tracking", "dónde está", "où est", "wo ist"])
_CANCEL_INTENT = _rx(["cancel", "cancelar", "résilier", "kündigen", "close my account"])


def _span(m: Msg, rx: re.Pattern, supports: str, widen: int = 40) -> dict | None:
    hit = rx.search(m.text)
    if not hit:
        return None
    start = max(0, hit.start() - widen)
    end = min(len(m.text), hit.end() + widen)
    # Snap to word boundaries for readability; quote remains an exact substring.
    while start > 0 and not m.text[start - 1].isspace():
        start -= 1
    while end < len(m.text) and not m.text[end].isspace():
        end += 1
    return {"message_id": m.source_id, "start": start, "end": end, "quote": m.text[start:end], "supports": supports}


def _covered(m: Msg) -> bool:
    return m.language in RULES_LANGUAGES or (m.language == "mixed")


def _sentiment(m: Msg | None) -> tuple[str, dict | None]:
    if m is None or not _covered(m):
        return "unknown", None
    neg = len(_NEG.findall(m.text))
    pos = len(_POS.findall(m.text))
    if neg > pos:
        return "negative", _span(m, _NEG, "sentiment")
    if pos > neg:
        return "positive", _span(m, _POS, "sentiment")
    return "neutral", None


def message_stages(msgs: list[Msg]) -> list[str]:
    """Inferred journey stage per message (rules), in chronological order."""
    stages: list[str] = []
    seen_support = False
    for i, m in enumerate(msgs):
        if m.role == "customer":
            if i == 0:
                stages.append("problem")
            elif _ESCALATE.search(m.text):
                stages.append("escalation")
            elif seen_support and (_CONFIRM.search(m.text) or _UNRESOLVED.search(m.text)):
                stages.append("outcome")
            else:
                stages.append("follow_up")
        else:
            seen_support = True
            if _SOLUTION.search(m.text):
                stages.append("support_action")
            elif _CLARIFY.search(m.text) or "?" in m.text:
                stages.append("clarification")
            else:
                stages.append("support_action")
    return stages


def analyze(msgs: list[Msg]) -> dict:
    """Analyse one conversation (messages in chronological order)."""
    evidence: list[dict] = []
    customer = [m for m in msgs if m.role == "customer"]
    support = [m for m in msgs if m.role == "support"]
    cust_text = "\n".join(m.text for m in customer)

    # Topics: score keyword hits in customer messages (first message weighted double).
    scores: dict[str, int] = {}
    for k, rx in _TOPIC_RX.items():
        s = sum(len(rx.findall(m.text)) * (2 if i == 0 else 1) for i, m in enumerate(customer))
        if s:
            scores[k] = s
    ranked = sorted(scores, key=lambda k: (-scores[k], k))
    if ranked:
        primary = ranked[0]
        secondary = ranked[1:3]
        for k in ranked[:3]:
            for m in customer:
                sp = _span(m, _TOPIC_RX[k], f"topic:{k}")
                if sp:
                    evidence.append(sp)
                    break
    else:
        primary = OTHER if customer and all(_covered(m) for m in customer) else UNKNOWN
        secondary = []
    subtheme = None
    if primary in _SUB_RX:
        best = max(_SUB_RX[primary].items(), key=lambda kv: len(kv[1].findall(cust_text)), default=None)
        if best and best[1].search(cust_text):
            subtheme = best[0]

    # Resolution: the last customer message after a support reply is the strongest signal.
    resolution = "unknown"
    last_support_idx = max((i for i, m in enumerate(msgs) if m.role == "support"), default=-1)
    first_support_idx = min((i for i, m in enumerate(msgs) if m.role == "support"), default=-1)
    after = [m for i, m in enumerate(msgs) if m.role == "customer" and first_support_idx >= 0 and i > first_support_idx]
    if after:
        last = after[-1]
        if _UNRESOLVED.search(last.text):
            resolution = "unresolved_explicit"
            evidence.append(_span(last, _UNRESOLVED, "resolution_status"))
        elif _CONFIRM.search(last.text):
            resolution = "resolved_confirmed"
            evidence.append(_span(last, _CONFIRM, "resolution_status"))
    if resolution == "unknown":
        offered = next((m for m in support if _SOLUTION.search(m.text)), None)
        if offered:
            resolution = "solution_offered_unconfirmed"
            evidence.append(_span(offered, _SOLUTION, "resolution_status"))

    # Escalation request by the customer.
    esc_msg = next((m for m in customer if _ESCALATE.search(m.text)), None)
    if esc_msg:
        escalation = "yes"
        evidence.append(_span(esc_msg, _ESCALATE, "escalation_requested"))
    else:
        escalation = "no" if customer and all(_covered(m) for m in customer) else "unknown"

    s_start, ev1 = _sentiment(customer[0] if customer else None)
    s_end, ev2 = _sentiment(customer[-1] if len(customer) > 1 else None)
    if len(customer) == 1:
        s_end = "unknown"  # no later customer turn to observe
    for ev in (ev1, ev2):
        if ev:
            evidence.append(ev)

    if _REFUND_INTENT.search(cust_text):
        intent = "request_refund"
    elif _CANCEL_INTENT.search(cust_text):
        intent = "cancel_service"
    elif _STATUS_INTENT.search(cust_text):
        intent = "ask_status"
    elif esc_msg or (s_start == "negative" and primary == "service_experience"):
        intent = "complain"
    elif customer:
        intent = "report_problem" if primary not in (OTHER, UNKNOWN) else "request_help"
    else:
        intent = "unknown"

    first = customer[0].text if customer else ""
    action = next((m.text for m in support if _SOLUTION.search(m.text)), support[0].text if support else "")
    from app.analytics.taxonomy import RESOLUTION, topic_label
    summary = (
        f"Customer raised a {topic_label(primary).lower()} issue"
        + (f" ({subtheme.replace('_', ' ')})" if subtheme else "")
        + f". Support replied {len(support)} time(s). Outcome label: {RESOLUTION[resolution].lower()}."
    )
    claims = [
        {"kind": "observed", "text": f"{len(customer)} customer and {len(support)} support messages in this thread."},
        {"kind": "inference", "text": f"Rules classify the topic as {topic_label(primary)} and the outcome as {RESOLUTION[resolution]}."},
    ]
    return {
        "primary_topic": primary,
        "secondary_topics": secondary,
        "subtheme": subtheme,
        "customer_intent": intent,
        "sentiment_start": s_start,
        "sentiment_end": s_end,
        "resolution_status": resolution,
        "escalation_requested": escalation,
        "summary": summary,
        "reported_problem": first[:400],
        "support_action": action[:400],
        "evidence": [e for e in evidence if e],
        "claims": claims,
        "analysis_method": "rules",
        "model_id": None,
        "prompt_version": RULES_VERSION,
    }


def validate_evidence(evidence: list[dict], texts: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Split evidence into (valid, invalid). A span is valid only if the quote is an exact substring of the
    stored redacted text of a message in this conversation. Offsets are (re)computed from the stored text."""
    valid, invalid = [], []
    for e in evidence:
        mid = str(e.get("message_id", ""))
        quote = e.get("quote") or ""
        text = texts.get(mid)
        if text is None or not quote.strip():
            invalid.append({**e, "error": "unknown message" if text is None else "empty quote"})
            continue
        start = e.get("start")
        if isinstance(start, int) and text[start:start + len(quote)] == quote:
            valid.append({**e, "start": start, "end": start + len(quote)})
            continue
        idx = text.find(quote)
        if idx < 0:
            invalid.append({**e, "error": "quote not found in stored text"})
        else:
            valid.append({**e, "start": idx, "end": idx + len(quote)})
    return valid, invalid
