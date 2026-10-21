"""Token usage from streamed model responses, without double counting.

Providers report streaming usage in three shapes:
- cumulative: every chunk carries the running total (Gemini's OpenAI-compatible endpoint: input 8 on every chunk,
  output 14 → 38 → 41 → 41). Summing chunks counts the prompt once per chunk.
- final only: one terminal chunk carries the totals (OpenAI with include_usage).
- incremental: the prompt is reported once and each chunk carries only its new output tokens (Anthropic).

``StreamUsage`` collects every chunk's ``usage_metadata`` and resolves them at the end. Numbers are only ever
provider-reported; when no chunk reports usage the result says so (``mode="missing"``) instead of estimating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

_KEYS = ("input_tokens", "output_tokens")
_DETAIL_KEYS = ("input_token_details", "output_token_details")


@dataclass
class StreamUsage:
    reports: list[dict] = field(default_factory=list)

    def add(self, chunk) -> None:
        u = getattr(chunk, "usage_metadata", None)
        if u:
            self.reports.append(dict(u))

    @property
    def mode(self) -> str:
        r = self.reports
        if not r:
            return "missing"
        if len(r) == 1:
            return "final_only"
        inputs = [int(x.get("input_tokens") or 0) for x in r]
        outputs = [int(x.get("output_tokens") or 0) for x in r]
        # The prompt is the same on every chunk and output never shrinks: running totals.
        if len(set(inputs)) == 1 and inputs[0] > 0 and all(b >= a for a, b in pairwise(outputs)):
            return "cumulative"
        return "incremental"

    def totals(self) -> dict:
        """Resolved usage: {input_tokens, output_tokens, total_tokens, mode, details}."""
        mode, r = self.mode, self.reports
        if mode == "missing":
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "mode": mode, "details": {}}
        if mode in ("final_only", "cumulative"):
            last = r[-1]
            ti, to = int(last.get("input_tokens") or 0), int(last.get("output_tokens") or 0)
            details = {k: last.get(k) for k in _DETAIL_KEYS if last.get(k)}
        else:
            ti = sum(int(x.get("input_tokens") or 0) for x in r)
            to = sum(int(x.get("output_tokens") or 0) for x in r)
            details = {}
            for k in _DETAIL_KEYS:
                merged: dict = {}
                for x in r:
                    for dk, dv in (x.get(k) or {}).items():
                        if isinstance(dv, (int, float)):
                            merged[dk] = merged.get(dk, 0) + dv
                if merged:
                    details[k] = merged
        return {"input_tokens": ti, "output_tokens": to, "total_tokens": ti + to, "mode": mode, "details": details}
