"""Load the synthetic demonstration fixtures through the real ingestion pipeline (idempotent)."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.ingestion.importer import run_import
from app.models.orm import Dataset, Message, Translation
from app.multilingual.translation import check_translation

log = logging.getLogger(__name__)
DEMO_NAME = "Demonstration fixtures (synthetic)"
ML_NAME = "Multilingual scenarios (synthetic)"


def ensure_demo_datasets() -> dict:
    s = get_settings()
    out = {}
    demo_csv = s.demo_data_dir / "demo_twcs.csv"
    ml_csv = s.demo_data_dir / "multilingual_scenarios.csv"
    if demo_csv.exists():
        out["demo"] = run_import(demo_csv, kind="demo", name=DEMO_NAME, source_label="synthetic fixture: data/demo/demo_twcs.csv", synthetic=True)
    if ml_csv.exists():
        ml_id = run_import(ml_csv, kind="synthetic_multilingual", name=ML_NAME,
                           source_label="synthetic fixture: data/demo/multilingual_scenarios.csv", synthetic=True)
        out["multilingual"] = ml_id
        ref_path = s.demo_data_dir / "multilingual_reference.json"
        if ref_path.exists():
            ref = json.loads(ref_path.read_text(encoding="utf-8"))
            with session_scope() as db:
                ds = db.get(Dataset, ml_id)
                if not (ds.manifest or {}).get("reference_translations_loaded"):
                    msgs = {m.source_id: m for m in db.scalars(select(Message).where(Message.dataset_id == ml_id))}
                    n = 0
                    for sid, info in ref["messages"].items():
                        m = msgs.get(sid)
                        if m and info.get("language") != "en":
                            chk = check_translation(m.text, info["reference_translation_en"])
                            db.add(Translation(message_id=m.id, target_language="en", text=info["reference_translation_en"],
                                               method="reference", model_id=None, prompt_version="fixture-reference-v1",
                                               checks=chk["checks"], needs_review=chk["needs_review"]))
                            n += 1
                    ds.manifest = {**ds.manifest, "reference_translations_loaded": n,
                                   "reference_note": ref["note"]}
    return out
