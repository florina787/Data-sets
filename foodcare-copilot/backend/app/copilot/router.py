"""Deterministic question understanding: entity extraction and intent scoring.

Questions are untrusted text. They are only matched against fixed vocabularies;
nothing in a question is executed or used to build queries except validated IDs
and values from these vocabularies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SKU_ALIASES = [
    ("FS-SPARKLIME-355", ("sparkling lime", "sparkling", "lime", "sparklime")),
    ("FS-MANGO-355", ("mango",)),
    ("FS-ORANGE-355", ("orange",)),
    ("FS-APPLE-355", ("apple",)),
    ("BH-COLDBREW-300", ("cold brew", "coldbrew", "coffee", "brewhouse")),
    ("NT-OATMILK-1L", ("oat milk", "oatmilk", "oat", "nutriterra")),
]
PROVINCE_NAMES = {"ontario": "ON", "quebec": "QC", "québec": "QC", "british columbia": "BC", "alberta": "AB",
                  "manitoba": "MB", "nova scotia": "NS"}
PROVINCE_CODE = re.compile(r"\b(ON|QC|BC|AB|MB|NS)\b")
WAREHOUSES = {"toronto": "DC-TOR", "montreal": "DC-MTL", "montréal": "DC-MTL", "vancouver": "DC-VAN"}
CHANNELS = {"retail": "retail", "grocery": "retail", "marketplace": "marketplace", "web store": "web",
            "online store": "web", "webstore": "web", "website": "web", "e-commerce": "web"}

INTENTS: dict[str, tuple[str, ...]] = {
    "sales": ("sales", "sell", "revenue", "selling", "sold", "units", "trend", "top product", "best seller",
              "bestseller", "best-selling", "turnover", "growth"),
    "campaign": ("campaign", "promotion", "promo", "uplift", "offer", "buy 2", "buy two", "b2g1", "3-for-2",
                 "weekend", "discount"),
    "inventory": ("stock", "inventory", "warehouse", "reorder", "run out", "running out", "running low", "low on",
                  "low stock", "days of cover", "supply", "inbound", "purchase order", "out of stock", "shortage",
                  "stock-out", "replenish"),
    "compliance": ("allergen", "ingredient", "compliance", "label", "listing", "regulatory", "gluten", "recall"),
    "delivery": ("release", "deploy", "gate", "blocked", "approval", "approve", "pipeline", "requirement",
                 "test", "build", "change set", "patch", "regression", "delivery run", "brief"),
    "incident": ("incident", "outage", "timeout", "failure", "failing", "error rate", "rollback", "roll back",
                 "root cause", "checkout errors", "outage"),
    "policy": ("policy", "returns", "refund", "cancellation", "rule", "standard", "guideline", "what does the",
               "allowed to", "stacking"),
    "overview": ("summary", "overview", "how are we doing", "briefing", "focus on", "priorities", "what should i",
                 "status of the business", "headlines", "today"),
    "help": ("what can you do", "help", "how do i use", "examples"),
}


@dataclass
class Parsed:
    question: str
    intents: list[str]
    scores: dict[str, int]
    skus: list[str] = field(default_factory=list)
    provinces: list[str] = field(default_factory=list)
    warehouses: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    weeks: int = 4
    run_id: str | None = None
    incident_id: str | None = None
    release_id: str | None = None

    def entities(self) -> dict:
        return {k: v for k, v in {"skus": self.skus, "provinces": self.provinces, "warehouses": self.warehouses,
                                  "channels": self.channels, "weeks": self.weeks, "run_id": self.run_id,
                                  "incident_id": self.incident_id, "release_id": self.release_id}.items() if v}


def _has(text: str, keyword: str) -> bool:
    """Whole-word match with an optional plural 's' ("test" must not match "latest")."""
    return re.search(rf"(?<![\w-]){re.escape(keyword)}s?(?![\w-])", text) is not None


def parse(question: str) -> Parsed:
    text = question.lower()
    skus: list[str] = []
    remaining = text
    for sku, aliases in SKU_ALIASES:
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", remaining):
                skus.append(sku)
                remaining = re.sub(rf"\b{re.escape(alias)}\b", " ", remaining)
                break
    provinces = [code for name, code in PROVINCE_NAMES.items() if name in text]
    provinces += [m for m in PROVINCE_CODE.findall(question) if m not in provinces]
    warehouses = [code for name, code in WAREHOUSES.items() if name in text]
    warehouses += [m.upper() for m in re.findall(r"\bdc-(?:tor|mtl|van)\b", text) if m.upper() not in warehouses]
    channels = sorted({code for name, code in CHANNELS.items() if name in text})
    weeks = 4
    if m := re.search(r"last (\d{1,2}) weeks?", text):
        weeks = int(m.group(1))
    elif "last week" in text:
        weeks = 1
    elif "quarter" in text or "last 3 months" in text:
        weeks = 8
    scores = {intent: sum(1 for kw in kws if _has(text, kw)) for intent, kws in INTENTS.items()}
    if any(w in text for w in ("enough", "risk", "run out", "running out")) and scores["campaign"]:
        scores["inventory"] += 1
    if skus and any(w in text for w in ("ingredient", "allergen", "contain")):
        scores["compliance"] += 1
    ranked = [i for i, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s > 0]
    if not ranked and warehouses:
        ranked = ["inventory"]
    elif not ranked and (skus or provinces or channels) and _has(text, "low"):
        ranked = ["inventory"]
    if "help" in ranked and len(ranked) > 1:
        ranked.remove("help")
    if len(ranked) > 1 and scores[ranked[1]] < scores[ranked[0]]:
        ranked = ranked[:1]  # a weaker secondary intent would add unrelated material
    run_id = (m.group(0).upper() if (m := re.search(r"\brun-[0-9a-f]{10}\b", text)) else None)
    incident_id = (m.group(0).upper() if (m := re.search(r"\binc-[0-9a-f]{10}\b", text)) else None)
    release_id = (m.group(0).upper() if (m := re.search(r"\brel-[0-9a-z]{6,12}\b", text)) else None)
    return Parsed(question, ranked[:2], scores, skus, provinces, warehouses, channels, max(1, min(weeks, 8)),
                  run_id, incident_id, release_id)
