"""Retrieval-augmented knowledge pipeline (Agent 14).

ingest -> validate -> extract -> clean -> chunk -> enrich metadata -> embed -> index
query  -> hybrid retrieve (BM25 + hashed-vector cosine) -> metadata rerank
       -> evidence validation (confidence threshold, staleness) -> extractive answer
       -> citation verification -> response (or refusal when evidence is insufficient)

Embeddings are deterministic feature-hashing vectors so the demo needs no external
embedding service. ``Embedder`` is a seam for swapping in a LangChain embedding model.
Answers are *extractive*: every sentence returned is copied from a cited chunk, so
citations are verifiable by construction (and re-verified before returning).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.config.settings import PROJECT_DIR

KB_DIR = PROJECT_DIR / "data" / "knowledge"
REQUIRED_META = {"document_id", "title", "provider", "publication_date", "retrieval_date", "version", "jurisdiction",
                 "service_type", "access_classification", "review_by"}
DIM = 512
_STOP = set("a an the and or of to in for on is are be by with from as at it this that you your can not if do "
            "does what how when which my i me we our".split())
MIN_CONFIDENCE = 0.18
# Generic service words carry little intent; they are down-weighted and cannot alone justify an answer.
GENERIC = {"mri", "ct", "ultrasound", "xray", "x", "ray", "scan", "appointment", "test", "imaging", "need",
           "get", "facility"}
EXPANSIONS = {"ohip": ["provincial", "coverage"], "cover": ["coverage"], "covered": ["coverage"],
              "cost": ["fee", "coverage"], "pay": ["fee", "private"], "price": ["fee"], "free": ["fee"],
              "prepare": ["preparation"], "cancel": ["cancelling"], "referral": ["referral", "requisition"],
              "book": ["booking"], "emergency": ["emergency", "911"], "suicide": ["crisis", "988"]}


def expand_query(tokens: list[str]) -> list[str]:
    out = list(tokens)
    for t in tokens:
        out.extend(EXPANSIONS.get(t, []))
    return out


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for t in toks:
        if t in _STOP:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


class Embedder:
    """Deterministic feature-hashing embedder (unigrams + bigrams), L2-normalised."""

    def embed(self, text: str) -> list[float]:
        toks = tokenize(text)
        vec = [0.0] * DIM
        for gram in toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]:
            h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
            vec[h % DIM] += 1.0 if (h >> 8) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


@dataclass
class Chunk:
    id: str
    document_id: str
    ordinal: int
    heading: str
    text: str
    tokens: list[str]
    embedding: list[float]
    meta: dict = field(default_factory=dict)


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    heading: str
    source_url: str | None
    provider: str
    version: str
    retrieval_date: str
    access_classification: str
    stale: bool


class RagAnswer(BaseModel):
    answered: bool
    answer: str | None
    citations: list[Citation]
    confidence: float
    refusal_reason: str | None = None
    warnings: list[str] = []
    kb_version: str


def parse_document(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    missing = REQUIRED_META - meta.keys()
    if missing:
        raise ValueError(f"{path.name}: missing metadata {sorted(missing)}")
    body = re.sub(r"[ \t]+", " ", m.group(2)).strip()
    return meta, body


def chunk_document(meta: dict, body: str, embedder: Embedder) -> list[Chunk]:
    chunks, heading = [], meta["title"]
    sections = re.split(r"^# (.+)$", body, flags=re.M)
    # re.split yields [pre, h1, body1, h2, body2...]
    pairs = [(heading, sections[0])] + [(sections[i], sections[i + 1]) for i in range(1, len(sections) - 1, 2)]
    ordinal = 0
    for h, text in pairs:
        for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
            cid = f"{meta['document_id']}#{ordinal}"
            chunks.append(Chunk(cid, meta["document_id"], ordinal, h, para, tokenize(h + " " + para),
                                embedder.embed(h + " " + para), meta))
            ordinal += 1
    return chunks


class KnowledgeIndex:
    def __init__(self, kb_dir: Path = KB_DIR, today: date | None = None) -> None:
        self.embedder = Embedder()
        self.docs: dict[str, dict] = {}
        self.chunks: list[Chunk] = []
        self.errors: list[str] = []
        self.today = today or date.today()
        digest = hashlib.sha256()
        for p in sorted(kb_dir.glob("*.md")):
            try:
                meta, body = parse_document(p)
            except ValueError as e:
                self.errors.append(str(e))
                continue
            meta["checksum"] = hashlib.sha256(body.encode()).hexdigest()
            digest.update(meta["checksum"].encode())
            self.docs[meta["document_id"]] = meta
            self.chunks.extend(chunk_document(meta, body, self.embedder))
        self.kb_version = digest.hexdigest()[:12]
        self.df = Counter(t for c in self.chunks for t in set(c.tokens))
        self.avgdl = sum(len(c.tokens) for c in self.chunks) / max(1, len(self.chunks))

    def is_stale(self, doc_id: str) -> bool:
        try:
            return date.fromisoformat(self.docs[doc_id]["review_by"]) < self.today
        except (KeyError, ValueError):
            return True

    def _bm25(self, q: list[str], c: Chunk, k1: float = 1.4, b: float = 0.75) -> float:
        tf = Counter(c.tokens)
        n = len(self.chunks)
        s = 0.0
        for t in set(q):
            if t not in tf:
                continue
            idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
            w = 0.4 if t in GENERIC else 1.0
            s += w * idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(c.tokens) / self.avgdl))
        return s

    def retrieve(self, query: str, k: int = 4, service: str | None = None,
                 allowed_classes: set[str] | None = None) -> list[tuple[Chunk, float]]:
        allowed_classes = allowed_classes or {"public", "synthetic_demo"}
        q = expand_query(tokenize(query))
        qv = self.embedder.embed(" ".join(q))
        scored = []
        bm = [self._bm25(q, c) for c in self.chunks]
        mx = max(bm) if bm and max(bm) > 0 else 1.0
        for c, b in zip(self.chunks, bm):
            if c.meta["access_classification"] not in allowed_classes:
                continue
            cos = sum(x * y for x, y in zip(qv, c.embedding))
            score = 0.6 * (b / mx) + 0.4 * max(0.0, cos)
            if service and (service in c.meta["service_type"] or c.meta["service_type"] == "ALL"):
                score *= 1.1  # metadata rerank
            if self.is_stale(c.document_id):
                score *= 0.8
            scored.append((c, round(score, 4)))
        scored.sort(key=lambda t: (-t[1], t[0].id))
        return scored[:k]

    def answer(self, query: str, service: str | None = None) -> RagAnswer:
        hits = self.retrieve(query, k=4, service=service)
        q = set(expand_query(tokenize(query)))
        core = q - GENERIC
        if not hits or hits[0][1] < MIN_CONFIDENCE or not core & set(hits[0][0].tokens):
            return RagAnswer(answered=False, answer=None, citations=[], confidence=hits[0][1] if hits else 0.0,
                             refusal_reason="I couldn't find this in the approved knowledge base, so I won't guess. "
                                            "Please check with the provider or your clinician.",
                             kb_version=self.kb_version)
        top = hits[0][1]
        used = [(c, s) for c, s in hits if s >= max(MIN_CONFIDENCE, top * 0.6)][:2]
        sentences: list[str] = []
        cites: list[Citation] = []
        warnings: list[str] = []
        for c, _ in used:
            sents = re.split(r"(?<=[.!?])\s+", c.text)
            ranked = sorted(sents, key=lambda s: -len(core & set(tokenize(s))))
            pick = [s for s in ranked[:2] if core & set(tokenize(s))] or ranked[:1]
            for s in sorted(pick, key=sents.index):
                sentences.append(f"{s} [{len(cites) + 1}]")
            meta = self.docs[c.document_id]
            stale = self.is_stale(c.document_id)
            if stale:
                warnings.append(f"'{meta['title']}' is past its review date ({meta['review_by']}); verify at source.")
            cites.append(Citation(document_id=c.document_id, chunk_id=c.id, title=meta["title"], heading=c.heading,
                                  source_url=meta.get("source_url"), provider=meta["provider"],
                                  version=meta["version"], retrieval_date=meta["retrieval_date"],
                                  access_classification=meta["access_classification"], stale=stale))
        ans = " ".join(sentences)
        if not verify_citations(ans, cites, self):
            return RagAnswer(answered=False, answer=None, citations=[], confidence=top,
                             refusal_reason="Citation verification failed.", kb_version=self.kb_version)
        if any(c.access_classification == "synthetic_demo" for c in cites):
            warnings.append("Includes FICTIONAL demo-facility documentation.")
        return RagAnswer(answered=True, answer=ans, citations=cites, confidence=top, warnings=warnings,
                         kb_version=self.kb_version)


def verify_citations(answer: str, cites: list[Citation], idx: KnowledgeIndex) -> bool:
    """Every '[n]'-tagged sentence must appear verbatim in the n-th cited chunk."""
    chunk_text = {c.id: c.text for c in idx.chunks}
    for m in re.finditer(r"(.+?) \[(\d+)\](?:\s|$)", answer):
        sent, n = m.group(1).strip(), int(m.group(2))
        if n < 1 or n > len(cites) or sent not in chunk_text.get(cites[n - 1].chunk_id, ""):
            return False
    return True


@lru_cache
def get_index() -> KnowledgeIndex:
    return KnowledgeIndex()
