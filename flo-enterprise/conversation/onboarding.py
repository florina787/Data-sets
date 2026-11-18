"""Extract figures a business owner states about their own firm ("we manage CAD 500 million with 8 advisors").

Only explicit statements are captured; nothing is inferred. Values are kept in conversation state as user-supplied
inputs for the firm model and are labelled as such everywhere they appear.
"""
from __future__ import annotations

import re

_SCALE = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
_AMOUNT = re.compile(r"(?:CAD|C\$|CA\$|\$)?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(billion|bn|million|mm|mn|thousand|m|b|k)?\b(?!\s?%)", re.I)
_CONTEXT = [
    ("net_flows", r"(net (client )?(in)?flows?|inflows?|new money|net new assets|outflows?|net redemptions)"),
    ("expenses", r"(expenses?|costs?|spend(ing)?|overhead)"),
    ("revenue", r"(revenue|fee income|fees of|earn(ed|s)?|billings?)"),
    ("aum", r"(manag\w*|aum|assets(?: under management)?|book of)"),
]


def _num(raw: str, scale: str | None) -> float:
    v = float(raw.replace(",", ""))
    return v * _SCALE.get((scale or "").lower(), 1.0)


def extract_profile(text: str) -> dict:
    out: dict = {}
    t = text
    for m in _AMOUNT.finditer(t):
        raw, scale = m.group(1), m.group(2)
        prefix = t[max(0, m.start() - 48):m.start()].lower()
        has_money = bool(re.search(r"(cad|c\$|\$)\s?$", t[max(0, m.start() - 5):m.start() + 4].lower())) or "$" in m.group(0) or "cad" in m.group(0).lower()
        if not scale and not has_money:
            continue  # bare numbers ("8 advisors", "2026") are not money
        val = _num(raw, scale)
        if val < 1000:
            continue
        for key, rx in _CONTEXT:
            # nearest keyword wins: look only at the words just before the amount
            if re.search(rx + r"[^.;]{0,32}$", prefix):
                if key == "net_flows" and re.search(r"outflows?|net redemptions", prefix):
                    val = -val
                out.setdefault(key, val)
                break
    m = re.search(r"(\d+(?:\.\d+)?)\s?%\s*(?:average\s+|all[- ]in\s+|management\s+)?(?:fee|management fee)", t, re.I) \
        or re.search(r"fees?\s+(?:rate\s+)?(?:of|is|are|at|around|about|averag\w*)?\s*(\d+(?:\.\d+)?)\s?%", t, re.I)
    if m:
        out["fee_bps"] = round(float(m.group(1)) * 100, 2)
    else:
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s?(?:bps|bp|basis points)\b[^.]{0,20}fee|fees?[^.]{0,20}?(\d{1,3}(?:\.\d+)?)\s?(?:bps|bp|basis points)", t, re.I)
        if m:
            out["fee_bps"] = float(m.group(1) or m.group(2))
    m = re.search(r"(\d{1,3}(?:,\d{3})*|\d+)\s+(?:financial\s+|wealth\s+|investment\s+)?advis[eo]rs?\b", t, re.I)
    if m:
        out["advisors"] = int(m.group(1).replace(",", ""))
    m = re.search(r"(\d{1,3}(?:,\d{3})*|\d+)\s+(?:client\s+)?(?:households|clients|families)\b", t, re.I)
    if m:
        out["clients"] = int(m.group(1).replace(",", ""))
    return out
