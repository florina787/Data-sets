"""Clock abstraction. The demo pins a fixed instant so real dates never break it."""

from __future__ import annotations

from datetime import datetime, timezone


class Clock:
    def __init__(self, fixed_iso: str | None = None) -> None:
        self._fixed = None
        if fixed_iso:
            parsed = datetime.fromisoformat(fixed_iso)
            if parsed.tzinfo is None:
                raise ValueError("Demo clock must include a UTC offset")
            self._fixed = parsed.astimezone(timezone.utc)

    @property
    def is_fixed(self) -> bool:
        return self._fixed is not None

    def now(self) -> datetime:
        return self._fixed or datetime.now(timezone.utc)
