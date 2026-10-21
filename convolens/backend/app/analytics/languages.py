"""Language Intelligence: message-level language counts, coverage, reviewed quality and guarded comparisons."""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.taxonomy import RESOLUTION, topic_label
from app.config import get_settings
from app.models.orm import Conversation, Correction, EvalRun, Message, Translation


def dashboard(db: Session, dataset_id: str) -> dict:
    min_n = get_settings().min_group_size
    msg_counts = dict(db.execute(select(Message.language, func.count()).where(Message.dataset_id == dataset_id)
                                 .group_by(Message.language)).all())
    corrected = db.scalar(select(func.count()).where(Message.dataset_id == dataset_id, Message.language_corrected.is_(True))) or 0
    by_role = defaultdict(Counter)
    for lang, role, n in db.execute(select(Message.language, Message.role, func.count()).where(Message.dataset_id == dataset_id)
                                    .group_by(Message.language, Message.role)).all():
        by_role[lang][role] = n
    # Group conversations by the language of the FIRST customer message (stated explicitly in the UI).
    first = {}
    for cid, lang in db.execute(select(Message.conversation_id, Message.language).where(Message.dataset_id == dataset_id, Message.role == "customer")
                                .order_by(Message.conversation_id, Message.position)).all():
        first.setdefault(cid, lang)
    convs = db.execute(select(Conversation.id, Conversation.primary_topic, Conversation.resolution_status, Conversation.sentiment_end,
                              Conversation.languages).where(Conversation.dataset_id == dataset_id)).all()
    groups: dict[str, list] = defaultdict(list)
    multi_lang = 0
    for c in convs:
        groups[first.get(c.id, "unknown")].append(c)
        if len([l for l in c.languages if l != "unknown"]) > 1:
            multi_lang += 1
    group_rows = []
    for lang, cs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        n = len(cs)
        known_topic = sum(1 for c in cs if c.primary_topic != "unknown")
        known_res = sum(1 for c in cs if c.resolution_status != "unknown")
        known_sent = sum(1 for c in cs if c.sentiment_end != "unknown")
        unresolved = sum(1 for c in cs if c.resolution_status == "unresolved_explicit")
        topics = Counter(c.primary_topic for c in cs)
        row = {"language": lang, "conversations": n,
               "coverage": {"topic": {"known": known_topic, "n": n}, "resolution": {"known": known_res, "n": n},
                            "sentiment_end": {"known": known_sent, "n": n}},
               "topic_mix": [{"key": k, "label": topic_label(k), "count": v} for k, v in topics.most_common(4)],
               "comparison_allowed": n >= min_n and known_res >= min_n}
        if row["comparison_allowed"]:
            row["explicitly_unresolved"] = {"numerator": unresolved, "denominator": known_res, "unknown": n - known_res}
        else:
            row["suppressed_reason"] = f"Fewer than {min_n} conversations with known outcomes; outcome rate not shown."
        group_rows.append(row)
    evals = db.scalars(select(EvalRun).where(EvalRun.suite.in_(["language_id", "topic_classification", "resolution_extraction",
                                                                "retrieval_relevance", "citation_validity"]))
                       .order_by(EvalRun.id.desc()).limit(200)).all()
    latest: dict[tuple, EvalRun] = {}
    for e in evals:
        latest.setdefault((e.suite, e.language, e.system), e)
    tr = db.execute(select(Translation.method, Translation.needs_review, func.count()).join(Message, Translation.message_id == Message.id)
                    .where(Message.dataset_id == dataset_id).group_by(Translation.method, Translation.needs_review)).all()
    lang_corrections = db.scalar(select(func.count()).where(Correction.dataset_id == dataset_id, Correction.field == "language")) or 0
    return {
        "dataset_id": dataset_id,
        "messages_by_language": [{"language": k, "messages": v, "customer": by_role[k].get("customer", 0), "support": by_role[k].get("support", 0)}
                                 for k, v in sorted(msg_counts.items(), key=lambda kv: -kv[1])],
        "total_messages": sum(msg_counts.values()),
        "unknown_messages": msg_counts.get("unknown", 0), "mixed_messages": msg_counts.get("mixed", 0),
        "reviewer_corrected_messages": corrected, "language_corrections": lang_corrections,
        "conversations_with_multiple_languages": multi_lang,
        "groups": group_rows, "group_basis": "language of the first customer message",
        "min_group_size": min_n,
        "reviewed_quality": [{"suite": e.suite, "language": e.language, "system": e.system, "n": e.n, "passed": e.passed,
                              "score": e.score, "judgment": e.judgment, "created_at": e.created_at.isoformat()} for e in latest.values()],
        "translations": [{"method": m, "needs_review": nr, "count": n} for m, nr, n in tr],
        "notes": ["Language labels describe message text only. They do not indicate nationality, ethnicity or location.",
                  "Rules-based labels cover en/es/fr/de keywords; other languages are expected to have lower coverage.",
                  f"Outcome comparisons are shown only for groups with at least {min_n} conversations with known outcomes."],
        "resolution_labels": RESOLUTION,
    }
