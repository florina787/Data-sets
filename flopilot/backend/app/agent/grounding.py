"""Final-result validation for model-written text: every number must come from a tool result."""
from __future__ import annotations

import re
from typing import Any

_NUM = re.compile(r"(?<![\w.])[-+]?\$?\(?\d[\d,]*(?:\.\d+)?%?\)?(?![\w])")


def _collect(value: Any, out: set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        v = float(value)
        for candidate in (v, v * 100, abs(v), abs(v) * 100):
            for digits in (0, 1, 2, 3, 4):
                out.add(round(candidate, digits))
        return
    if isinstance(value, dict):
        for v in value.values():
            _collect(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect(v, out)
    elif isinstance(value, str):
        for m in re.finditer(r"\d+(?:\.\d+)?", value.replace(",", "")):
            out.add(float(m.group()))


def ungrounded_numbers(text: str, tool_outputs: list[Any], extra_allowed: set[float] | None = None) -> list[str]:
    allowed: set[float] = set(extra_allowed or set())
    for out in tool_outputs:
        _collect(out, allowed)
    bad = []
    for m in _NUM.finditer(text):
        raw = m.group()
        cleaned = raw.replace("$", "").replace(",", "").replace("(", "").replace(")", "").replace("+", "")
        is_pct = cleaned.endswith("%")
        cleaned = cleaned.rstrip("%")
        try:
            v = abs(float(cleaned))
        except ValueError:
            continue
        if v <= 12 and not is_pct and float(v).is_integer():
            continue  # small counts/ordinals ("top 3", "2 sheets") are not treated as claims
        if 1900 <= v <= 2100 and float(v).is_integer():
            continue  # years
        decimals = len(cleaned.split(".")[1]) if "." in cleaned else 0
        if round(v, decimals) in allowed or v in allowed:
            continue
        bad.append(raw)
    return bad
