"""Evidence assembly: resolve cited conversation/message IDs to source excerpts.

Every evidence item carries the conversation ID, message IDs, turn range, the
masked excerpt text and the source CSV line, so a reader can verify it. IDs that
do not resolve, or fall outside the selected dataset mode, are dropped and
reported to QA.
"""

from __future__ import annotations

import re

import pandas as pd

from app.analytics.db import DATASET_SOURCES, AnalyticsDB

def _match_reason(r: dict) -> str:
    ms = r.get("method_scores") or {}
    if r.get("retrieval_method") == "hybrid":
        parts = [f"{'MiniLM' if m == 'dense' else 'LSA'} #{v['rank']}" for m, v in ms.items()]
        return "Hybrid match (" + ", ".join(parts) + f"; fused by RRF; similarity {r['similarity']:.2f})"
    return f"Semantic match (cosine similarity {r['similarity']:.2f})"


MSG_ID = re.compile(r"^(C\d{7})-T(\d{2})$")
MAX_ITEMS = 12


def _excerpts(msgs: pd.DataFrame, focus_turns: list[int] | None = None) -> list[dict]:
    """Key messages: opening, most negative customer turn, the agent reply after it, and any focus turns."""
    msgs = msgs.sort_values("turn_index")
    pick: list[int] = [int(msgs["turn_index"].iloc[0])]
    cust = msgs[(msgs["speaker_role"] == "customer") & (msgs["turn_index"] > 0)]
    if focus_turns:
        for t in focus_turns:
            pick += [t - 1, t]
    elif len(cust):
        worst = cust.sort_values(["sentiment_score", "turn_index"]).iloc[0]
        pick += [int(worst["turn_index"]), int(worst["turn_index"]) + 1]
    pick.append(int(msgs["turn_index"].iloc[-1]))
    chosen = msgs[msgs["turn_index"].isin(set(pick))]
    return [{"message_id": r.message_id, "turn_index": int(r.turn_index), "role": r.speaker_role, "text": r.text,
             "sentiment": r.sentiment, "act": r.act, "source_reference": r.source_reference} for r in chosen.itertuples()]


def assemble(db: AnalyticsDB, refs: list[tuple[str, str]], retrieval: list[dict], dataset_mode: str) -> tuple[list[dict], dict]:
    """refs: (id, reason) pairs from analytical results. Returns (evidence, validation report)."""
    conv_focus: dict[str, list[int]] = {}
    reasons: dict[str, str] = {}
    invalid: list[str] = []
    for ref, reason in refs:
        m = MSG_ID.match(ref)
        cid = m.group(1) if m else ref
        if m:
            conv_focus.setdefault(cid, []).append(int(m.group(2)))
        else:
            conv_focus.setdefault(cid, [])
        reasons.setdefault(cid, reason)
    for r in retrieval:
        conv_focus.setdefault(r["conversation_id"], [])
    ids = list(conv_focus)[: MAX_ITEMS + len(retrieval)]
    if not ids:
        return [], {"requested": 0, "resolved": 0, "invalid": [], "out_of_scope": []}
    allowed_sources = DATASET_SOURCES[dataset_mode]
    msgs = db.query(
        f"""SELECT m.message_id, m.conversation_id, m.turn_index, m.speaker_role, m.masked_text AS text, m.source_reference,
                   l.sentiment, l.sentiment_score, l.act
            FROM messages m JOIN message_labels l USING (message_id)
            WHERE m.conversation_id IN ({','.join('?' * len(ids))})""", ids)
    conv = db.query(
        f"""SELECT conversation_id, topic_label, product, sentiment, agent_id, CAST(start_timestamp AS DATE) AS date, dataset_source
            FROM conversations WHERE conversation_id IN ({','.join('?' * len(ids))})""", ids).set_index("conversation_id")
    evidence: list[dict] = []
    out_of_scope: list[str] = []
    for r in retrieval:
        cid = r["conversation_id"]
        if cid not in conv.index:
            invalid.append(r["evidence_id"])
            continue
        if conv.loc[cid, "dataset_source"] not in allowed_sources:
            out_of_scope.append(cid)
            continue
        g = msgs[(msgs["conversation_id"] == cid) & msgs["message_id"].isin(r["message_ids"])].sort_values("turn_index")
        evidence.append({
            "evidence_id": r["evidence_id"], "kind": "retrieval", "conversation_id": cid, "message_ids": r["message_ids"],
            "turn_range": r["turn_range"], "excerpts": [{"message_id": x.message_id, "turn_index": int(x.turn_index), "role": x.speaker_role,
                                                         "text": x.text, "sentiment": x.sentiment, "act": x.act, "source_reference": x.source_reference}
                                                        for x in g.itertuples()],
            "topic": conv.loc[cid, "topic_label"], "product": conv.loc[cid, "product"], "sentiment": conv.loc[cid, "sentiment"],
            "agent_id": conv.loc[cid, "agent_id"], "date": str(conv.loc[cid, "date"])[:10], "similarity": r["similarity"],
            "reason": _match_reason(r),
            "retrieval_method": r.get("retrieval_method"), "method_scores": r.get("method_scores", {}),
        })
    for cid, focus in conv_focus.items():
        if any(e["conversation_id"] == cid for e in evidence):
            continue
        if cid not in conv.index:
            invalid.append(cid)
            continue
        if conv.loc[cid, "dataset_source"] not in allowed_sources:
            out_of_scope.append(cid)
            continue
        g = msgs[msgs["conversation_id"] == cid]
        ex = _excerpts(g, focus or None)
        evidence.append({
            "evidence_id": f"{cid}#analysis", "kind": "analysis", "conversation_id": cid, "message_ids": [e["message_id"] for e in ex],
            "turn_range": [min(e["turn_index"] for e in ex), max(e["turn_index"] for e in ex)], "excerpts": ex,
            "topic": conv.loc[cid, "topic_label"], "product": None if pd.isna(conv.loc[cid, "product"]) else conv.loc[cid, "product"],
            "sentiment": conv.loc[cid, "sentiment"], "agent_id": conv.loc[cid, "agent_id"], "date": str(conv.loc[cid, "date"])[:10],
            "similarity": None, "reason": reasons.get(cid, "Cited by the analysis"),
        })
        if len(evidence) >= MAX_ITEMS + len(retrieval):
            break
    for e in evidence:
        if isinstance(e.get("product"), float):
            e["product"] = None
    return evidence, {"requested": len(conv_focus), "resolved": len(evidence), "invalid": invalid, "out_of_scope": out_of_scope}
