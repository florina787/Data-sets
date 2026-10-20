"""Connected-mode structured conversation analysis with Claude via LangChain structured output.

Results are cached by (conversation content hash, model id, prompt version, source text). Evidence spans
are validated against the stored redacted text; invalid spans are dropped and recorded. Failures are
recorded as extraction failures, never replaced by rules output.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.analytics.labels import apply_effective_labels
from app.analytics.rules import validate_evidence
from app.db import session_scope
from app.graph.prompts import EXTRACT_SYSTEM, EXTRACT_VERSION
from app.llm.provider import get_chat_model, provider_status
from app.models.orm import Analysis, Conversation, Dataset, Message, Translation
from app.models.schemas import ConversationAnalysis


def transcript(msgs: list[Message], translated: dict[int, str] | None = None) -> str:
    lines = []
    for m in msgs:
        text = translated.get(m.id, m.text) if translated else m.text
        lines.append(json.dumps({"message_id": m.source_id, "reply_to": m.parent_source_id, "role": m.role,
                                 "language": m.language, "text": text}, ensure_ascii=False))
    return "<untrusted_transcript>\n" + "\n".join(lines) + "\n</untrusted_transcript>"


def extract_messages(msgs: list[dict], model) -> dict:
    """In-memory extraction for evaluation: msgs = [{id, role, text, language?}]. Raises on failure."""
    prompt = "<untrusted_transcript>\n" + "\n".join(json.dumps({"message_id": m["id"], "role": m["role"], "language": m.get("language", "unknown"),
                                                               "text": m["text"]}, ensure_ascii=False) for m in msgs) + "\n</untrusted_transcript>"
    out = model.with_structured_output(ConversationAnalysis, include_raw=True).invoke([SystemMessage(EXTRACT_SYSTEM), HumanMessage(prompt)])
    if out.get("parsed") is None:
        raise ValueError(f"structured output failed validation: {out.get('parsing_error')}")
    fields = out["parsed"].model_dump(mode="json")
    fields["evidence"], fields["invalid_evidence"] = validate_evidence(fields["evidence"], {m["id"]: m["text"] for m in msgs})
    return fields


def analyze_conversation(conv_id: int, source_text: str = "original", model=None) -> Analysis:
    model = model or get_chat_model()
    model_id = provider_status()["model_id"]
    with session_scope() as db:
        conv = db.get(Conversation, conv_id)
        msgs = db.scalars(select(Message).where(Message.conversation_id == conv_id).order_by(Message.position)).all()
        cached = db.scalar(select(Analysis).where(Analysis.conversation_id == conv_id, Analysis.method == "llm",
                                                  Analysis.model_id == model_id, Analysis.prompt_version == EXTRACT_VERSION,
                                                  Analysis.content_hash == conv.content_hash, Analysis.source_text == source_text))
        if cached and cached.status == "ok":
            return cached
        translated = None
        if source_text == "translated":
            rows = db.scalars(select(Translation).where(Translation.message_id.in_([m.id for m in msgs]), Translation.target_language == "en")).all()
            translated = {t.message_id: t.text for t in rows}
        texts = {m.source_id: (translated or {}).get(m.id, m.text) for m in msgs}
        prompt = transcript(msgs, translated)
        content_hash = conv.content_hash
    fields, status, error = {}, "ok", None
    try:
        out = model.with_structured_output(ConversationAnalysis, include_raw=True).invoke(
            [SystemMessage(EXTRACT_SYSTEM), HumanMessage(prompt)])
        parsed = out.get("parsed")
        if parsed is None:
            raise ValueError(f"structured output failed validation: {out.get('parsing_error')}")
        fields = parsed.model_dump(mode="json")
        valid, invalid = validate_evidence(fields["evidence"], texts)
        fields["evidence"] = valid
        fields["invalid_evidence"] = invalid
        if source_text == "translated":
            for e in fields["evidence"]:
                e["translated"] = True  # quotes refer to the translation, never presented as original text
        fields.update(analysis_method="llm", model_id=model_id, prompt_version=EXTRACT_VERSION, subtheme=None)
    except Exception as exc:  # recorded as an extraction failure
        status, error = "failed", f"{type(exc).__name__}: {str(exc)[:500]}"
    with session_scope() as db:
        if cached:
            db.delete(db.get(Analysis, cached.id))
            db.flush()
        a = Analysis(conversation_id=conv_id, method="llm", model_id=model_id, prompt_version=EXTRACT_VERSION,
                     content_hash=content_hash, source_text=source_text, fields=fields, status=status, error=error)
        db.add(a)
        db.flush()
        db.expunge(a)
        return a


def activate_llm_analysis(dataset_id: str) -> dict:
    """Make the latest LLM extraction the effective labels. Failed extractions become 'unknown' (never rules)."""
    model_id = provider_status()["model_id"]
    counts = {"ok": 0, "failed": 0, "missing": 0}
    with session_scope() as db:
        convs = db.scalars(select(Conversation).where(Conversation.dataset_id == dataset_id)).all()
        for c in convs:
            a = db.scalar(select(Analysis).where(Analysis.conversation_id == c.id, Analysis.method == "llm", Analysis.model_id == model_id,
                                                 Analysis.prompt_version == EXTRACT_VERSION, Analysis.source_text == "original")
                          .order_by(Analysis.id.desc()))
            if a is None:
                counts["missing"] += 1
                apply_effective_labels(c, {}, None)
            elif a.status != "ok":
                counts["failed"] += 1
                apply_effective_labels(c, {}, a.id)
            else:
                counts["ok"] += 1
                apply_effective_labels(c, a.fields, a.id)
        db.get(Dataset, dataset_id).active_analysis = f"llm:{model_id}:{EXTRACT_VERSION}"
    return counts
