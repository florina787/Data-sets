"""Engine / session management and synthetic seed loading."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.models import db as m
from app.schemas.domain import IMAGING, LAB, SERVICE_LABELS


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - driver hook
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return engine


@lru_cache
def _factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    s = _factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "patient": {"patient:search", "patient:chat", "patient:book", "patient:self", "approval:self"},
    "engineer": {"patient:search", "patient:chat", "sdlc:read", "sdlc:write", "agents:read", "telemetry:read",
                 "governance:read", "approval:engineering"},
    "release_approver": {"sdlc:read", "agents:read", "telemetry:read", "governance:read", "approval:release",
                         "approval:engineering"},
    "admin": {"patient:search", "patient:chat", "sdlc:read", "sdlc:write", "agents:read", "telemetry:read",
              "governance:read", "governance:write", "admin:all", "approval:engineering", "approval:release"},
}

DEMO_USERS = [
    ("usr-patient-demo", "patient@medaccess-demo.invalid", "Demo Patient", "patient"),
    ("usr-engineer-demo", "engineer@medaccess-demo.invalid", "Demo Engineer", "engineer"),
    ("usr-approver-demo", "approver@medaccess-demo.invalid", "Demo Release Approver", "release_approver"),
    ("usr-admin-demo", "admin@medaccess-demo.invalid", "Demo Administrator", "admin"),
]


def init_db(seed: bool = True) -> None:
    from app.services.synthetic import current_dataset

    engine = get_engine()
    m.Base.metadata.create_all(engine)
    if not seed:
        return
    with session_scope() as s:
        if s.scalar(select(m.Role).limit(1)) is None:
            for role, perms in ROLE_PERMISSIONS.items():
                s.add(m.Role(id=role, description=f"{role} role"))
                s.flush()
                for p in sorted(perms):
                    s.add(m.Permission(role_id=role, permission=p))
            for uid, email, name, role in DEMO_USERS:
                s.add(m.User(id=uid, email=email, display_name=name, role_id=role))
                s.add(m.UserPreference(user_id=uid))
        if s.scalar(select(m.HealthcareService).limit(1)) is None:
            for svc, label in SERVICE_LABELS.items():
                cat = "imaging" if svc in IMAGING else "laboratory" if svc in LAB else "consultation"
                s.add(m.HealthcareService(code=svc.value, label=label, category=cat))
        ds = current_dataset()
        if s.scalar(select(m.ProviderIntegration).limit(1)) is None:
            for i in ds.integrations:
                s.add(m.ProviderIntegration(id=i.id, name=i.name, adapter_type=i.adapter_type,
                                            reliability=i.reliability, data_mode=i.data_mode.value,
                                            authorized=i.authorized, notes=i.notes))
            s.flush()
        if s.scalar(select(m.Facility).limit(1)) is None:
            for f in ds.facilities:
                s.add(m.Facility(id=f.id, name=f.name, facility_type=f.facility_type.value, network=f.network,
                                 phone=f.phone, booking_url=f.booking_url, booking_capability=f.booking_capability,
                                 funding=f.funding, wheelchair_accessible=f.wheelchair_accessible,
                                 transit_score=f.transit_score, parking=f.parking, hours=f.hours,
                                 accepted_requisition_formats=f.accepted_requisition_formats,
                                 integration_id=f.integration_id, data_mode=f.data_mode.value,
                                 is_synthetic=f.is_synthetic))
            s.flush()
            for f in ds.facilities:
                s.add(m.FacilityLocation(facility_id=f.id, address=f.address, city=f.city,
                                         neighbourhood=f.neighbourhood, postal_code=f.postal_code,
                                         latitude=f.latitude, longitude=f.longitude, timezone=f.timezone))
                for svc in f.services:
                    s.add(m.FacilityService(facility_id=f.id, service_code=svc.value,
                                            referral_required=svc in f.referral_required_for))
                    req = "referral" if svc in f.referral_required_for else (
                        "requisition" if svc in IMAGING or svc in LAB else "none")
                    s.add(m.RequisitionRequirement(facility_id=f.id, service_code=svc.value, requirement=req,
                                                   accepted_formats=f.accepted_requisition_formats))
        refresh_slots(s, ds)


def refresh_slots(s: Session, ds=None) -> int:
    """Replace stored synthetic slots with the current synthetic snapshot."""
    from app.services.synthetic import current_dataset

    ds = ds or current_dataset()
    s.query(m.AppointmentSlot).filter(m.AppointmentSlot.is_synthetic.is_(True)).delete()
    for sl in ds.slots:
        s.add(m.AppointmentSlot(id=sl.slot_id, facility_id=sl.facility_id, service_code=sl.service.value,
                                start_utc=sl.start_utc, duration_minutes=sl.duration_minutes,
                                source_status=sl.source_status.value, source_id=sl.source_id,
                                last_verified_at=sl.last_verified_at, is_synthetic=True))
    return len(ds.slots)


def reset_engine_cache() -> None:
    get_engine.cache_clear()
    _factory.cache_clear()
