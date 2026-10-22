"""Token accounting.

Gemini's streamed responses attach `usage_metadata` to chunks and the counts are
**cumulative** (each chunk repeats the running totals; the last chunk has the
final totals). Summing chunk usage therefore over-counts. `aggregate_stream_usage`
takes the maximum seen per field, which equals the final totals and is robust to
chunks that omit usage.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens, self.total_tokens + other.total_tokens)


def usage_from_metadata(meta) -> Usage:
    if meta is None:
        return Usage()
    get = (lambda k: meta.get(k)) if isinstance(meta, dict) else (lambda k: getattr(meta, k, None))
    inp = get("prompt_token_count") or 0
    out = (get("candidates_token_count") or 0) + (get("thoughts_token_count") or 0)
    total = get("total_token_count") or (inp + out)
    return Usage(int(inp), int(out), int(total))


def aggregate_stream_usage(chunk_metadata: list) -> Usage:
    """Final usage of a streamed response whose chunks carry cumulative counts."""
    best = Usage()
    for meta in chunk_metadata:
        u = usage_from_metadata(meta)
        best = Usage(max(best.input_tokens, u.input_tokens), max(best.output_tokens, u.output_tokens), max(best.total_tokens, u.total_tokens))
    return best


def estimate_cost(usage: Usage, input_per_mtok: float, output_per_mtok: float) -> float:
    return round(usage.input_tokens / 1e6 * input_per_mtok + usage.output_tokens / 1e6 * output_per_mtok, 6)
