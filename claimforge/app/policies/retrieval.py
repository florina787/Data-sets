"""Policy retrieval (RAG retrieval step) — local BM25, no paid embedding API.

BM25 is deterministic, explainable and dependency-free. Embeddings are an optional
future enhancement (see docs/ARCHITECTURE.md); they are never required in DEMO_MODE.

Evidence sufficiency is enforced: if no chunk matches enough distinct query terms the
result is ``INSUFFICIENT POLICY EVIDENCE`` — nothing is fabricated.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.models.domain import PolicySection
from app.policies.knowledge_base import PolicyKnowledgeBase

INSUFFICIENT = "INSUFFICIENT POLICY EVIDENCE"

_STOP = set("""a an and are as at be by for from if in into is it of on or such that the their then there
these this to was will with what which who when where how does do should can about after before per any all
under within than more most other our we you your i me my policy""".split())
_SYNONYMS = {
    "physio": "physiotherapy", "pt": "physiotherapy", "physical": "physiotherapy",
    "auth": "authorization", "preauthorization": "authorization", "pre-authorization": "authorization",
    "authorisation": "authorization", "preauth": "authorization", "approval": "authorization",
    "max": "maximum", "limit": "maximum", "cap": "maximum", "coverage": "covered", "covers": "covered",
    "chiro": "chiropractic", "massage": "massage", "rmt": "massage", "cancelled": "cancel", "canceled": "cancel",
    "cancellations": "cancel", "cancellation": "cancel", "dup": "duplicate", "duplicates": "duplicate",
    "eligible": "eligibility", "ineligible": "eligibility", "visits": "visit", "annual": "annual",
}
_TOKEN_RE = re.compile(r"[a-z0-9\-\$\.]+")


def _stem(tok: str) -> str:
    tok = tok.strip(".-")
    tok = _SYNONYMS.get(tok, tok)
    for suffix in ("ations", "ation", "ings", "ing", "ies", "es", "s"):
        if len(tok) > 5 and tok.endswith(suffix):
            base = tok[: -len(suffix)]
            return _SYNONYMS.get(base, base)
    return tok


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class RetrievedChunk:
    section: PolicySection
    score: float
    matched_terms: list[str]

    def to_evidence(self) -> dict:
        s = self.section
        return {"doc_id": s.doc_id, "section_id": s.section_id, "title": s.title, "text": s.text,
                "score": round(self.score, 3), "matched_terms": self.matched_terms, "citation": s.citation,
                "source": "RETRIEVAL (BM25 over synthetic policy KB)"}


class BM25Retriever:
    def __init__(self, kb: PolicyKnowledgeBase, k1: float = 1.5, b: float = 0.75) -> None:
        self.kb, self.k1, self.b = kb, k1, b
        self.reindex()

    def reindex(self) -> None:
        self.docs = self.kb.sections
        self.tokens = [tokenize(f"{s.title} {s.title} {s.text}") for s in self.docs]
        self.tf = [Counter(t) for t in self.tokens]
        self.avgdl = (sum(len(t) for t in self.tokens) / len(self.tokens)) if self.tokens else 1.0
        df: Counter = Counter()
        for t in self.tokens:
            df.update(set(t))
        n = len(self.tokens)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def search(self, query: str, top_k: int = 5, min_coverage: float = 0.5) -> list[RetrievedChunk]:
        q_terms = list(dict.fromkeys(tokenize(query)))
        if not q_terms:
            return []
        results: list[RetrievedChunk] = []
        for sec, tf, toks in zip(self.docs, self.tf, self.tokens):
            score = 0.0
            matched = []
            for term in q_terms:
                f = tf.get(term, 0)
                if not f:
                    continue
                matched.append(term)
                idf = self.idf.get(term, 0.0)
                score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(toks) / self.avgdl))
            if not matched:
                continue
            # Evidence sufficiency: a chunk must cover enough of the query terms (unknown terms count).
            needed = max(1, math.ceil(min_coverage * min(len(q_terms), 4)))
            if len(matched) >= needed:
                results.append(RetrievedChunk(sec, score, matched))
        results.sort(key=lambda r: (-r.score, r.section.section_id))
        return results[:top_k]

    def search_evidence(self, query: str, top_k: int = 5) -> dict:
        hits = self.search(query, top_k=top_k)
        if not hits:
            return {"query": query, "status": INSUFFICIENT, "evidence": [],
                    "message": f"{INSUFFICIENT}: no policy section in the knowledge base supports this query. "
                               "No clause has been generated or assumed."}
        return {"query": query, "status": "EVIDENCE_FOUND", "evidence": [h.to_evidence() for h in hits]}
