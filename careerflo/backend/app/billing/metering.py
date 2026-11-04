"""Server-side usage metering: two lifetime free uses per feature, then plan allowances.

Lifecycle of one billable action:

    reserve()  -> counters.reserved += 1 (atomic, conditional UPDATE) + reservation row (unique idempotency key)
    <run the feature>
    commit()   -> reserved -= 1, used += 1, result cached for idempotent replays
    release()  -> reserved -= 1 (failures never consume an allowance)

Concurrency: the conditional ``UPDATE ... WHERE used + reserved < limit`` is evaluated under the row
lock in PostgreSQL (READ COMMITTED re-checks the predicate after waiting) and under the database
write lock in SQLite, so parallel requests can never take more than the allowance.
Idempotency: ``(user_id, feature_id, idempotency_key)`` is unique; a retry of a committed action
replays the stored result without charging again.
Nested work: a feature executed inside another metered action (e.g. job matching inside resume
optimisation) is not charged separately (see ``metered``).
"""
from __future__ import annotations

import contextvars
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..features import ENTITLED_STATUSES, FEATURES, GRACE_STATUSES, PLANS, Plan
from ..models import MonthlyUsage, Subscription, TrialUsage, UsageEvent, UsageReservation, utcnow


class MeteringError(Exception):
    status_code = 400
    code = "metering_error"

    def __init__(self, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class FeatureExhausted(MeteringError):
    status_code = 402
    code = "feature_exhausted"


class ReservationInFlight(MeteringError):
    status_code = 409
    code = "request_in_progress"


class UnknownFeature(MeteringError):
    status_code = 404
    code = "unknown_feature"


@dataclass
class Reservation:
    id: uuid.UUID | None
    user_id: uuid.UUID
    feature_id: str
    source: str  # trial | plan | included (nested) | replay
    period: str | None = None
    replay_result: dict[str, Any] | None = None
    result: dict[str, Any] | None = field(default=None)

    @property
    def is_replay(self) -> bool:
        return self.source == "replay"


_active_scope: contextvars.ContextVar[str | None] = contextvars.ContextVar("metering_scope", default=None)


def current_period(now: datetime | None = None) -> str:
    return (now or utcnow()).strftime("%Y-%m")


def _insert(db: Session):
    return pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert


def active_plan(db: Session, user_id: uuid.UUID) -> tuple[Plan, Subscription | None]:
    """The plan the user is entitled to *right now*, computed only from webhook-synced state."""
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.updated_at.desc())
    ).all()
    now = utcnow()
    best: tuple[Plan, Subscription | None] = (PLANS["free"], None)
    for s in subs:
        if s.status not in ENTITLED_STATUSES | GRACE_STATUSES:
            continue
        end = s.current_period_end
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end is not None and end + timedelta(days=3) < now:
            continue  # stale row: never trust a subscription past its paid period
        plan = PLANS.get(s.plan_id)
        if plan and plan.priority > best[0].priority:
            best = (plan, s)
    return best


def _ensure_rows(db: Session, user_id: uuid.UUID, feature_id: str, period: str | None) -> None:
    ins = _insert(db)
    db.execute(ins(TrialUsage).values(user_id=user_id, feature_id=feature_id, used=0, reserved=0)
               .on_conflict_do_nothing())
    if period:
        db.execute(ins(MonthlyUsage).values(user_id=user_id, feature_id=feature_id, period=period, used=0, reserved=0)
                   .on_conflict_do_nothing())


def _existing(db: Session, user_id: uuid.UUID, feature_id: str, key: str) -> UsageReservation | None:
    return db.scalar(select(UsageReservation).where(
        UsageReservation.user_id == user_id, UsageReservation.feature_id == feature_id,
        UsageReservation.idempotency_key == key))


def reserve(db: Session, user_id: uuid.UUID, feature_id: str, idempotency_key: str | None = None) -> Reservation:
    feature = FEATURES.get(feature_id)
    if feature is None:
        raise UnknownFeature(f"Unknown feature '{feature_id}'")
    key = (idempotency_key or uuid.uuid4().hex)[:100]

    prior = _existing(db, user_id, feature_id, key)
    if prior is not None:
        if prior.status == "committed":
            _log(db, user_id, feature_id, prior.source, "replayed", prior.id)
            db.commit()
            return Reservation(prior.id, user_id, feature_id, "replay", prior.period, prior.result or {})
        raise ReservationInFlight("This request is already being processed. Retry shortly.")

    plan, _sub = active_plan(db, user_id)
    period = current_period()
    _ensure_rows(db, user_id, feature_id, period)

    source: str | None = None
    res = db.execute(update(TrialUsage)
                     .where(and_(TrialUsage.user_id == user_id, TrialUsage.feature_id == feature_id,
                                 TrialUsage.used + TrialUsage.reserved < feature.trial_limit))
                     .values(reserved=TrialUsage.reserved + 1))
    if res.rowcount == 1:
        source = "trial"
    else:
        limit = plan.monthly_limits.get(feature_id, 0)
        if limit > 0:
            res = db.execute(update(MonthlyUsage)
                             .where(and_(MonthlyUsage.user_id == user_id, MonthlyUsage.feature_id == feature_id,
                                         MonthlyUsage.period == period,
                                         MonthlyUsage.used + MonthlyUsage.reserved < limit))
                             .values(reserved=MonthlyUsage.reserved + 1))
            if res.rowcount == 1:
                source = "plan"
    if source is None:
        db.rollback()
        _log(db, user_id, feature_id, "none", "denied", None, {"plan": plan.id})
        db.commit()
        if plan.id == "free":
            msg = f"You've completed your two free trials of {feature.name}. Upgrade to continue."
        elif plan.monthly_limits.get(feature_id, 0) == 0:
            msg = f"{feature.name} is not included in the {plan.name} plan. Upgrade to continue."
        else:
            msg = f"You've used this month's {feature.name} allowance on the {plan.name} plan."
        raise FeatureExhausted(msg, feature_id=feature_id, plan=plan.id, upgrade_url="/pricing")

    row = UsageReservation(user_id=user_id, feature_id=feature_id, idempotency_key=key, source=source,
                           period=period if source == "plan" else None, status="reserved")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request with the same idempotency key won the race; our counter increment
        # is rolled back with this transaction.
        db.rollback()
        return reserve(db, user_id, feature_id, key)
    return Reservation(row.id, user_id, feature_id, source, row.period)


def _counter_update(r: Reservation, *, used_delta: int):
    if r.source == "trial":
        return (update(TrialUsage)
                .where(TrialUsage.user_id == r.user_id, TrialUsage.feature_id == r.feature_id,
                       TrialUsage.reserved > 0)
                .values(reserved=TrialUsage.reserved - 1, used=TrialUsage.used + used_delta))
    return (update(MonthlyUsage)
            .where(MonthlyUsage.user_id == r.user_id, MonthlyUsage.feature_id == r.feature_id,
                   MonthlyUsage.period == r.period, MonthlyUsage.reserved > 0)
            .values(reserved=MonthlyUsage.reserved - 1, used=MonthlyUsage.used + used_delta))


def commit(db: Session, r: Reservation, result: dict[str, Any] | None = None) -> None:
    if r.source not in ("trial", "plan"):
        return
    # Only finalise a reservation that is still open: makes commit itself idempotent.
    upd = db.execute(update(UsageReservation)
                     .where(UsageReservation.id == r.id, UsageReservation.status == "reserved")
                     .values(status="committed", result=_trim(result), finalized_at=utcnow()))
    if upd.rowcount == 1:
        db.execute(_counter_update(r, used_delta=1))
        _log(db, r.user_id, r.feature_id, r.source, "consumed", r.id)
    db.commit()


def release(db: Session, r: Reservation, reason: str = "failed") -> None:
    if r.source not in ("trial", "plan"):
        return
    gone = db.execute(delete(UsageReservation)
                      .where(UsageReservation.id == r.id, UsageReservation.status == "reserved"))
    if gone.rowcount == 1:
        db.execute(_counter_update(r, used_delta=0))
        _log(db, r.user_id, r.feature_id, r.source, "released", r.id, {"reason": reason[:200]})
    db.commit()


def release_stale(db: Session, older_than_minutes: int = 15) -> int:
    """Free reservations orphaned by a crash between reserve() and commit()/release()."""
    cutoff = utcnow() - timedelta(minutes=older_than_minutes)
    stale = db.scalars(select(UsageReservation).where(
        UsageReservation.status == "reserved", UsageReservation.created_at < cutoff)).all()
    for s in stale:
        release(db, Reservation(s.id, s.user_id, s.feature_id, s.source, s.period), "stale")
    return len(stale)


def _trim(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if result is None:
        return None
    import json

    raw = json.dumps(result, default=str)
    return result if len(raw) <= 200_000 else {"truncated": True}


def _log(db: Session, user_id, feature_id, source, outcome, reservation_id, detail=None) -> None:
    db.add(UsageEvent(user_id=user_id, feature_id=feature_id, source=source, outcome=outcome,
                      reservation_id=reservation_id, detail=detail or {}))


class MeterHandle:
    def __init__(self, reservation: Reservation) -> None:
        self.reservation = reservation
        self.result: dict[str, Any] | None = None

    @property
    def replay(self) -> dict[str, Any] | None:
        return self.reservation.replay_result if self.reservation.is_replay else None

    def set_result(self, result: dict[str, Any]) -> None:
        self.result = result


@asynccontextmanager
async def metered(user_id: uuid.UUID, feature_id: str, idempotency_key: str | None = None) -> AsyncIterator[MeterHandle]:
    """Charge one use of ``feature_id`` if (and only if) the block completes successfully.

    Inside an outer metered block the inner feature is included in the outer charge.
    Uses its own DB session so the caller's transaction never interferes with metering.
    """
    if _active_scope.get() is not None:
        yield MeterHandle(Reservation(None, user_id, feature_id, "included"))
        return
    db = SessionLocal()
    try:
        r = reserve(db, user_id, feature_id, idempotency_key)
        handle = MeterHandle(r)
        if r.is_replay:
            yield handle
            return
        token = _active_scope.set(feature_id)
        try:
            yield handle
        except BaseException as exc:
            release(db, r, f"{type(exc).__name__}: {exc}")
            raise
        finally:
            _active_scope.reset(token)
        commit(db, r, handle.result)
    finally:
        db.close()


def usage_summary(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    plan, sub = active_plan(db, user_id)
    period = current_period()
    trials = {t.feature_id: t for t in db.scalars(select(TrialUsage).where(TrialUsage.user_id == user_id))}
    monthly = {m.feature_id: m for m in db.scalars(select(MonthlyUsage).where(
        MonthlyUsage.user_id == user_id, MonthlyUsage.period == period))}
    features = []
    for f in FEATURES.values():
        t = trials.get(f.id)
        used = t.used if t else 0
        m = monthly.get(f.id)
        plan_limit = plan.monthly_limits.get(f.id, 0)
        features.append({
            "id": f.id, "name": f.name, "description": f.description, "unit": f.unit,
            "trial_limit": f.trial_limit, "trial_used": used,
            "trial_remaining": max(0, f.trial_limit - used - (t.reserved if t else 0)),
            "plan_limit": plan_limit, "plan_used": m.used if m else 0,
            "plan_remaining": max(0, plan_limit - (m.used + m.reserved if m else 0)),
        })
    for item in features:
        item["available"] = item["trial_remaining"] + item["plan_remaining"]
        item["final_free_use"] = item["trial_remaining"] == 1 and item["plan_remaining"] == 0
    return {
        "plan": {"id": plan.id, "name": plan.name},
        "subscription": None if sub is None else {
            "status": sub.status, "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end},
        "period": period,
        "features": features,
    }
