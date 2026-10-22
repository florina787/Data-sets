"""JSON-safe serialization of workflow state (Pydantic, dataclasses, enums, dates, numpy)."""

from __future__ import annotations

import dataclasses
import math
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

_SKIP_KEYS = {"artifacts"}


def to_jsonable(obj: Any, _depth: int = 0) -> Any:
    if _depth > 30:
        return str(obj)
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, BaseModel):
        return to_jsonable(obj.model_dump(mode="json"), _depth + 1)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        if hasattr(obj, "to_dict"):
            return to_jsonable(obj.to_dict(), _depth + 1)
        return {f.name: to_jsonable(getattr(obj, f.name), _depth + 1) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v, _depth + 1) for k, v in obj.items() if k not in _SKIP_KEYS}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v, _depth + 1) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        try:
            return to_jsonable(obj.item(), _depth + 1)
        except Exception:
            pass
    if hasattr(obj, "to_dict"):  # pandas
        try:
            return to_jsonable(obj.to_dict(orient="records"), _depth + 1)
        except TypeError:
            return to_jsonable(obj.to_dict(), _depth + 1)
    return str(obj)
