"""Question-level guardrails and answer grounding.

* `_INSTRUCTION_LIKE` is reused verbatim from FloPilot backend/app/workbook/security.py.
* Grounding follows FloPilot backend/app/agent/grounding.py: any number in an LLM-written narrative
  must appear in the tool output it is describing.
"""
from __future__ import annotations

import re

_INSTRUCTION_LIKE = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)|system override|you are now|"
    r"(reveal|print|show|send) (me |us )?(your |the )?(api[ _-]?key|password|secret|system prompt)|"
    r"disregard (the )?(rules|policy)|act as (an? )?(admin|administrator)|developer mode", re.I)
_WRITE_INTENT = re.compile(r"\b(delete|drop|truncate|update|insert|alter|overwrite|modify|change|edit|remove)\b.{0,40}"
                           r"\b(rows?|records?|invoices?|accounts?|tables?|data(base)?|amounts?|status(es)?)\b", re.I)
MAX_QUESTION_CHARS = 1000


def instruction_like(text: str) -> bool:
    return bool(_INSTRUCTION_LIKE.search(text or ""))


def write_intent(text: str) -> bool:
    return bool(_WRITE_INTENT.search(text or ""))


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def _numbers(text: str) -> set[float]:
    out = set()
    for tok in _NUM.findall(text or ""):
        try:
            out.add(round(abs(float(tok.replace(",", ""))), 2))
        except ValueError:
            pass
    return out


def ungrounded_numbers(narrative: str, rows: list[list], extra_allowed: set[float] | None = None) -> set[float]:
    """Numbers in `narrative` that do not appear (to 2 dp, also as %, rounded, or year-like) in `rows`."""
    allowed: set[float] = set(extra_allowed or set())
    for row in rows:
        for v in row:
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float)):
                f = abs(float(v))
                allowed |= {round(f, 2), round(f, 1), round(f), round(f * 100, 1), round(f * 100, 2), round(f * 100),
                            round(f / 1e6, 1), round(f / 1e6, 2), round(f / 1e3, 1)}
            else:
                allowed |= _numbers(str(v))
    small = {float(i) for i in range(0, 13)}  # ordinals / "top 5" / months
    return {n for n in _numbers(narrative) if n not in allowed and n not in small and not (1990 <= n <= 2100)}
