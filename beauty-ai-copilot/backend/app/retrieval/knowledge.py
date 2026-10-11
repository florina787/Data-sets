"""Offline lexical retrieval (BM25) over versioned demo documents.

Authorization filtering happens BEFORE scoring: documents a user may not read are never
tokenized for that query. Retrieved text is data; it is scanned for instruction-like content
and can never alter policy, gates or permissions (those live in deterministic services).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.errors import Forbidden, NotFound

TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-\.]*")
STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "is", "be", "for", "on", "by", "with", "as", "it", "its",
        "are", "at", "from", "that", "this", "must", "may", "not", "no", "any", "each", "every", "only"}
INJECTION_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"ignore (all |the |previous |prior )?(instructions|release policy|policy)",
        r"system override", r"mark (every|all) gates? as pass", r"grant (the )?\w+ role",
        r"approve the release immediately", r"you are now", r"disregard (the )?(rules|policy)",
    ]
]


@dataclass
class Section:
    doc_id: str
    version: str
    section: str
    heading: str
    text: str
    tokens: list[str] = field(default_factory=list)


@dataclass
class Document:
    doc_id: str
    version: str
    title: str
    status: str
    effective_date: str
    owner_role: str
    access: list[str]
    meta: dict
    preamble: str
    sections: list[Section]

    def can_read(self, roles: list[str]) -> bool:
        return "all" in self.access or bool(set(roles) & set(self.access))


def _tok(text: str) -> list[str]:
    return [t.strip(".") for t in TOKEN.findall(text.lower()) if t not in STOP]


def _parse(path: Path) -> Document:
    raw = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not m:
        raise ValueError(f"missing front matter: {path}")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    body = m.group(2)
    parts = re.split(r"^## (§\d+(?:\.\d+)?) (.+)$", body, flags=re.M)
    preamble = parts[0].strip()
    sections = []
    for i in range(1, len(parts), 3):
        sec, heading, text = parts[i], parts[i + 1].strip(), parts[i + 2].strip()
        sections.append(Section(meta["doc_id"], meta["version"], sec, heading, text, _tok(heading + " " + text)))
    return Document(meta["doc_id"], meta["version"], meta["title"], meta["status"], meta["effective_date"],
                    meta.get("owner_role", ""), [a.strip() for a in meta.get("access", "all").split(",")], meta,
                    preamble, sections)


def detect_injection(text: str) -> list[str]:
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


class KnowledgeBase:
    def __init__(self, directory: Path):
        self.docs: list[Document] = sorted((_parse(p) for p in directory.glob("*.md")), key=lambda d: (d.doc_id, d.version))
        self._all_sections = [s for d in self.docs for s in d.sections]
        self.avgdl = sum(len(s.tokens) for s in self._all_sections) / max(1, len(self._all_sections))
        df: Counter = Counter()
        for s in self._all_sections:
            df.update(set(s.tokens))
        self.df = df
        self.n = len(self._all_sections)

    def doc(self, doc_id: str, version: str | None = None) -> Document:
        cands = [d for d in self.docs if d.doc_id == doc_id and (version is None or d.version == version)]
        if not cands:
            raise NotFound("document_not_found", f"{doc_id} v{version} not found")
        cands.sort(key=lambda d: (d.status == "approved", d.effective_date))
        return cands[-1]

    def latest_approved(self, doc_id: str) -> Document | None:
        c = [d for d in self.docs if d.doc_id == doc_id and d.status == "approved"]
        return max(c, key=lambda d: d.effective_date) if c else None

    def visible_docs(self, roles: list[str]) -> list[Document]:
        return [d for d in self.docs if d.can_read(roles)]

    def search(self, query: str, roles: list[str], k: int = 5, include_unapproved: bool = False) -> list[dict]:
        q = _tok(query)
        results = []
        for d in self.visible_docs(roles):  # authorization filter BEFORE scoring
            if d.status not in ("approved",) and not include_unapproved:
                continue
            for s in d.sections:
                tf = Counter(s.tokens)
                score = 0.0
                for t in q:
                    if t not in tf:
                        continue
                    idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    f = tf[t]
                    score += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(s.tokens) / self.avgdl))
                if score > 0:
                    results.append((score, d, s))
        results.sort(key=lambda x: -x[0])
        return [self.citation(d, s, score) for score, d, s in results[:k]]

    def citation(self, d: Document, s: Section, score: float | None = None) -> dict:
        flags = self.flags_for(d)
        inj = detect_injection(s.text)
        if inj:
            flags.append("instruction_like_text_ignored")
        return {
            "source_id": d.doc_id, "source_version": d.version, "title": d.title, "section": s.section,
            "heading": s.heading, "excerpt": s.text, "status": d.status, "effective_date": d.effective_date,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "score": round(score, 3) if score else None,
            "flags": flags, "injection_patterns": inj,
        }

    def flags_for(self, d: Document) -> list[str]:
        flags = []
        if d.status == "superseded":
            flags.append("outdated: superseded by v" + d.meta.get("superseded_by", "?"))
        elif d.status != "approved":
            flags.append(f"not_approved: status={d.status}")
        return flags

    def get_excerpt(self, doc_id: str, version: str, section: str, roles: list[str]) -> dict:
        d = self.doc(doc_id, version)
        if not d.can_read(roles):
            raise Forbidden("document_access_denied", f"{doc_id} is restricted to {d.access}")
        for s in d.sections:
            if s.section == section:
                return self.citation(d, s)
        raise NotFound("section_not_found", f"{doc_id} v{version} has no section {section}")

    def validate_citation(self, ref: dict) -> dict:
        """Return VALID / OUTDATED / UNRESOLVED / EXCERPT_MISMATCH for a stored reference."""
        try:
            d = self.doc(ref["source_id"], ref["source_version"])
        except NotFound:
            return {"status": "UNRESOLVED", "reason": "document/version not found"}
        sec = next((s for s in d.sections if s.section == ref["section"]), None)
        if sec is None:
            return {"status": "UNRESOLVED", "reason": "section not found"}
        if ref.get("excerpt") and ref["excerpt"].strip() not in sec.text:
            return {"status": "EXCERPT_MISMATCH", "reason": "stored excerpt not present in source section"}
        if d.status != "approved":
            return {"status": "OUTDATED" if d.status == "superseded" else "NOT_APPROVED", "reason": f"document status {d.status}"}
        return {"status": "VALID", "reason": ""}

    def conflicts(self) -> list[dict]:
        """Superseded versions whose same-numbered sections differ from the current approved version."""
        out = []
        for d in self.docs:
            if d.status != "superseded":
                continue
            cur = self.latest_approved(d.doc_id)
            if not cur:
                continue
            for s in d.sections:
                cs = next((c for c in cur.sections if c.section == s.section), None)
                if cs and cs.text != s.text:
                    out.append({"doc_id": d.doc_id, "outdated_version": d.version, "current_version": cur.version,
                                "section": s.section, "outdated_text": s.text, "current_text": cs.text})
        return out


@lru_cache(maxsize=4)
def _kb(path: str) -> KnowledgeBase:
    return KnowledgeBase(Path(path))


def get_kb() -> KnowledgeBase:
    return _kb(str(get_settings().data_dir / "knowledge"))
