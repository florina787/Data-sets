"""Numeric grounding check for model-written text.

Every number in a model explanation must correspond to a number in the verified
facts (allowing the formatting variants a writer would use: rounding, percent
conversion). Small ordinals (1-10) and numbers that appear verbatim in the facts
text (dates, IDs) are allowed. Anything else is treated as a fabricated statistic.
"""

from __future__ import annotations

import json
import re

_NUM = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)*(?:\.\d+)?")


def _variants(x: float) -> set[str]:
    out: set[str] = set()
    for v in (x, x * 100):
        for d in (0, 1, 2, 3, 4):
            s = f"{round(v, d):.{d}f}"
            out.add(s)
            out.add(s.lstrip("-+"))
    out.add(f"{int(x):,}" if float(x).is_integer() else str(x))
    return out


def allowed_numbers(facts: object, extra_text: str = "") -> set[str]:
    text = json.dumps(facts, default=str) + " " + extra_text
    allowed: set[str] = set()
    for tok in _NUM.findall(text):
        clean = tok.replace(",", "")
        allowed.add(tok)
        allowed.add(clean)
        try:
            allowed |= _variants(float(clean))
        except ValueError:
            pass
    allowed |= {str(i) for i in range(0, 11)} | {"95"}  # small ordinals; "95% CI" is a method constant
    return allowed


def ungrounded_numbers(text: str, allowed: set[str]) -> list[str]:
    bad = []
    for tok in _NUM.findall(text):
        t = tok.lstrip("+")
        if t in allowed or t.replace(",", "") in allowed or t.lstrip("-") in allowed:
            continue
        bad.append(tok)
    return bad
