"""Deterministic hashing embedder (char n-grams + words, 384 dims, L2-normalized). It needs no external model and is
multilingual at the character level; quality is below neural embeddings. The `Embedder` interface allows a provider
embedder (e.g. Bedrock Titan) and pgvector storage in production."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata

DIM = 384


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", _norm(text), flags=re.UNICODE)


def embed(text: str) -> list[float]:
    v = [0.0] * DIM
    toks = tokens(text)
    feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    for t in toks:
        padded = f" {t} "
        feats += [padded[i:i + 3] for i in range(len(padded) - 2)]
    for f in feats:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        v[h % DIM] += 1.0 if (h >> 32) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / n, 6) for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
