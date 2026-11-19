"""Read Prediction Memory through FLO's database session (used by the governed markets.predictions tool and the API)."""
from __future__ import annotations

from backend.db.session import session_scope
from markets import ledger


def summary(recent: int = 50, ticker: str | None = None) -> dict:
    with session_scope() as s:
        out = ledger.summary(s)
        out["recent"] = ledger.rows(s, ticker=ticker, limit=recent)
        out["data_status"] = "research_result"
        out["classification"] = "public"
        out["note"] = ("historical_replay rows were recorded on a simulated clock over past data before each outcome was resolved; "
                       "they are not forward tests. forward rows require an enabled current-data feed and a promoted model.")
        return out
