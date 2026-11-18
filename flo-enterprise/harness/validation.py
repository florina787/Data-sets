"""Output validation: numeric grounding of narratives against tool-produced facts."""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

NUM_RX = re.compile(r"(-?\$?\d[\d,]*(?:\.\d+)?)\s?(%|bps|bp|bn|billion|b\b|m\b|million|k\b|pp)?", re.IGNORECASE)


def _walk_numbers(obj: Any) -> Iterable[float]:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
    elif isinstance(obj, str):
        try:
            yield float(obj)
        except ValueError:
            for m in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", obj):
                yield float(m.group(0).replace(",", ""))
            for m in re.finditer(r"-?\d+(?:\.\d+)?", obj):
                yield float(m.group(0))
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_numbers(v)


def ungrounded_numbers(narrative: str, facts: Any, extra_allowed: Iterable[float] = ()) -> list[str]:
    """Return number tokens in the narrative that cannot be matched to any fact value (allowing unit scaling and
    rounding). Years, ordinals and small counts that appear in facts are matched like any other number."""
    values = list(_walk_numbers(facts)) + list(extra_allowed)
    bad = []
    for mt in NUM_RX.finditer(narrative):
        raw, unit = mt.group(1), (mt.group(2) or "").lower()
        try:
            x = float(raw.replace("$", "").replace(",", ""))
        except ValueError:
            continue
        if 1900 <= x <= 2100 and unit == "":
            continue  # calendar years
        candidates = [x]
        if unit in ("%", "pp"):
            candidates += [x / 100]
        if unit in ("bn", "billion", "b"):
            candidates += [x * 1e9]
        if unit in ("m", "million"):
            candidates += [x * 1e6]
        if unit == "k":
            candidates += [x * 1e3]
        if unit in ("bps", "bp"):
            candidates += [x / 10000]
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        ok = False
        for c in candidates:
            for v in values:
                tol = max(abs(v) * 0.006, 0.5 * 10 ** (-decimals) * (abs(c) / abs(x) if x else 1))
                if abs(c - v) <= tol or abs(abs(c) - abs(v)) <= tol:
                    ok = True
                    break
            if ok:
                break
        if not ok:
            bad.append(mt.group(0).strip())
    return bad
