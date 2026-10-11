"""Deterministic dataset permission service. Eligibility is recomputed from consent records at
evaluation time; a record's own 'declared_eligible' flag is never trusted on its own."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import DatasetConsentRecord, DatasetRecord


def eligibility(rec: DatasetRecord, consent: DatasetConsentRecord | None, purpose: str, split: str, today: date) -> list[str]:
    reasons = []
    if rec.split != split:
        reasons.append(f"split_{rec.split}_not_{split}")
    if consent is None:
        reasons.append("missing_consent_record")
    else:
        if consent.consent_status != "granted":
            reasons.append("consent_" + consent.consent_status)
        if purpose not in consent.permitted_use:
            reasons.append(f"{purpose}_not_permitted")
        if date.fromisoformat(consent.retention_until) < today:
            reasons.append("retention_expired")
    if rec.image_quality != "pass":
        reasons.append("image_quality_below_protocol")
    if not rec.grouping_protocol.startswith("GP-DEMO-1"):
        reasons.append("unapproved_grouping_protocol")
    return reasons


def eligible_samples(db: Session, snapshot_id: str, split: str = "test", purpose: str = "evaluation",
                     today: date | None = None) -> dict:
    today = today or date.today()
    recs = db.execute(select(DatasetRecord).where(DatasetRecord.dataset_version_id == snapshot_id)
                      .order_by(DatasetRecord.sample_id)).scalars().all()
    consents = {c.sample_id: c for c in db.execute(select(DatasetConsentRecord)).scalars()}
    eligible, excluded, overridden = [], {}, []
    for r in recs:
        reasons = eligibility(r, consents.get(r.sample_id), purpose, split, today)
        if r.split != split:
            continue  # other splits are not part of this evaluation at all
        if reasons:
            for x in reasons:
                excluded[x] = excluded.get(x, 0) + 1
            if r.declared_eligible:
                overridden.append(r.sample_id)
        else:
            eligible.append(r)
    return {"eligible": eligible, "excluded_by_reason": excluded, "declared_eligible_overridden": overridden,
            "split_total": sum(1 for r in recs if r.split == split)}
