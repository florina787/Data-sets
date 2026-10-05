"""Chunking + partitioned BM25 index.

Chunks are stored in partitions keyed by access label (firm, practice:X, client:Y, matter:Z).
The index exposes NO global search: callers must name the partitions, and the retriever only names
partitions present in a sealed AccessScope. Partitions that are not permitted are never read or scored,
and corpus statistics (IDF) are computed only over the permitted partitions so unauthorised documents
cannot influence ranking either.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

STOPWORDS = set("""a an the and or of to in on for by with as at from is are be been this that these those it its
shall will may any all such other than which who whom into upon our your their we you they his her not no
under over per following within without between each either party parties agreement""".split())

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    out = []
    for t in TOKEN_RE.findall(text.lower()):
        if t in STOPWORDS or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    section_id: str
    title: str
    heading: str
    text: str
    access_label: str
    sensitivity: str
    matter_id: str | None
    client_id: str | None
    practice_id: str | None
    kind: str
    tokens: tuple[str, ...] = field(repr=False, default=())


def chunk_sections(doc_id: str, title: str, sections, meta: dict, max_words: int = 120, overlap: int = 20) -> list[Chunk]:
    chunks: list[Chunk] = []
    for s in sections:
        words = s.text.split()
        if not words:
            continue
        windows = [words] if len(words) <= max_words else [
            words[i:i + max_words] for i in range(0, len(words), max_words - overlap)]
        for n, w in enumerate(windows):
            text = " ".join(w)
            chunks.append(Chunk(chunk_id=f"{doc_id}#{s.section_id}#{n}", doc_id=doc_id, section_id=s.section_id,
                                title=title, heading=s.heading, text=text,
                                tokens=tuple(tokenize(f"{title} {s.heading} {text}")), **meta))
    return chunks


class PartitionedIndex:
    def __init__(self) -> None:
        self._partitions: dict[str, list[Chunk]] = defaultdict(list)
        self._df: dict[str, Counter] = defaultdict(Counter)
        self._len: dict[str, int] = defaultdict(int)
        self.read_log: list[str] = []  # partitions read; used by isolation tests and audit

    def add(self, chunk: Chunk) -> None:
        self._partitions[chunk.access_label].append(chunk)
        self._df[chunk.access_label].update(set(chunk.tokens))
        self._len[chunk.access_label] += len(chunk.tokens)

    def partitions(self) -> list[str]:
        return sorted(self._partitions)

    def partition_size(self, label: str) -> int:
        return len(self._partitions.get(label, []))

    def search(self, partitions: frozenset[str], query: str, predicate, top_k: int = 5,
               k1: float = 1.4, b: float = 0.75) -> list[tuple[float, Chunk]]:
        q = tokenize(query)
        if not q:
            return []
        labels = sorted(p for p in partitions if p in self._partitions)
        self.read_log.extend(labels)
        candidates = [c for lab in labels for c in self._partitions[lab] if predicate(c)]
        if not candidates:
            return []
        n = len(candidates)
        df: Counter = Counter()
        for c in candidates:
            df.update(set(c.tokens) & set(q))
        avgdl = sum(len(c.tokens) for c in candidates) / n
        scored = []
        for c in candidates:
            tf = Counter(c.tokens)
            dl = len(c.tokens)
            s = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / avgdl))
            if s > 0:
                scored.append((round(s, 6), c))
        scored.sort(key=lambda x: (-x[0], x[1].chunk_id))
        return scored[:top_k]
