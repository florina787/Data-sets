"""Seed the demo database from fixture files.  python -m app.seed [--reset]
Reset is permitted only in demo mode."""
from __future__ import annotations

import json
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import Base, get_engine, session_scope
from app.models import orm  # noqa: F401  (register tables)
from app.models.orm import (CodeRevision, DatasetConsentRecord, DatasetRecord, DatasetVersion, ModelVersion, Tenant, User)
from app.services import fixtures

SEED_CHANGE_ID = "BR-101"
SEED_STATEMENT = ("Improve foundation-shade recommendations for deeper skin tones under warm indoor lighting "
                  "while preserving performance for other tested groups.")


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def seed(create_br101: bool = True) -> bool:
    fixtures.clear_caches()
    with session_scope() as db:
        if db.execute(select(Tenant)).first():
            return False
        u = json.loads((fixtures.synthetic_dir() / "users.json").read_text())
        for t in u["tenants"]:
            db.add(Tenant(**t))
        db.flush()
        for x in u["users"]:
            db.add(User(**x))
        mf = fixtures.models_file()
        cat = fixtures.load_json(fixtures.synthetic_dir() / "catalogue.json")["catalogue_version"]
        for m in mf["models"]:
            db.add(ModelVersion(id=m["model_id"], version=m["version"], role=m["role"],
                                artifact_digest=fixtures.compute_artifact_digest(m["model_id"]),
                                artifact_uri=f"fixture://predictions/{m['model_id']}.json", preprocessing=m["preprocessing"],
                                catalogue_version=cat, code_revision_id=m["code_revision"],
                                lighting_profile_map_id=m["lighting_profile_map"], provenance=m["provenance"], is_fixture=True))
        revs = json.loads((fixtures.synthetic_dir() / "revisions" / "revisions.json").read_text())["revisions"]
        for r in revs:
            diff = (fixtures.synthetic_dir() / "revisions" / r["diff_file"]).read_text()
            db.add(CodeRevision(id=r["revision_id"], author_user_id=r["author_user_id"], summary=r["summary"], diff=diff,
                                diff_digest=fixtures.sha256_bytes(diff.encode()), requirement_refs=r["requirement_refs"],
                                test_refs=r["test_refs"]))
        db.add(CodeRevision(id="REV-2.3.0", author_user_id="u-cv-eng", summary="Released baseline", diff="",
                            diff_digest=fixtures.sha256_bytes(b""), requirement_refs=[], test_refs=[]))
        ds = fixtures.dataset_file()
        db.add(DatasetVersion(id=ds["dataset_snapshot_id"], digest=fixtures.dataset_digest(), record_count=len(ds["records"]),
                              devices_covered=ds["devices_covered"], note=ds["note"], synthetic=True))
        db.flush()
        for r in ds["records"]:
            db.add(DatasetRecord(sample_id=r["sample_id"], dataset_version_id=ds["dataset_snapshot_id"], split=r["split"],
                                 tone_stratum=r["tone_stratum"], lighting_category=r["lighting_category"],
                                 device_category=r["device_category"], expected_shade_id=r["expected_shade_id"],
                                 label_provenance=r["label_provenance"], consent_record_id=r["consent_record_id"],
                                 image_quality=r["image_quality"], grouping_protocol=r["grouping_protocol"],
                                 image_ref=r["image_ref"], declared_eligible=r["declared_eligible"]))
            db.add(DatasetConsentRecord(id=r["consent_record_id"], sample_id=r["sample_id"], consent_status=r["consent_status"],
                                        permitted_use=r["permitted_use"], retention_until=r["retention_until"]))
    if create_br101:
        from app.services.lifecycle import create_change
        with session_scope() as db:
            po = db.get(User, "u-po")
            create_change(db, po, "BR-101 Foundation shade — deeper tones under warm indoor light", SEED_STATEMENT,
                          change_id=SEED_CHANGE_ID)
    return True


def reset() -> None:
    if not get_settings().demo:
        raise SystemExit("Reset is only permitted in demo mode (APP_ENV=demo).")
    Base.metadata.drop_all(get_engine())
    init_db()
    seed()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset()
        print("demo database reset and reseeded")
    else:
        init_db()
        print("seeded" if seed() else "already seeded")
