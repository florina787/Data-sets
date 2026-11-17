"""Provider abstraction: caching, retries, rate limiting, freshness, provenance."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from flowwealth.contracts import DataStatus, Provenance, utcnow

BAR_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]


class ProviderError(RuntimeError):
    pass


class RateLimiter:
    """Token bucket: at most ``rate`` calls per ``per`` seconds."""

    def __init__(self, rate: int, per: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.rate, self.per, self.clock, self.sleep = rate, per, clock, sleep
        self.tokens = float(rate)
        self.last = clock()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            while True:
                now = self.clock()
                self.tokens = min(self.rate, self.tokens + (now - self.last) * self.rate / self.per)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                self.sleep((1 - self.tokens) * self.per / self.rate)


@dataclass
class FetchResult:
    frame: pd.DataFrame
    provenance: Provenance


@dataclass
class MarketDataProvider(ABC):
    name: str
    license_note: str
    cache_dir: Path | None = None
    freshness: timedelta = timedelta(days=1)
    max_retries: int = 3
    backoff_s: float = 1.0
    limiter: RateLimiter = field(default_factory=lambda: RateLimiter(5, 60))
    native_status: DataStatus = DataStatus.HISTORICAL

    @abstractmethod
    def _fetch(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Return columns BAR_COLUMNS (date naive, exchange-local)."""

    def _cache_path(self, ticker: str, start: str, end: str) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha256(json.dumps([self.name, ticker, start, end]).encode()).hexdigest()[:24]
        return Path(self.cache_dir) / self.name / f"{key}.parquet"

    def get_daily(self, ticker: str, start: str, end: str) -> FetchResult:
        path = self._cache_path(ticker, start, end)
        if path and path.exists():
            meta = json.loads(path.with_suffix(".json").read_text())
            fetched = pd.Timestamp(meta["retrieved_at"]).to_pydatetime()
            age = utcnow() - fetched
            if age <= self.freshness:
                status = self.native_status
            else:
                # Stale cache is still usable for research but is labelled CACHED, never LIVE.
                status = DataStatus.CACHED
            return FetchResult(pd.read_parquet(path), Provenance(
                source=f"{self.name} (cache)", retrieved_at=fetched, status=status,
                license_note=self.license_note))

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                self.limiter.acquire()
                df = self._fetch(ticker, start, end)
                missing = set(BAR_COLUMNS) - set(df.columns)
                if missing:
                    raise ProviderError(f"{self.name}: missing columns {missing}")
                df = df[BAR_COLUMNS]
                prov = Provenance(source=self.name, retrieved_at=utcnow(),
                                  status=self.native_status, license_note=self.license_note)
                if path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_parquet(path, index=False)
                    path.with_suffix(".json").write_text(json.dumps(
                        {"retrieved_at": prov.retrieved_at.isoformat(), "status": prov.status.value}))
                return FetchResult(df, prov)
            except Exception as e:  # noqa: BLE001 - retried and re-raised
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.backoff_s * 2 ** attempt)
        raise ProviderError(f"{self.name} failed for {ticker}: {last_err}") from last_err
