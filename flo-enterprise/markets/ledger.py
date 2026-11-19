"""Prediction Memory: the append-only, hash-chained forecast ledger in FLO's database.

Rules (all tested in tests/unit/test_markets_ledger.py):
* A forecast is recorded only if ``feature_cutoff <= now < outcome_due``: inputs existed, the outcome did not.
* Rows can never be updated or deleted: database triggers reject it (migration 0005), and every row's SHA-256 covers its
  content and the previous row's hash, so editing the file directly is detected by ``verify_chain``.
* An outcome is written once, only after ``outcome_due``, from market data available at resolution time.
* ``mode`` is ``historical_replay`` (simulated clock over past data) or ``forward`` (real clock). Replay is never
  presented as forward testing.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.db import models as m
from governance.policy import canonical_json

GENESIS = "0" * 64
MODES = ("historical_replay", "forward")
_lock = threading.Lock()


class RecordingError(ValueError):
    pass


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise RecordingError("timestamps must be timezone-aware")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _body(p: m.MarketPrediction) -> dict:
    return {"id": p.id, "created_at": p.created_at.isoformat(timespec="microseconds"), "mode": p.mode, "model_version": p.model_version,
            "dataset_version": p.dataset_version, "ticker": p.ticker, "horizon_sessions": p.horizon_sessions,
            "feature_cutoff": p.feature_cutoff.isoformat(), "outcome_due": p.outcome_due.isoformat(),
            "predicted_excess_return": p.predicted_excess_return, "predicted_rank_pct": p.predicted_rank_pct,
            "uncertainty": p.uncertainty, "regime": p.regime, "evidence": p.evidence}


def _digest(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + canonical_json(body)).encode()).hexdigest()


def record(s: Session, *, now: datetime, mode: str, model_version: str, dataset_version: str, ticker: str, horizon_sessions: int,
           feature_cutoff: datetime, outcome_due: datetime, predicted_excess_return: float | None, predicted_rank_pct: float | None,
           uncertainty: float | None, regime: str, evidence: dict) -> str:
    if mode not in MODES:
        raise RecordingError(f"mode must be one of {MODES}")
    n, cut, due = _naive_utc(now), _naive_utc(feature_cutoff), _naive_utc(outcome_due)
    if cut > n:
        raise RecordingError("feature_cutoff is after the recording time: inputs cannot postdate the forecast")
    if due <= n:
        raise RecordingError("outcome_due has passed: a forecast must be recorded before its outcome is knowable")
    with _lock:
        if s.get_bind().dialect.name == "postgresql":
            s.execute(text("SELECT pg_advisory_xact_lock(74202)"))
        prev = s.execute(select(m.MarketPrediction.hash).order_by(m.MarketPrediction.seq.desc()).limit(1)).scalar() or GENESIS
        p = m.MarketPrediction(id=f"MP-{uuid.uuid4().hex[:16]}", created_at=n, mode=mode, model_version=model_version,
                               dataset_version=dataset_version, ticker=ticker, horizon_sessions=horizon_sessions, feature_cutoff=cut,
                               outcome_due=due, predicted_excess_return=predicted_excess_return, predicted_rank_pct=predicted_rank_pct,
                               uncertainty=uncertainty, regime=regime, evidence=json.loads(json.dumps(evidence, default=str)),
                               prev_hash=prev, hash="")
        p.hash = _digest(prev, _body(p))
        s.add(p)
        s.flush()
        return p.id


def resolve_due(s: Session, *, now: datetime, lookup: Callable[[str, datetime, datetime, int], dict | None], source: str) -> int:
    """lookup(ticker, feature_cutoff, outcome_due, horizon) -> {"return", "benchmark_return"} or None if not yet observable."""
    n = _naive_utc(now)
    done = select(m.MarketPredictionOutcome.prediction_id)
    due = s.scalars(select(m.MarketPrediction).where(m.MarketPrediction.outcome_due <= n, m.MarketPrediction.id.not_in(done))
                    .order_by(m.MarketPrediction.seq)).all()
    k = 0
    for p in due:
        res = lookup(p.ticker, p.feature_cutoff, p.outcome_due, p.horizon_sessions)
        if res is None:
            continue
        actual, bench = res.get("return"), res.get("benchmark_return")
        excess = None if actual is None or bench is None else actual - bench
        correct = None if excess is None or p.predicted_excess_return is None or excess == 0 else \
            (excess > 0) == (p.predicted_excess_return > 0)
        s.add(m.MarketPredictionOutcome(prediction_id=p.id, resolved_at=n, actual_return=actual, benchmark_return=bench,
                                        actual_excess_return=excess, direction_correct=correct,
                                        abs_error=None if excess is None or p.predicted_excess_return is None
                                        else abs(p.predicted_excess_return - excess),
                                        status="resolved" if actual is not None else "no_data", source=source[:120]))
        k += 1
    s.flush()
    return k


def verify_chain(s: Session) -> dict:
    prev, n = GENESIS, 0
    for p in s.scalars(select(m.MarketPrediction).order_by(m.MarketPrediction.seq)):
        n += 1
        if p.prev_hash != prev or _digest(prev, _body(p)) != p.hash:
            return {"valid": False, "checked": n, "first_invalid_seq": p.seq, "prediction_id": p.id}
        prev = p.hash
    return {"valid": True, "checked": n, "head": prev}


def rows(s: Session, *, model_version: str | None = None, ticker: str | None = None, limit: int = 200) -> list[dict]:
    q = select(m.MarketPrediction, m.MarketPredictionOutcome).outerjoin(
        m.MarketPredictionOutcome, m.MarketPredictionOutcome.prediction_id == m.MarketPrediction.id)
    if model_version:
        q = q.where(m.MarketPrediction.model_version == model_version)
    if ticker:
        q = q.where(m.MarketPrediction.ticker == ticker)
    out = []
    for p, o in s.execute(q.order_by(m.MarketPrediction.seq.desc()).limit(limit)):
        out.append({**_body(p), "seq": p.seq, "hash": p.hash,
                    "outcome": None if o is None else {"resolved_at": o.resolved_at.isoformat(), "actual_return": o.actual_return,
                                                       "benchmark_return": o.benchmark_return, "actual_excess_return": o.actual_excess_return,
                                                       "direction_correct": o.direction_correct, "abs_error": o.abs_error,
                                                       "status": o.status, "source": o.source},
                    "state": "pending" if o is None else o.status})
    return out


def summary(s: Session) -> dict:
    """Counts and accuracy by mode, model and regime, computed from the ledger itself."""
    data = rows(s, limit=10_000_000)
    by: dict[str, dict] = {}

    def acc(key, r):
        b = by.setdefault(key, {"n": 0, "resolved": 0, "correct": 0, "pending": 0, "abs_err": 0.0, "excess_sum": 0.0})
        b["n"] += 1
        o = r["outcome"]
        if o is None:
            b["pending"] += 1
        elif o["direction_correct"] is not None:
            b["resolved"] += 1
            b["correct"] += int(o["direction_correct"])
            b["abs_err"] += o["abs_error"] or 0
    for r in data:
        acc(f"mode:{r['mode']}", r)
        acc(f"model:{r['model_version']}", r)
        acc(f"regime:{r['regime']}", r)
    for b in by.values():
        b["accuracy"] = b["correct"] / b["resolved"] if b["resolved"] else None
        b["mae"] = b["abs_err"] / b["resolved"] if b["resolved"] else None
        del b["abs_err"], b["excess_sum"]
    return {"total": len(data), "groups": by, "chain": verify_chain(s)}
