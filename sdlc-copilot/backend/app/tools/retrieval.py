"""Lightweight local document retrieval (BM25 over heading-level sections).

Documents are untrusted data: retrieved text is quoted as evidence and never
interpreted as instructions to the platform or to a model.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import FIXTURES

TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
STOP = set("a an and are as at be by for from in is it of on or that the to with must not this "
           "any be may unless when which".split())


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


@dataclass(frozen=True)
class Section:
    doc_id: str
    title: str
    version: str
    effective: str
    section: str
    heading: str
    text: str

    @property
    def ref(self) -> str:
        return f"{self.doc_id} v{self.version} §{self.section}"


def _parse(path: Path) -> list[Section]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not match:
        raise ValueError(f"{path.name}: missing front matter")
    meta = dict(
        (k.strip(), v.strip().strip('"')) for k, v in
        (line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    )
    sections: list[Section] = []
    for block in re.split(r"\n(?=## )", match.group(2)):
        heading = re.match(r"## (\d+)\.\s*(.+)", block)
        if not heading:
            continue
        body = block.split("\n", 1)[1].strip() if "\n" in block else ""
        sections.append(Section(meta["doc_id"], meta["title"], meta["version"],
                                meta.get("effective", ""), heading.group(1),
                                heading.group(2).strip(), body))
    return sections


class Index:
    def __init__(self, docs_dir: Path) -> None:
        self.sections = [s for p in sorted(docs_dir.glob("*.md")) for s in _parse(p)]
        self.tokens = [tokenize(f"{s.heading} {s.heading} {s.text}") for s in self.sections]
        self.avg_len = sum(map(len, self.tokens)) / max(len(self.tokens), 1)
        df: Counter[str] = Counter()
        for toks in self.tokens:
            df.update(set(toks))
        n = len(self.tokens)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 3, min_score: float = 1.0) -> list[dict]:
        q = tokenize(query)
        scored = []
        for section, toks in zip(self.sections, self.tokens, strict=True):
            tf = Counter(toks)
            score = 0.0
            for term in q:
                if term in tf:
                    f = tf[term]
                    score += self.idf[term] * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(toks) / self.avg_len))
            if score >= min_score:
                scored.append((score, section))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "ref": s.ref, "doc_id": s.doc_id, "title": s.title, "version": s.version,
                "effective": s.effective, "section": s.section, "heading": s.heading,
                "excerpt": s.text[:600], "score": round(score, 2),
            }
            for score, s in scored[:k]
        ]

    def documents(self) -> list[dict]:
        seen: dict[str, dict] = {}
        for s in self.sections:
            doc = seen.setdefault(s.doc_id, {"doc_id": s.doc_id, "title": s.title,
                                             "version": s.version, "effective": s.effective,
                                             "sections": []})
            doc["sections"].append({"section": s.section, "heading": s.heading, "text": s.text})
        return list(seen.values())


@lru_cache(maxsize=1)
def get_index() -> Index:
    return Index(FIXTURES / "docs")
