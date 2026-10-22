"""End-to-end preparation: raw file -> normalized, labelled DuckDB tables + manifests.

Run with `python -m scripts.prepare_dataset` (see README). The pipeline is
idempotent: it rebuilds analytics.duckdb from the raw file every time and never
modifies the raw file.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from app.config import Settings, get_settings
from app.data.ingestion import load_dataset
from app.data.normalization import normalize_messages
from app.data.validation import profile, quality_report
from app.labeling import rules
from app.labeling.store import LabelStore, text_key
from app.labeling.taxonomy import TAXONOMY_VERSION, TOPICS

log = logging.getLogger(__name__)
PIPELINE_VERSION = "pipeline-1.0"


def _label_messages(messages: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, dict]:
    gemini: dict = {}
    if settings.label_source == "gemini":
        gemini = LabelStore(settings.labels_database_path).valid_labels()
    rows = []
    used_gemini = 0
    for r in messages.itertuples(index=False):
        is_opening = r.speaker_role == "customer" and int(r.turn_index) == 0
        base = rules.label_message(r.clean_text, r.speaker_role, int(r.turn_index))
        label = base.to_dict()
        label.update(labeler=rules.LABELER_VERSION, model_name=None, prompt_version=None)
        g = gemini.get(text_key(r.masked_text, r.speaker_role, is_opening))
        if g:
            used_gemini += 1
            # Topic/product of the opening come from the parsed template when it matched;
            # Gemini supplies them only where the template did not.
            for k in ("act", "sentiment", "sentiment_score", "empathy", "courtesy", "resolution", "language"):
                label[k] = g[k]
            if is_opening and base.method != "template":
                label["topic"], label["product"] = g.get("topic") or "other", g.get("product")
            label.update(method="gemini", confidence=g.get("confidence", 0.8), labeler="gemini",
                         model_name=g["model"], prompt_version=g["prompt_version"])
        rows.append(label)
    labels = pd.DataFrame(rows)
    labels.insert(0, "message_id", messages["message_id"].values)
    labels.insert(1, "conversation_id", messages["conversation_id"].values)
    labels["taxonomy_version"] = TAXONOMY_VERSION
    labels["labeled_at"] = datetime.now(UTC).isoformat()
    labels["validation_status"] = labels["method"].map({"template": "validated_template", "gemini": "schema_valid", "lexicon": "provisional"})
    coverage = {
        "label_source": settings.label_source,
        "messages": len(labels),
        "by_method": labels["method"].value_counts().to_dict(),
        "gemini_labels_used": used_gemini,
    }
    return labels, coverage


def _conversations(messages: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    merged = messages.merge(labels.drop(columns=["conversation_id"]), on="message_id").sort_values(["conversation_id", "turn_index"])
    out = []
    for cid, g in merged.groupby("conversation_id", sort=True):
        turns = g.to_dict("records")
        agg = rules.aggregate_conversation(turns)
        ts = g["timestamp"].dropna()
        start = ts.min() if len(ts) else pd.NaT
        out.append({
            "conversation_id": cid,
            "dataset_source": g["dataset_source"].iloc[0],
            "source_record_id": g["source_reference"].iloc[0],
            "start_timestamp": start,
            "end_timestamp": ts.max() if len(ts) else pd.NaT,
            "conversation_date": start.date() if pd.notna(start) else None,
            "month": start.strftime("%Y-%m") if pd.notna(start) else None,
            "agent_id": g["agent_id"].mode().iloc[0] if g["agent_id"].notna().any() else None,
            "customer_id": g["customer_id"].iloc[0],
            "message_count": len(g),
            "customer_turns": int((g["speaker_role"] == "customer").sum()),
            "agent_turns": int((g["speaker_role"] == "agent").sum()),
            "duration_hours": round((ts.max() - ts.min()).total_seconds() / 3600, 2) if len(ts) > 1 else None,
            "timestamps_monotonic": bool(g["timestamp"].is_monotonic_increasing),
            **agg,
            "topic_label": TOPICS.get(agg["topic"], TOPICS["other"]).label,
            "label_version": f"{TAXONOMY_VERSION}/{rules.LABELER_VERSION}",
            "processing_status": "labelled" if agg["min_label_confidence"] and agg["min_label_confidence"] >= 0.8 else "provisional",
        })
    return pd.DataFrame(out)


def run(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    started = datetime.now(UTC)
    frames = []
    sources = []
    loaded = load_dataset(settings.raw_dataset_path)
    frames.append(normalize_messages(loaded.frame, "original", loaded.member or loaded.source_file))
    sources.append({
        "dataset_source": "original", "file": loaded.source_file, "member": loaded.member, "sha256": loaded.sha256,
        "encoding": loaded.encoding, "delimiter": loaded.delimiter, "column_mapping": loaded.column_mapping,
        "archive_members": loaded.archive_members, "rows": len(loaded.frame),
        "citation": "Customer Support Conversation Dataset (Syncora.ai), Kaggle. Supplied sample of 3,000 synthetic conversations.",
    })
    if settings.synthetic_dataset_path.exists():
        syn = load_dataset(settings.synthetic_dataset_path)
        frames.append(normalize_messages(syn.frame, "synthetic_demo", syn.source_file))
        sources.append({"dataset_source": "synthetic_demo", "file": syn.source_file, "sha256": syn.sha256, "rows": len(syn.frame),
                        "citation": "Generated by scripts/generate_synthetic.py for demonstrating combined mode. Not real data."})
    messages = pd.concat(frames, ignore_index=True)
    original = messages[messages["dataset_source"] == "original"]
    report = quality_report(original)
    prof = profile(original)

    labels, coverage = _label_messages(messages, settings)
    conversations = _conversations(messages, labels)

    db_path: Path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".building.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        con.register("m", messages)
        con.register("l", labels)
        con.register("c", conversations)
        con.execute("CREATE TABLE messages AS SELECT * FROM m ORDER BY conversation_id, turn_index")
        con.execute("CREATE TABLE message_labels AS SELECT * FROM l")
        con.execute("CREATE TABLE conversations AS SELECT * FROM c ORDER BY conversation_id")
        con.execute("CREATE TABLE topics AS SELECT * FROM (VALUES " + ",".join(
            f"('{t.id}', '{t.label}', '{t.description.replace(chr(39), chr(39) * 2)}')" for t in TOPICS.values()) + ") t(topic, topic_label, description)")
        meta = {
            "pipeline_version": PIPELINE_VERSION,
            "taxonomy_version": TAXONOMY_VERSION,
            "labeler_version": rules.LABELER_VERSION,
            "built_at": datetime.now(UTC).isoformat(),
            "sources": sources,
            "label_coverage": coverage,
        }
        con.execute("CREATE TABLE build_metadata AS SELECT ? AS meta_json", [json.dumps(meta, default=str)])
        con.execute("CREATE INDEX idx_msg_conv ON messages(conversation_id)")
    finally:
        con.close()
    tmp.replace(db_path)

    settings.manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest = {**meta, "duration_seconds": round((datetime.now(UTC) - started).total_seconds(), 2),
                "tables": {"messages": len(messages), "message_labels": len(labels), "conversations": len(conversations)}}
    (settings.manifests_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (settings.manifests_dir / "data_quality_report.json").write_text(json.dumps(report, indent=2, default=str))
    (settings.manifests_dir / "data_profile.json").write_text(json.dumps(prof, indent=2, default=str))
    return {"manifest": manifest, "quality": report, "profile": prof}
