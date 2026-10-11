"""Reproducible seed of synthetic data.

Times in the dataset are minutes relative to the seed time, so freshness
rules behave the same whenever the demo is (re)seeded.

Usage:  python -m app.seed [--reset]
Seeding and reset are refused unless APP_MODE=demo.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, get_engine, session_scope, utcnow
from .models.orm import (
    Account, Case, Customer, DiagnosticSample, Equipment, Incident, NetworkAsset, Service,
    ServiceAssetMapping, SupportInteraction, Tenant, User,
)
from .observability import audit
from .retrieval.knowledge import load_knowledge


def _num(customer_id: str) -> str:
    return customer_id.split("-", 1)[1]


def load_dataset() -> dict:
    return json.loads((get_settings().data_dir / "synthetic" / "dataset.json").read_text())


def _at(now: datetime, minutes: int | None) -> datetime | None:
    return None if minutes is None else now + timedelta(minutes=minutes)


def expand_series(series: dict, profiles: dict, now: datetime) -> list[dict]:
    out = []
    t = series["from"]
    idx = 0
    while t <= series["to"]:
        seg = next(s for s in series["segments"] if t < s["until"] or s is series["segments"][-1])
        values = dict(profiles[seg["profile"]])
        uptime = 2_592_000  # 30 days, in seconds
        reboot_every = seg.get("reboot_every")
        if reboot_every and idx % reboot_every == 0:
            values["cpe_unexpected_reboots"] = 1
            values["link_retrains"] = max(values["link_retrains"], 1)
            uptime = 600 + 37 * (idx % 7)
        out.append({
            "service": series["service"],
            "collected_at": now + timedelta(minutes=t),
            "interval_minutes": series["every"],
            "cpe_uptime_s": uptime,
            **values,
        })
        t += series["every"]
        idx += 1
    return out


def seed(db: Session, now: datetime | None = None) -> dict:
    now = now or utcnow()
    ds = load_dataset()
    for t in ds["tenants"]:
        db.add(Tenant(**t))
    for u in ds["users"]:
        db.add(User(**u))
    db.flush()
    for a in ds["network_assets"]:  # parents are listed before children
        db.add(NetworkAsset(updated_at=now - timedelta(days=30), **a))
        db.flush()
    customer_tenant = {}
    groups: dict[str, list] = {k: [] for k in ("customers", "accounts", "services", "mappings", "equipment")}
    for c in ds["customers"]:
        n = _num(c["id"])
        customer_tenant[c["id"]] = c["tenant_id"]
        groups["customers"].append(Customer(
            id=c["id"], tenant_id=c["tenant_id"], display_name=c["name"],
            contact_phone=f"555-01{n[-2:]}", contact_email=f"customer{n}@example.invalid"))
        groups["accounts"].append(Account(
            id=f"ACCT-{n}", tenant_id=c["tenant_id"], customer_id=c["id"], segment=c["segment"],
            service_address=c["address"], postal_area=c["postal_area"], updated_at=now - timedelta(days=10)))
        groups["services"].append(Service(
            id=f"SVC-{n}", tenant_id=c["tenant_id"], account_id=f"ACCT-{n}", product="home_internet",
            plan="Fibre-to-node 100", access_technology="vdsl2", updated_at=now - timedelta(days=10)))
        groups["mappings"].append(ServiceAssetMapping(
            id=f"MAP-{n}", tenant_id=c["tenant_id"], service_id=f"SVC-{n}", asset_id=c["asset"],
            port=c["port"], valid_from=now - timedelta(days=400), updated_at=now - timedelta(days=30)))
        groups["equipment"].append(Equipment(
            id=f"EQ-{n}", tenant_id=c["tenant_id"], service_id=f"SVC-{n}", model=c["equipment_model"],
            firmware=c["firmware"], installed_at=now - timedelta(days=380), updated_at=now - timedelta(days=5)))
    for rows in groups.values():  # insert parents before children (FKs enforced)
        db.add_all(rows)
        db.flush()
    for inc in ds["incidents"]:
        db.add(Incident(
            id=inc["id"], tenant_id=inc["tenant_id"], asset_id=inc["asset_id"], title=inc["title"],
            status=inc["status"], started_at=_at(now, inc["started_at"]),
            ended_at=_at(now, inc["ended_at"]),
            estimated_restoration_at=_at(now, inc["estimated_restoration_at"]),
            status_history=[{"at": _at(now, h["t"]).isoformat(), "status": h["status"], "note": h["note"]}
                            for h in inc["status_history"]],
            updated_at=_at(now, inc["status_history"][-1]["t"]),
        ))
    sample_count = 0
    for series in ds["diagnostic_series"]:
        tenant = customer_tenant[f"CUST-{series['service'].split('-')[1]}"]
        for i, s in enumerate(expand_series(series, ds["diagnostic_profiles"], now)):
            sample_count += 1
            db.add(DiagnosticSample(
                id=f"DS-{series['service'].split('-')[1]}-{int(series['from'])}-{i:03d}".replace("--", "-m"),
                tenant_id=tenant, service_id=s["service"], collected_at=s["collected_at"],
                source="line_telemetry", link_state=s["link_state"],
                loss_of_signal_events=s["loss_of_signal_events"], link_retrains=s["link_retrains"],
                packet_loss_pct=s["packet_loss_pct"], latency_ms=s["latency_ms"],
                snr_margin_db=s["snr_margin_db"], crc_errors=s["crc_errors"],
                cpe_uptime_s=s["cpe_uptime_s"], cpe_unexpected_reboots=s["cpe_unexpected_reboots"],
                interval_minutes=s["interval_minutes"],
            ))
    for it in ds["support_interactions"]:
        n = _num(it["customer"])
        db.add(SupportInteraction(
            id=it["id"], tenant_id=customer_tenant[it["customer"]], account_id=f"ACCT-{n}",
            channel=it["channel"], occurred_at=_at(now, it["t"]), summary=it["summary"],
            notes=it["notes"], actions_taken=it["actions_taken"], outcome=it["outcome"],
            author_type=it["author_type"],
        ))
    db.flush()
    for c in ds["cases"]:
        n = _num(c["customer"])
        tenant = customer_tenant[c["customer"]]
        created = _at(now, c["t"])
        case = Case(id=c["id"], tenant_id=tenant, account_id=f"ACCT-{n}", service_id=f"SVC-{n}",
                    title=c["title"], complaint_text=c["complaint"], reported_symptoms={},
                    status="NEW", version=1, created_by="seed", created_at=created,
                    updated_at=created, simulation_profile=c.get("simulation_profile", {}))
        db.add(case)
        db.flush()
        audit.record(db, tenant_id=tenant, actor_id="seed", actor_role="system",
                     event_type="CASE_CREATED", case_id=case.id, to_status="NEW",
                     detail={"source": "synthetic seed", "dataset_version": ds["dataset_version"]})
    docs = load_knowledge(db, get_settings().data_dir / "knowledge")
    return {"dataset_version": ds["dataset_version"], "cases": len(ds["cases"]),
            "diagnostic_samples": sample_count, "knowledge_documents": docs}


def create_schema() -> None:
    Base.metadata.create_all(get_engine())


def reset_demo() -> dict:
    """Drop and recreate all tables, then seed. Demo mode only."""
    if not get_settings().is_demo:
        raise PermissionError("Reset is disabled outside demo mode")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from .workflows.checkpoints import reset_checkpoints

    reset_checkpoints()
    with session_scope() as db:
        return seed(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed TelecomResolve synthetic data")
    parser.add_argument("--reset", action="store_true", help="drop all data first (demo only)")
    args = parser.parse_args()
    if not get_settings().is_demo:
        print("Refusing to seed: APP_MODE is not 'demo'.", file=sys.stderr)
        sys.exit(2)
    if args.reset:
        print(json.dumps(reset_demo(), indent=2))
        return
    create_schema()
    with session_scope() as db:
        if db.get(Tenant, "tenant-north") is not None:
            print("Already seeded; use --reset to restore the known demo state.")
            return
        print(json.dumps(seed(db), indent=2))


if __name__ == "__main__":
    main()
