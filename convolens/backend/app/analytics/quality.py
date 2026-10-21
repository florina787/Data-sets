"""Data-quality report for one dataset."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.metrics import GROUPABLE
from app.models.orm import Analysis, Conversation, Dataset, Exclusion, Message

REDACTION_LIMITATIONS = [
    "Pattern-based: emails, URLs, IPs, Luhn-valid card numbers, phone numbers, long alphanumeric identifiers, @handles "
    "(public brand support accounts are kept), self-introduced names and agent sign-offs.",
    "Names that are not introduced with phrases such as 'my name is' may remain. Street addresses and postcodes are not detected.",
    "Short numbers (amounts, dates, version numbers) are kept intentionally so analysis and translation checks remain possible.",
    "Original unredacted text is never stored, so it cannot be re-examined after import.",
]


def report(db: Session, dataset_id: str) -> dict:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise ValueError("Unknown dataset")
    m = ds.manifest or {}
    unknown = {}
    for field, (col, _, _) in GROUPABLE.items():
        unknown[field] = db.scalar(select(func.count()).where(Conversation.dataset_id == dataset_id, col == "unknown")) or 0
    total = db.scalar(select(func.count()).where(Conversation.dataset_id == dataset_id)) or 0
    failures = db.execute(select(Analysis.method, Analysis.status, func.count()).join(Conversation, Analysis.conversation_id == Conversation.id)
                          .where(Conversation.dataset_id == dataset_id).group_by(Analysis.method, Analysis.status)).all()
    invalid_spans = 0
    for (fields,) in db.execute(select(Analysis.fields).join(Conversation, Analysis.conversation_id == Conversation.id)
                                .where(Conversation.dataset_id == dataset_id)).all():
        invalid_spans += len((fields or {}).get("invalid_evidence") or [])
    excl = db.execute(select(Exclusion.reason, func.count(), func.sum(Exclusion.message_count)).where(Exclusion.dataset_id == dataset_id)
                      .group_by(Exclusion.reason)).all()
    partial = db.scalar(select(func.count()).where(Conversation.dataset_id == dataset_id, Conversation.completeness == "partial")) or 0
    lang_unknown = db.scalar(select(func.count()).where(Message.dataset_id == dataset_id, Message.language == "unknown")) or 0
    return {
        "dataset": {"id": ds.id, "name": ds.name, "kind": ds.kind, "synthetic": ds.synthetic, "status": ds.status,
                    "active_analysis": ds.active_analysis},
        "manifest": m,
        "conversations": total,
        "missing_messages": {"messages_with_missing_parent": m.get("counts", {}).get("messages_with_missing_parent", 0),
                             "threads_excluded_for_missing_root_parent": m.get("exclusions", {}).get("root_parent_missing", 0),
                             "selected_threads_with_dangling_reply_refs": m.get("branching", {}).get("selected", {}).get("with_dangling_reply_refs", 0),
                             "selected_messages_missing_text": m.get("counts", {}).get("selected_messages_missing_text", 0),
                             "partial_conversations": partial},
        "branching": m.get("branching", {}),
        "cycles": {"messages_in_cycles": m.get("counts", {}).get("messages_in_cycles", 0),
                   "messages_unreachable": m.get("counts", {}).get("messages_unreachable_due_to_cycles", 0)},
        "duplicates": {"exact_dropped": m.get("counts", {}).get("exact_duplicates_dropped", 0),
                       "conflicting": m.get("counts", {}).get("conflicting_duplicates", 0)},
        "rejected_rows": {k: v for k, v in m.get("counts", {}).items() if k.startswith("rejected_") or k == "invalid_timestamp"},
        "unknown_labels": {"denominator": total, **unknown},
        "unknown_language_messages": lang_unknown,
        "extraction": [{"method": a, "status": s, "count": n} for a, s, n in failures],
        "invalid_evidence_spans_dropped": invalid_spans,
        "exclusions": [{"reason": r, "threads": n, "messages": int(msgs or 0)} for r, n, msgs in excl],
        "sampling": m.get("sampling", {}),
        "redactions": m.get("redactions", {}),
        "redaction_limitations": REDACTION_LIMITATIONS,
    }
