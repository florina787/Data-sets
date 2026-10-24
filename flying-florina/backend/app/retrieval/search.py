"""Access-aware hybrid retrieval over the synthetic document library.

Order of operations (the point of this module):
  1. compute the labels and roles the requesting human may see;
  2. filter candidates by those attributes *in SQL*, before any ranking;
  3. rank permitted candidates with SQLite FTS5 BM25, falling back to a local
     TF-IDF cosine score when FTS finds nothing;
  4. sanitize: text that tries to issue instructions is quarantined and the
     result is flagged, so it can never reach a tool as a command.
Every hit carries document ID, revision, effective date, status, provenance
and classification.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.core import db
from app.core.policy import LABELS, label_allows
from app.core.security import Actor
from app.core.util import DEMO_TODAY

INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore (all )?(previous|prior) instructions"),
    re.compile(r"(?i)you are now in [a-z ]*mode"),
    re.compile(r"(?i)\bcall [a-z_]+_[a-z_]+\b"),
    re.compile(r"(?i)send [^.]* to [^\s]+@[^\s]+"),
    re.compile(r"(?i)approve all"),
    re.compile(r"(?i)disregard (the )?(system|policy)"),
]

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]{1,}")
STOP = {"the", "and", "for", "with", "show", "what", "which", "this", "that", "from", "are", "was", "why", "how",
        "check", "draft", "me", "all", "into", "a", "of", "to", "in", "on", "is", "my", "our", "can", "it", "retrieve"}


def detect_injection(text: str) -> list[str]:
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


def sanitize(text: str) -> str:
    """Neutralize instruction-like spans; the content is kept as quoted, inert data."""
    out = text
    for p in INJECTION_PATTERNS:
        out = p.sub("[QUARANTINED INSTRUCTION-LIKE TEXT]", out)
    return out


def terms(query: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(query) if t.lower() not in STOP]


def _permitted_filter(actor: Actor) -> tuple[str, list[Any]]:
    labels = [lbl for lbl in LABELS if label_allows(actor, lbl)[0]]
    if not labels:
        return "0", []
    clause = f"d.classification IN ({','.join('?' * len(labels))}) AND (d.permitted_roles LIKE '%\"*\"%' OR d.permitted_roles LIKE ?)"
    return clause, labels + [f'%"{actor.role}"%']


def _fts_query(ts: list[str]) -> str:
    # Each term is quoted so user text can never become FTS5 syntax.
    return " OR ".join('"' + t.replace('"', "") + '"' for t in ts)


def search(actor: Actor, query: str, limit: int = 6) -> dict[str, Any]:
    ts = terms(query)
    clause, params = _permitted_filter(actor)
    total_docs = db.query_one("SELECT COUNT(*) n FROM documents")["n"]
    permitted_docs = db.query_one(f"SELECT COUNT(*) n FROM documents d WHERE {clause}", params)["n"]  # noqa: S608 - clause is built from constants
    hits: list[dict[str, Any]] = []
    method = "fts5_bm25"
    if ts:
        hits = db.query(
            f"SELECT d.*, bm25(documents_fts) AS score FROM documents_fts JOIN documents d ON d.id = documents_fts.doc_id "  # noqa: S608
            f"WHERE documents_fts MATCH ? AND {clause} ORDER BY score LIMIT ?",
            [_fts_query(ts)] + params + [limit],
        )
    if not hits and ts:
        method = "tfidf_fallback"
        hits = _tfidf(ts, clause, params, limit)
    results = [_present(h, ts) for h in hits]
    return {
        "query": query,
        "terms": ts,
        "method": method,
        "results": results,
        "permitted_documents": permitted_docs,
        "withheld_by_policy": total_docs - permitted_docs,
        "filter": "Classification and role filter applied in SQL before ranking (POL-003).",
    }


def _tfidf(ts: list[str], clause: str, params: list[Any], limit: int) -> list[dict[str, Any]]:
    docs = db.query(f"SELECT d.* FROM documents d WHERE {clause}", params)  # noqa: S608
    tokenized = {d["id"]: terms(d["title"] + " " + d["body"] + " " + (d["tags"] or "")) for d in docs}
    n = len(docs) or 1
    df = Counter(t for toks in tokenized.values() for t in set(toks))
    scored = []
    for d in docs:
        tf = Counter(tokenized[d["id"]])
        score = sum((tf[t] / (len(tokenized[d["id"]]) or 1)) * math.log((n + 1) / (df[t] + 1) + 1) for t in ts)
        if score > 0:
            scored.append({**d, "score": -score})
    return sorted(scored, key=lambda x: x["score"])[:limit]


def _present(d: dict[str, Any], ts: list[str]) -> dict[str, Any]:
    injection = detect_injection(d["body"])
    body = sanitize(d["body"]) if injection else d["body"]
    flags = []
    if d["status"] != "current":
        flags.append("superseded")
    if d["review_due"] < DEMO_TODAY:
        flags.append("review_overdue")
    if not d["provenance_sha256"]:
        flags.append("missing_provenance")
    if injection:
        flags.append("prompt_injection_quarantined")
    authoritative = not ({"superseded", "missing_provenance", "prompt_injection_quarantined"} & set(flags))
    return {
        "doc_id": d["id"],
        "title": d["title"],
        "revision": d["revision"],
        "effective_date": d["effective_date"],
        "review_due": d["review_due"],
        "classification": d["classification"],
        "source": d["source"],
        "status": d["status"],
        "provenance_sha256": d["provenance_sha256"],
        "superseded_by": d.get("superseded_by"),
        "snippet": _snippet(body, ts),
        "score": round(-float(d["score"]), 4),
        "flags": flags,
        "authoritative": authoritative,
        "injection_patterns": injection,
    }


def _snippet(body: str, ts: list[str], width: int = 260) -> str:
    low = body.lower()
    pos = min((low.find(t) for t in ts if low.find(t) >= 0), default=0)
    start = max(0, pos - 60)
    text = body[start:start + width]
    return ("..." if start else "") + text + ("..." if start + width < len(body) else "")


def get_document(actor: Actor, doc_id: str) -> tuple[dict[str, Any] | None, str]:
    d = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if not d:
        return None, "not_found"
    allowed, why = label_allows(actor, d["classification"])
    roles = db.jload(d["permitted_roles"], [])
    if not allowed or ("*" not in roles and actor.role not in roles):
        return None, why if not allowed else f"Role '{actor.role}' is not on the document's permitted list."
    d["permitted_roles"] = roles
    injection = detect_injection(d["body"])
    if injection:
        d["body"] = sanitize(d["body"])
        d["injection_patterns"] = injection
    return d, "ok"
