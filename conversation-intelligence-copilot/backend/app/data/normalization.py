"""Normalization from the canonical source frame to message records.

Key decisions (documented in ASSUMPTIONS.md):

* Every source message is a meaningful templated sentence followed by a run of
  random lowercase tokens (synthetic filler). `clean_text` is the text up to the
  last sentence terminator when, and only when, everything after it consists of
  lowercase ASCII tokens. The original `text` is never modified.
* Message order is `turn_index`. Timestamps are not monotonic within a
  conversation in this dataset, so they are used only for dating the
  conversation (earliest timestamp = conversation start).
"""

from __future__ import annotations

import re

import pandas as pd

from app.governance.pii import mask_text, pseudonymize

_TERMINATOR = re.compile(r"[.!?]")
_NOISE = re.compile(r"[a-z ]*")
ROLE_MAP = {"customer": "customer", "client": "customer", "user": "customer", "agent": "agent", "support": "agent", "assistant": "agent", "rep": "agent"}


def split_noise(text: str) -> tuple[str, int]:
    """Return (clean_text, noise_token_count)."""
    text = text.strip()
    matches = list(_TERMINATOR.finditer(text))
    if not matches:
        return text, 0
    end = matches[-1].end()
    rest = text[end:]
    if rest and _NOISE.fullmatch(rest):
        return text[:end].strip(), len(rest.split())
    return text, 0


def normalize_messages(frame: pd.DataFrame, dataset_source: str, source_file: str) -> pd.DataFrame:
    df = frame.copy()
    df["conversation_id"] = df["conversation_id"].str.strip()
    df["turn_index"] = pd.to_numeric(df["turn_index"], errors="coerce").astype("Int64")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["speaker_role"] = df["speaker_role"].str.strip().str.lower().map(lambda r: ROLE_MAP.get(r, "unknown"))
    split = df["text"].fillna("").map(split_noise)
    df["clean_text"] = split.map(lambda x: x[0])
    df["noise_token_count"] = split.map(lambda x: x[1])
    masked = [mask_text(t) for t in df["clean_text"]]
    df["masked_text"] = [m[0] for m in masked]
    df["pii_hits"] = [sum(m[1].values()) for m in masked]
    df["customer_id"] = df["customer_name"].map(lambda n: pseudonymize(n, "CUST") if n else None)
    df["agent_id"] = df["agent_name"].str.strip().replace("", None)
    df["message_id"] = df["conversation_id"] + "-T" + df["turn_index"].astype(str).str.zfill(2)
    df["dataset_source"] = dataset_source
    df["source_reference"] = source_file + ":line " + df["source_row"].astype(str)
    return df[
        [
            "message_id", "conversation_id", "turn_index", "timestamp", "speaker_role", "text", "clean_text",
            "masked_text", "noise_token_count", "pii_hits", "customer_id", "agent_id", "dataset_source", "source_reference",
        ]
    ]
