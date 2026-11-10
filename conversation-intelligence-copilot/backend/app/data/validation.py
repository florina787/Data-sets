"""Data-quality checks. Each check reports a count, a severity and examples."""

from __future__ import annotations

import pandas as pd


def _check(name: str, count: int, total: int, severity: str, description: str, examples: list | None = None) -> dict:
    return {
        "check": name,
        "count": int(count),
        "total": int(total),
        "rate": round(count / total, 4) if total else 0.0,
        "severity": severity if count else "pass",
        "description": description,
        "examples": (examples or [])[:5],
    }


def quality_report(messages: pd.DataFrame) -> dict:
    n = len(messages)
    convs = messages.groupby("conversation_id")
    n_conv = convs.ngroups
    checks: list[dict] = []

    dup_rows = messages.duplicated(["conversation_id", "turn_index", "speaker_role", "text"])
    checks.append(_check("duplicate_messages", dup_rows.sum(), n, "error", "Identical (conversation, turn, role, text) rows."))
    dup_turns = messages.duplicated(["conversation_id", "turn_index"])
    checks.append(_check("duplicate_turn_index", dup_turns.sum(), n, "error", "Two messages share a conversation and turn index.",
                         messages.loc[dup_turns, "message_id"].tolist()))
    signature = convs["clean_text"].apply(lambda s: "␞".join(s))
    dup_conv = signature.duplicated()
    checks.append(_check("duplicate_conversations", dup_conv.sum(), n_conv, "warning", "Conversations with identical cleaned transcripts.",
                         signature[dup_conv].index.tolist()))
    checks.append(_check("missing_timestamp", messages["timestamp"].isna().sum(), n, "warning", "Unparseable or missing timestamps."))
    checks.append(_check("missing_turn_index", messages["turn_index"].isna().sum(), n, "error", "Missing or non-numeric turn index."))
    unknown_role = messages["speaker_role"].eq("unknown")
    checks.append(_check("unknown_speaker", unknown_role.sum(), n, "error", "Speaker role not recognised."))
    empty = messages["clean_text"].str.strip().eq("")
    checks.append(_check("empty_text", empty.sum(), n, "error", "Messages with no text."))
    checks.append(_check("missing_agent", messages["agent_id"].isna().sum(), n, "warning", "Messages without an agent identifier."))

    def gaps(s: pd.Series) -> bool:
        idx = sorted(int(i) for i in s.dropna())
        return idx != list(range(len(idx)))

    gap_ids = [cid for cid, s in convs["turn_index"] if gaps(s)]
    checks.append(_check("turn_index_gaps", len(gap_ids), n_conv, "warning", "Turn indexes are not contiguous from 0.", gap_ids))

    def non_monotonic(g: pd.DataFrame) -> bool:
        ts = g.sort_values("turn_index")["timestamp"]
        return not ts.is_monotonic_increasing

    nm = [cid for cid, g in convs if non_monotonic(g)]
    checks.append(_check("timestamps_not_in_turn_order", len(nm), n_conv, "warning",
                         "Timestamps decrease while turn_index increases. Turn order is treated as authoritative; timestamps are used only to date conversations.", nm))
    multi_agent = convs["agent_id"].nunique()
    checks.append(_check("multiple_agents_per_conversation", (multi_agent > 1).sum(), n_conv, "info", "Conversations handled by more than one agent ID."))
    first_role = convs.apply(lambda g: g.sort_values("turn_index")["speaker_role"].iloc[0])
    checks.append(_check("not_customer_opened", (first_role != "customer").sum(), n_conv, "info", "Conversations whose first turn is not from the customer."))
    sizes = convs.size()
    checks.append(_check("very_short_conversations", (sizes < 4).sum(), n_conv, "warning", "Fewer than 4 messages."))
    q1, q3 = sizes.quantile(0.25), sizes.quantile(0.75)
    outliers = sizes[(sizes > q3 + 1.5 * (q3 - q1)) | (sizes < q1 - 1.5 * (q3 - q1))]
    checks.append(_check("length_outliers", len(outliers), n_conv, "info", "Conversation length outside 1.5 IQR.", outliers.index.tolist()))
    noisy = messages["noise_token_count"] > 0
    checks.append(_check("synthetic_filler_tokens", noisy.sum(), n, "info",
                         "Messages ending in random lowercase filler tokens. Filler is removed in clean_text; raw text is preserved."))
    nonascii = messages["clean_text"].str.contains(r"[^\x00-\x7F‘’“”]", regex=True)
    checks.append(_check("unsupported_characters", nonascii.sum(), n, "info", "Characters outside ASCII and typographic quotes."))
    checks.append(_check("pii_detected", (messages["pii_hits"] > 0).sum(), n, "warning", "Messages where PII patterns were found and masked."))

    severity_rank = {"error": 3, "warning": 2, "info": 1, "pass": 0}
    worst = max((c["severity"] for c in checks), key=lambda s: severity_rank[s])
    return {"messages": n, "conversations": n_conv, "overall": worst, "checks": checks}


def profile(messages: pd.DataFrame) -> dict:
    convs = messages.groupby("conversation_id")
    ts = messages["timestamp"]
    sizes = convs.size()
    return {
        "rows": len(messages),
        "conversations": int(convs.ngroups),
        "agents": int(messages["agent_id"].nunique()),
        "customers": int(messages["customer_id"].nunique()),
        "roles": messages["speaker_role"].value_counts().to_dict(),
        "timestamp_min": str(ts.min()),
        "timestamp_max": str(ts.max()),
        "messages_per_conversation": {k: round(float(v), 2) for k, v in sizes.describe().items()},
        "unique_clean_texts": int(messages["clean_text"].nunique()),
        "conversations_per_agent": {k: round(float(v), 2) for k, v in messages.groupby("agent_id")["conversation_id"].nunique().describe().items()},
    }
