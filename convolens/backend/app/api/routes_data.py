"""Datasets, imports, analytics, conversations, maps, opportunities, impact, language and data-quality endpoints."""
from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import impact as impact_mod
from app.analytics import languages as lang_mod
from app.analytics import metrics, quality
from app.analytics.labels import CORRECTABLE, reapply
from app.analytics.opportunities import DEFAULT_WEIGHTS, candidates
from app.analytics.rules import Msg, _sentiment
from app.analytics.taxonomy import ESCALATION, JOURNEY_LABELS, RESOLUTION, SENTIMENT, TOPIC_KEYS, TOPICS, topic_label
from app.api.common import dataset_info, parse_filters, ready_dataset
from app.config import get_settings
from app.db import get_db
from app.ingestion import twcs
from app.ingestion.jobs import KAGGLE_DATASET, get_jobs
from app.models.orm import Action, Conversation, Correction, Dataset, ImportJob, Message, OpportunityReview, Translation
from app.models.schemas import Filters
from app.retrieval.index import invalidate, search, semantic_status
from app.security.csv_safe import to_csv
from app.tools.catalog import get_conversation_detail

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------------------------------------ datasets
@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    rows = db.scalars(select(Dataset).order_by(Dataset.synthetic.desc(), Dataset.created_at)).all()
    out = []
    for ds in rows:
        info = dataset_info(ds)
        info.pop("time_range", None)
        if ds.status == "ready":
            rng = db.execute(select(func.min(Conversation.started_at), func.max(Conversation.ended_at)).where(Conversation.dataset_id == ds.id)).one()
            info["data_from"] = rng[0].isoformat() if rng[0] else None
            info["data_to"] = rng[1].isoformat() if rng[1] else None
        out.append(info)
    return {"datasets": out}


@router.get("/datasets/{dataset_id}/quality")
def data_quality(ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    return quality.report(db, ds.id)


@router.get("/taxonomy")
def taxonomy():
    return {"topics": [{"key": k, "label": topic_label(k), "definition": TOPICS.get(k, {}).get("definition"),
                        "department": TOPICS.get(k, {}).get("department")} for k in TOPIC_KEYS],
            "resolution": RESOLUTION, "sentiment": SENTIMENT, "escalation": ESCALATION, "journey": JOURNEY_LABELS}


# ------------------------------------------------------------------------------------------------ imports
def _job_dict(j: ImportJob) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status, "stage": j.stage, "progress": j.progress, "error": j.error,
            "dataset_id": j.dataset_id, "params": {k: v for k, v in (j.params or {}).items() if k != "path"},
            "created_at": j.created_at.isoformat(), "updated_at": j.updated_at.isoformat() if j.updated_at else None}


@router.get("/imports/jobs")
def jobs(db: Session = Depends(get_db)):
    return {"jobs": [_job_dict(j) for j in db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(30))]}


@router.get("/imports/jobs/{job_id}")
def job(job_id: str, db: Session = Depends(get_db)):
    j = db.get(ImportJob, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return _job_dict(j)


@router.post("/imports/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        get_jobs().cancel(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found")
    return {"cancel_requested": True}


@router.post("/imports/jobs/{job_id}/resume")
def resume_job(job_id: str):
    try:
        get_jobs().resume(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"resumed": True}


class ImportOptions(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=2**31)
    sample_size: int | None = Field(default=None, ge=1, le=3000)
    name: str = Field(default="Customer Support on Twitter (Kaggle)", max_length=200)


@router.post("/imports/upload")
async def upload(file: UploadFile = File(...), seed: int | None = Form(None), sample_size: int | None = Form(None),
                 name: str = Form("Customer Support on Twitter (Kaggle)")):
    s = get_settings()
    opts = ImportOptions(seed=seed, sample_size=sample_size, name=name)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Only .csv files are accepted (the Kaggle file is twcs.csv).")
    dest_dir = s.import_root / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"upload_{secrets.token_hex(8)}.csv"
    limit = s.max_upload_mb * 1024 * 1024
    written = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1 << 20):
            written += len(chunk)
            if written > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds the {s.max_upload_mb} MB upload limit. Use a local-path import instead.")
            out.write(chunk)
    try:
        schema = twcs.inspect_schema(dest)
    except twcs.SchemaError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Schema validation failed: {exc}")
    jid = get_jobs().submit("upload", {"path": str(dest), "source_label": f"upload:{Path(file.filename).name}", "name": opts.name,
                                       "seed": opts.seed, "sample_size": opts.sample_size, "dataset_kind": "kaggle_twcs"})
    return {"job_id": jid, "schema": schema}


class LocalImport(ImportOptions):
    path: str = Field(max_length=1000)


@router.post("/imports/local")
def import_local(body: LocalImport):
    s = get_settings()
    root = s.import_root.resolve()
    p = Path(body.path)
    p = (p if p.is_absolute() else root / p).resolve()
    if root not in p.parents and p != root:
        raise HTTPException(403, f"Local imports must be inside the import directory ({root}).")
    if not p.is_file():
        raise HTTPException(404, f"File not found: {p.name}")
    try:
        schema = twcs.inspect_schema(p)
    except twcs.SchemaError as exc:
        raise HTTPException(422, f"Schema validation failed: {exc}")
    jid = get_jobs().submit("local_path", {"path": str(p), "source_label": f"local:{p.name}", "name": body.name,
                                           "seed": body.seed, "sample_size": body.sample_size, "dataset_kind": "kaggle_twcs"})
    return {"job_id": jid, "schema": schema}


@router.post("/imports/kaggle")
def import_kaggle(body: ImportOptions):
    jid = get_jobs().submit("kaggle", {"dataset": KAGGLE_DATASET, "source_label": f"kaggle:{KAGGLE_DATASET}", "name": body.name,
                                       "seed": body.seed, "sample_size": body.sample_size, "dataset_kind": "kaggle_twcs"})
    return {"job_id": jid}


class AnalysisJob(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=3000)
    activate: bool = True


@router.post("/datasets/{dataset_id}/analysis-jobs")
def start_analysis(body: AnalysisJob, ds: Dataset = Depends(ready_dataset)):
    if ds.synthetic:
        raise HTTPException(409, "Connected analysis runs only on imported datasets. Demonstration data uses rules.")
    return {"job_id": get_jobs().submit("analysis", {"dataset_id": ds.id, "limit": body.limit, "activate": body.activate})}


@router.post("/datasets/{dataset_id}/translation-jobs")
def start_translation(ds: Dataset = Depends(ready_dataset)):
    if ds.synthetic:
        raise HTTPException(409, "Model translation runs only on imported datasets; synthetic scenarios carry reference translations.")
    return {"job_id": get_jobs().submit("translation", {"dataset_id": ds.id})}


# ------------------------------------------------------------------------------------------------ analytics
def _suggestions(db: Session, ds_id: str, f: Filters) -> list[dict]:
    rows = db.execute(select(Conversation.primary_topic, Conversation.resolution_status, Conversation.escalation_requested)
                      .where(*metrics.conditions(ds_id, f))).all()
    by_topic: dict[str, dict] = {}
    for t, r, e in rows:
        if t in ("unknown", "other"):
            continue
        d = by_topic.setdefault(t, {"n": 0, "unres": 0, "known": 0, "esc": 0, "esc_known": 0})
        d["n"] += 1
        d["unres"] += r == "unresolved_explicit"
        d["known"] += r != "unknown"
        d["esc"] += e == "yes"
        d["esc_known"] += e != "unknown"
    out = []
    if by_topic:
        t, d = max(by_topic.items(), key=lambda kv: (kv[1]["unres"], kv[0]))
        ev = metrics.sample_evidence(db, ds_id, f.model_copy(update={"topics": [t], "resolution": ["unresolved_explicit"]}), "resolution_status", "unresolved_explicit", 2)
        out.append({"title": f"Investigate unresolved {topic_label(t).lower()} conversations",
                    "basis": f"{d['unres']} of {d['known']} {topic_label(t).lower()} conversations with a known outcome were explicitly unresolved.",
                    "question": "Why is this happening?", "filters": {"topics": [t]}, "evidence": ev})
        t2, d2 = max(by_topic.items(), key=lambda kv: (kv[1]["esc"], kv[0]))
        ev2 = metrics.sample_evidence(db, ds_id, f.model_copy(update={"topics": [t2], "escalation": ["yes"]}), "escalation_requested", "yes", 2)
        out.append({"title": f"Review escalation requests in {topic_label(t2).lower()}",
                    "basis": f"{d2['esc']} of {d2['esc_known']} {topic_label(t2).lower()} conversations with a known value requested escalation.",
                    "question": "Show the evidence behind this chart.", "filters": {"topics": [t2], "escalation": ["yes"]}, "evidence": ev2})
        t3, d3 = max(by_topic.items(), key=lambda kv: ((kv[1]["n"] - kv[1]["known"]) / kv[1]["n"], kv[0]))
        ev3 = metrics.sample_evidence(db, ds_id, f.model_copy(update={"topics": [t3]}), "primary_topic", t3, 2)
        out.append({"title": f"Check outcome visibility for {topic_label(t3).lower()}",
                    "basis": f"{d3['n'] - d3['known']} of {d3['n']} {topic_label(t3).lower()} conversations have no observable outcome in the thread.",
                    "question": "Explain the limitations of this analysis.", "filters": {"topics": [t3]}, "evidence": ev3})
    return out


@router.get("/datasets/{dataset_id}/overview")
def overview(ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    q = quality.report(db, ds.id)
    return {
        "dataset": dataset_info(ds),
        "summary": metrics.dataset_summary(db, ds.id, f),
        "topics": metrics.breakdown(db, ds.id, f, "primary_topic"),
        "resolution": metrics.breakdown(db, ds.id, f, "resolution_status"),
        "sentiment": metrics.breakdown(db, ds.id, f, "sentiment_end"),
        "escalation": metrics.breakdown(db, ds.id, f, "escalation_requested"),
        "limitations": {"unknown_labels": q["unknown_labels"], "exclusions": q["manifest"].get("exclusions", {}),
                        "sampling": q["sampling"], "partial": q["missing_messages"]["partial_conversations"]},
        "suggestions": _suggestions(db, ds.id, f),
    }


@router.get("/datasets/{dataset_id}/breakdown/{field}")
def breakdown(field: str, ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    if field not in metrics.GROUPABLE:
        raise HTTPException(400, "Unsupported field")
    return metrics.breakdown(db, ds.id, f, field)


@router.get("/datasets/{dataset_id}/crosstab")
def crosstab(rows: str = Query(...), cols: str = Query(...), ds: Dataset = Depends(ready_dataset),
             f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    if rows not in metrics.GROUPABLE or cols not in metrics.GROUPABLE:
        raise HTTPException(400, "Unsupported field")
    return metrics.cross_tab(db, ds.id, f, rows, cols)


@router.get("/datasets/{dataset_id}/timeseries")
def timeseries(grain: str = Query("week", pattern="^(day|week|month)$"), ds: Dataset = Depends(ready_dataset),
               f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    return metrics.timeseries(db, ds.id, f, grain)


@router.get("/datasets/{dataset_id}/cohorts")
def cohorts(ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    return metrics.compare(db, ds.id, f, Filters(resolution=["resolved_confirmed"]), Filters(resolution=["unresolved_explicit"]),
                           ("Customer-confirmed resolved", "Explicitly unresolved"))


@router.get("/datasets/{dataset_id}/maps/issues")
def issue_map(ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    return metrics.topic_cooccurrence(db, ds.id, f)


@router.get("/datasets/{dataset_id}/maps/journey")
def journey_map(ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    return metrics.journey(db, ds.id, f)


@router.get("/datasets/{dataset_id}/maps/ownership")
def ownership_map(ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    cands = candidates(db, ds.id, f)["candidates"][:8]
    acts = db.scalars(select(Action).where(Action.dataset_id == ds.id)).all()
    return {"candidates": [{k: c[k] for k in ("key", "topic", "topic_label", "title", "intervention", "proposed_department", "frequency")} for c in cands],
            "actions": [{"id": a.id, "title": a.title, "issue": a.issue, "status": a.status, "owner": a.owner,
                         "owner_confirmed": a.owner_confirmed, "department": a.proposed_department} for a in acts],
            "note": "Departments are proposed from a fixed topic-to-function template, not inferred from the data. "
                    "Ownership stays 'proposed' until a reviewer confirms an owner on the action record."}


@router.get("/datasets/{dataset_id}/maps/geo")
def geo_map(ds: Dataset = Depends(ready_dataset)):
    cols = ((ds.manifest or {}).get("schema") or {}).get("columns", [])
    has_loc = any(c.lower() in ("country", "region", "city", "location", "lat", "latitude") for c in cols)
    return {"available": False, "reason": "Geographic analysis unavailable: reliable location data is absent.",
            "location_columns_detected": has_loc}


class Weights(BaseModel):
    frequency: float = Field(default=DEFAULT_WEIGHTS["frequency"], ge=0, le=1)
    severity: float = Field(default=DEFAULT_WEIGHTS["severity"], ge=0, le=1)
    evidence: float = Field(default=DEFAULT_WEIGHTS["evidence"], ge=0, le=1)
    effort: float = Field(default=DEFAULT_WEIGHTS["effort"], ge=0, le=1)


@router.get("/datasets/{dataset_id}/opportunities")
def opportunities(w_frequency: float = 0.35, w_severity: float = 0.35, w_evidence: float = 0.2, w_effort: float = 0.1,
                  ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    w = Weights(frequency=w_frequency, severity=w_severity, evidence=w_evidence, effort=w_effort)
    return candidates(db, ds.id, f, w.model_dump())


class OpportunityInput(BaseModel):
    effort: int | None = Field(default=None, ge=1, le=5)
    effort_source: str | None = Field(default=None, max_length=200)
    severity: int | None = Field(default=None, ge=1, le=5)
    reviewer: str = Field(min_length=1, max_length=80)


@router.put("/datasets/{dataset_id}/opportunities/{key}")
def review_opportunity(key: str, body: OpportunityInput, ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    if len(key) > 80 or ":" not in key:
        raise HTTPException(400, "Invalid candidate key")
    row = db.scalar(select(OpportunityReview).where(OpportunityReview.dataset_id == ds.id, OpportunityReview.candidate_key == key))
    if row is None:
        row = OpportunityReview(dataset_id=ds.id, candidate_key=key)
        db.add(row)
    row.effort, row.effort_source, row.severity, row.reviewer = body.effort, body.effort_source, body.severity, body.reviewer
    db.commit()
    return {"saved": True}


class ImpactRequest(BaseModel):
    baseline_dataset: str
    followup_dataset: str | None = None
    intervention_date: date
    filters: Filters = Field(default_factory=Filters)
    action_id: int | None = None
    reviewer: str = Field(default="reviewer", max_length=80)


@router.post("/impact")
def impact(body: ImpactRequest, db: Session = Depends(get_db)):
    from app.models.orm import ImpactReview
    try:
        res = impact_mod.review(db, baseline_dataset=body.baseline_dataset, followup_dataset=body.followup_dataset,
                                intervention_date=body.intervention_date, filters=body.filters)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    db.add(ImpactReview(action_id=body.action_id, dataset_id=body.baseline_dataset, intervention_date=body.intervention_date.isoformat(),
                        params=body.model_dump(mode="json"), result=res, reviewer=body.reviewer))
    db.commit()
    return res


@router.get("/datasets/{dataset_id}/languages")
def languages(ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    return lang_mod.dashboard(db, ds.id)


# ------------------------------------------------------------------------------------------------ conversations
@router.get("/datasets/{dataset_id}/conversations")
def conversations(q: str | None = Query(default=None, max_length=300), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                  ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    hits_by_key: dict[str, list] = {}
    retrieval = None
    conds = metrics.conditions(ds.id, f)
    if q:
        retrieval = search(db, ds.id, q, f, k=60, role=None)
        for h in retrieval["hits"]:
            hits_by_key.setdefault(h["conversation_key"], []).append({"message_id": h["message_id"], "text": h["text"], "score": h["score"]})
        keys = list(hits_by_key)
        total = len(keys)
        page_keys = keys[(page - 1) * page_size: page * page_size]
        rows = {c.key: c for c in db.scalars(select(Conversation).where(Conversation.dataset_id == ds.id, Conversation.key.in_(page_keys)))}
        convs = [rows[k] for k in page_keys if k in rows]
    else:
        total = db.scalar(select(func.count(Conversation.id)).where(*conds)) or 0
        convs = db.scalars(select(Conversation).where(*conds).order_by(Conversation.started_at.desc().nullslast(), Conversation.key)
                           .offset((page - 1) * page_size).limit(page_size)).all()
    first_msgs = {}
    if convs:
        for cid, text in db.execute(select(Message.conversation_id, Message.text).where(Message.conversation_id.in_([c.id for c in convs]), Message.position == 0)).all():
            first_msgs[cid] = text
    return {"total": total, "page": page, "page_size": page_size, "scope": f.describe(),
            "retrieval": {k: retrieval[k] for k in ("methods_used", "semantic_unavailable_reason", "candidates_in_scope")} if retrieval else None,
            "items": [{"key": c.key, "brand": c.brand, "started_at": c.started_at.isoformat() if c.started_at else None,
                       "message_count": c.message_count, "branch_count": c.branch_count, "languages": c.languages,
                       "primary_topic": c.primary_topic, "resolution_status": c.resolution_status, "sentiment_end": c.sentiment_end,
                       "escalation_requested": c.escalation_requested, "corrected": c.corrected, "completeness": c.completeness,
                       "first_message": first_msgs.get(c.id, ""), "matches": hits_by_key.get(c.key, [])} for c in convs]}


@router.get("/datasets/{dataset_id}/conversations/export.csv")
def export_conversations(ds: Dataset = Depends(ready_dataset), f: Filters = Depends(parse_filters), db: Session = Depends(get_db)):
    convs = db.scalars(select(Conversation).where(*metrics.conditions(ds.id, f)).order_by(Conversation.key)).all()
    body = to_csv(["conversation_key", "brand", "started_at", "messages", "primary_topic", "resolution_status", "sentiment_start",
                   "sentiment_end", "escalation_requested", "languages", "corrected"],
                  ([c.key, c.brand, c.started_at.isoformat() if c.started_at else "", c.message_count, c.primary_topic, c.resolution_status,
                    c.sentiment_start, c.sentiment_end, c.escalation_requested, " ".join(c.languages), c.corrected] for c in convs))
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="conversations_{ds.id}.csv"'})


@router.get("/datasets/{dataset_id}/conversations/{key}")
def conversation(key: str, ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    if not key.startswith("cv_") or len(key) != 19:
        raise HTTPException(400, "Invalid conversation key")
    try:
        d = get_conversation_detail(db, ds.id, key)
    except ValueError:
        raise HTTPException(404, "Conversation not found")
    conv = db.scalar(select(Conversation).where(Conversation.dataset_id == ds.id, Conversation.key == key))
    corr = db.scalars(select(Correction).where(Correction.target_type == "conversation", Correction.target_id == conv.id).order_by(Correction.id)).all()
    msg_ids = {m.source_id: m.id for m in conv.messages}
    trs = db.scalars(select(Translation).where(Translation.message_id.in_(list(msg_ids.values())))).all()
    by_mid = {}
    for t in trs:
        by_mid.setdefault(t.message_id, []).append({"text": t.text, "method": t.method, "model_id": t.model_id, "prompt_version": t.prompt_version,
                                                     "needs_review": t.needs_review, "checks": t.checks, "translated": True})
    for m in d["messages"]:
        m["translations"] = by_mid.get(msg_ids[m["message_id"]], [])
    # Turn-level inferred sentiment (rules) for the sentiment journey chart.
    turns = []
    for m in d["messages"]:
        if m["role"] == "customer":
            label, ev = _sentiment(Msg(m["message_id"], "customer", m["text"], m["language"]))
            turns.append({"message_id": m["message_id"], "position": len(turns) + 1, "sentiment": label, "text": m["text"],
                          "evidence": ev["quote"] if ev else None})
    d["sentiment_journey"] = {"method": "rules-v1 lexicon per customer message (inferred)", "turns": turns}
    d["corrections"] = [{"field": c.field, "original": c.original_value, "corrected": c.corrected_value, "reviewer": c.reviewer,
                         "note": c.note, "at": c.created_at.isoformat()} for c in corr]
    return d


class CorrectionIn(BaseModel):
    field: str
    value: str = Field(max_length=60)
    reviewer: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)


@router.post("/datasets/{dataset_id}/conversations/{key}/corrections")
def correct(key: str, body: CorrectionIn, ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    allowed = {"primary_topic": TOPIC_KEYS, "resolution_status": list(RESOLUTION), "sentiment_start": list(SENTIMENT),
               "sentiment_end": list(SENTIMENT), "escalation_requested": list(ESCALATION)}
    if body.field not in CORRECTABLE or body.value not in allowed[body.field]:
        raise HTTPException(422, "Invalid field or value")
    conv = db.scalar(select(Conversation).where(Conversation.dataset_id == ds.id, Conversation.key == key))
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    from app.models.orm import Analysis
    a = db.get(Analysis, conv.analysis_id) if conv.analysis_id else None
    original = (a.fields.get(body.field) if a else None)
    db.add(Correction(dataset_id=ds.id, target_type="conversation", target_id=conv.id, field=body.field, original_value=original,
                      corrected_value=body.value, reviewer=body.reviewer, note=body.note))
    db.flush()
    reapply(db, conv)
    db.commit()
    return {"saved": True, "confirmed_unchanged": original == body.value}


class LanguageCorrectionIn(BaseModel):
    message_id: str = Field(pattern=r"^\d{1,25}$")
    language: str = Field(pattern=r"^([a-z]{2}(-[A-Z][a-z]{3})?|mixed|unknown)$")
    reviewer: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)


@router.post("/datasets/{dataset_id}/messages/language")
def correct_language(body: LanguageCorrectionIn, ds: Dataset = Depends(ready_dataset), db: Session = Depends(get_db)):
    m = db.scalar(select(Message).where(Message.dataset_id == ds.id, Message.source_id == body.message_id))
    if m is None:
        raise HTTPException(404, "Message not found")
    db.add(Correction(dataset_id=ds.id, target_type="message", target_id=m.id, field="language", original_value=m.language,
                      corrected_value=body.language, reviewer=body.reviewer, note=body.note))
    m.language, m.language_corrected = body.language, True
    conv = db.get(Conversation, m.conversation_id)
    conv.languages = sorted({x.language for x in conv.messages})
    db.commit()
    invalidate(ds.id)
    return {"saved": True}


@router.get("/retrieval/status")
def retrieval_status():
    return semantic_status()
