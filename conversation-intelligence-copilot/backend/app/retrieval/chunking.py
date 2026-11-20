"""Conversation-aware chunking: sliding windows of whole turns with speaker labels.

A chunk never splits a message, always keeps the speaker of each turn, and
overlaps the previous window so a complaint and the reply to it stay together.
The opening turn (which names the issue and product) is prefixed to every chunk
as context so later chunks remain interpretable on their own.
"""

from __future__ import annotations

import pandas as pd


def chunk_conversations(messages: pd.DataFrame, turns: int = 4, overlap: int = 2) -> list[dict]:
    if overlap >= turns:
        raise ValueError("overlap must be smaller than the window size")
    step = turns - overlap
    chunks: list[dict] = []
    for cid, g in messages.sort_values(["conversation_id", "turn_index"]).groupby("conversation_id", sort=True):
        rows = g.to_dict("records")
        opening = rows[0]
        starts = list(range(0, max(1, len(rows) - overlap), step)) or [0]
        for s in starts:
            window = rows[s : s + turns]
            if not window:
                continue
            body = "\n".join(f"{r['speaker_role'].upper()}: {r['masked_text']}" for r in window)
            context = "" if s == 0 else f"[Opening] CUSTOMER: {opening['masked_text']}\n"
            chunks.append({
                "chunk_id": f"{cid}#{int(window[0]['turn_index'])}-{int(window[-1]['turn_index'])}",
                "conversation_id": cid,
                "message_ids": [r["message_id"] for r in window],
                "turn_start": int(window[0]["turn_index"]),
                "turn_end": int(window[-1]["turn_index"]),
                "speakers": sorted({r["speaker_role"] for r in window}),
                "text": context + body,
                "body": body,
                "dataset_source": opening["dataset_source"],
            })
    return chunks
