"""Load configurable sample model pricing from ``config/model_pricing.json``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


class PricingError(ValueError):
    """Raised when the pricing file is missing or malformed."""


@lru_cache(maxsize=8)
def _load(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise PricingError(f"Pricing file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    for name, model in data.get("models", {}).items():
        for key in ("input_per_mtok", "cached_input_per_mtok", "output_per_mtok", "latency_ms_per_call"):
            if not isinstance(model.get(key), (int, float)) or model[key] < 0:
                raise PricingError(f"Model '{name}' has invalid '{key}'")
    return data


def load_pricing(path: str | Path | None = None) -> dict[str, Any]:
    return _load(str(path or get_settings().pricing_file))


def model_price(pricing: dict[str, Any], name: str) -> dict[str, Any]:
    try:
        return pricing["models"][name]
    except KeyError as exc:
        raise PricingError(f"Unknown model '{name}'. Available: {sorted(pricing['models'])}") from exc
