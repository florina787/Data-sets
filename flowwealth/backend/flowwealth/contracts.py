"""Shared data contracts.

Every market record, forecast and scenario carries a ``DataStatus`` so the API
and the UI can never present delayed, cached, synthetic or hypothetical data as
live. Timestamps are timezone-aware UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DataStatus(str, Enum):
    LIVE = "LIVE"                  # streamed within the provider's freshness SLA
    DELAYED = "DELAYED"            # exchange-delayed quote (e.g. 15 min)
    CACHED = "CACHED"              # served from local cache, older than freshness SLA
    HISTORICAL = "HISTORICAL"      # end-of-day / archived history
    SYNTHETIC = "SYNTHETIC"        # generated for engineering tests; no market meaning
    HYPOTHETICAL = "HYPOTHETICAL"  # what-if scenario output; never a fact


class Horizon(str, Enum):
    SCALP = "scalp"        # seconds-minutes; requires licensed tick/L2 feed
    INTRADAY = "intraday"
    SWING = "swing"        # days-weeks
    POSITION = "position"  # weeks-months
    LONG_TERM = "long_term"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Provenance(BaseModel):
    source: str
    retrieved_at: datetime
    status: DataStatus
    license_note: str = ""
    url: str | None = None

    @field_validator("retrieved_at")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return v


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


class PredictionIn(BaseModel):
    """A forecast as it must be recorded *before* its outcome is knowable."""

    model_version: str
    strategy_id: str
    ticker: str
    horizon: Horizon
    horizon_bars: int = Field(gt=0, description="Forecast horizon in trading bars")
    input_cutoff: datetime = Field(description="Latest timestamp of any input used")
    target_time: datetime = Field(description="When the outcome becomes observable")
    regime: str = "unknown"
    forecast_return: float | None = None
    prob_up: float | None = Field(default=None, ge=0, le=1)
    uncertainty: float | None = Field(default=None, ge=0)
    calibrated: bool = False
    bull_thesis: str = ""
    bear_thesis: str = ""
    judge_decision: Decision = Decision.ABSTAIN
    risk_assessment: str = ""
    sources: list[str] = Field(default_factory=list)
    data_status: DataStatus

    @field_validator("input_cutoff", "target_time")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return v
