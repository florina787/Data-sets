"""Paragraph-level chunking.

Each paragraph becomes its own chunk so a passage's embedding is not diluted
by unrelated neighbours (measured: a resume line scored 0.27 against a
paraphrased query on its own, 0.17 when packed with the rest of the resume).
Fragments shorter than ``min_chars`` (headings, names) are merged into the
following paragraph. Paragraphs longer than ``size`` are split on line, then
sentence boundaries, with ``overlap`` characters carried between pieces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extract import Page


@dataclass
class ChunkText:
    page: int | None
    ordinal: int
    text: str


def _pieces(text: str, size: int) -> list[str]:
    """Break text into units no longer than size: lines, then sentences, then hard cuts."""
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) <= size:
            out.append(line)
            continue
        for s in re.split(r"(?<=[.!?;])\s+", line):
            while len(s) > size:
                out.append(s[:size])
                s = s[size:]
            if s:
                out.append(s)
    return out


def _split_long(paragraph: str, size: int, overlap: int) -> list[str]:
    chunks, cur = [], ""
    for p in _pieces(paragraph, size):
        if cur and len(cur) + len(p) + 1 > size:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            tail = tail[tail.find(" ") + 1 :] if " " in tail else tail
            cur = f"{tail}\n{p}".strip() if len(tail) + len(p) + 1 <= size else p
        else:
            cur = f"{cur}\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def chunk_pages(pages: list[Page], size: int = 900, overlap: int = 150, min_chars: int = 60) -> list[ChunkText]:
    chunks: list[ChunkText] = []
    ordinal = 0
    for page in pages:
        carry = ""
        for para in re.split(r"\n\s*\n", page.text):
            para = para.strip()
            if not para:
                continue
            para = f"{carry}\n{para}" if carry else para
            if len(para) < min_chars:
                carry = para
                continue
            carry = ""
            for piece in _split_long(para, size, overlap) if len(para) > size else [para]:
                chunks.append(ChunkText(page.number, ordinal, piece))
                ordinal += 1
        if carry:
            if chunks and chunks[-1].page == page.number and len(chunks[-1].text) + len(carry) + 1 <= size:
                chunks[-1].text += "\n" + carry
            else:
                chunks.append(ChunkText(page.number, ordinal, carry))
                ordinal += 1
    return chunks
