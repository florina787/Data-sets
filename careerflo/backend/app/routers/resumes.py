from __future__ import annotations

import difflib
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from .. import mcp_gateway as gw
from ..billing.metering import metered
from ..careers import resume as R
from ..config import get_settings
from ..governance.approvals import request_approval
from ..llm.qwen import LLMUnavailable, get_llm
from ..models import Resume, ResumeVersion, Skill
from ..security.auth import CurrentUser, DB
from ..security.sanitize import wrap_untrusted
from ..security.uploads import validate_upload
from .common import IdemKey, with_usage

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _resume(r: Resume, full: bool = False) -> dict:
    d = {"id": str(r.id), "title": r.title, "filename": r.original_filename, "is_primary": r.is_primary,
         "is_synthetic": r.is_synthetic, "created_at": r.created_at.isoformat(), "skills": r.parsed.get("skills", [])[:40],
         "years_experience": r.parsed.get("years_experience")}
    if full:
        d |= {"parsed": r.parsed, "original_text": r.original_text}
    return d


@router.post("", status_code=201)
async def upload(user: CurrentUser, db: DB, file: UploadFile = File(...)) -> dict:
    data = await file.read(get_settings().max_upload_bytes + 1)
    mime = validate_upload(file.filename or "", data, get_settings().max_upload_bytes)
    try:
        text = R.extract_text(data, mime)
    except Exception as exc:  # noqa: BLE001 - malformed documents
        raise HTTPException(422, f"Could not read the document: {type(exc).__name__}") from exc
    if len(text.split()) < 30:
        raise HTTPException(422, "Too little text found. Scanned/image-only PDFs are not supported; upload a text PDF or DOCX.")
    parsed = R.parse_resume(text)
    has_primary = db.scalar(select(Resume.id).where(Resume.user_id == user.id, Resume.is_primary.is_(True)))
    r = Resume(user_id=user.id, title=(file.filename or "Resume")[:200], original_filename=(file.filename or "")[:255],
               mime_type=mime, original_text=text, parsed=parsed, is_primary=not has_primary)
    db.add(r)
    existing = {s.name.lower() for s in db.scalars(select(Skill).where(Skill.user_id == user.id))}
    for s in parsed["taxonomy_skills"]:
        if s.lower() not in existing:
            db.add(Skill(user_id=user.id, name=s, source="resume", verified=True))
    db.commit()
    return _resume(r, full=True) | {"analysis": R.analyze_resume(parsed)}


@router.get("")
def list_resumes(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc()))
    return {"resumes": [_resume(r) for r in rows]}


def _owned(db, user_id, resume_id: uuid.UUID) -> Resume:
    r = db.get(Resume, resume_id)
    if not r or r.user_id != user_id:
        raise HTTPException(404, "Resume not found")
    return r


@router.get("/{resume_id}")
def get_resume(resume_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    r = _owned(db, user.id, resume_id)
    return _resume(r, full=True) | {"analysis": R.analyze_resume(r.parsed)}


@router.post("/{resume_id}/primary")
def make_primary(resume_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    r = _owned(db, user.id, resume_id)
    db.execute(update(Resume).where(Resume.user_id == user.id).values(is_primary=False))
    r.is_primary = True
    db.commit()
    return {"primary": str(r.id)}


@router.delete("/{resume_id}")
def delete_resume(resume_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    r = _owned(db, user.id, resume_id)
    req = request_approval(db, user.id, "delete_data", f"Delete resume '{r.title}' and its versions",
                           {"kind": "resume", "id": str(r.id)}, "user")
    return {"approval_required": True, "approval_id": str(req.id)}


class TailorIn(BaseModel):
    job_id: uuid.UUID
    resume_id: uuid.UUID | None = None
    use_ai_summary: bool = True


@router.post("/tailor")
async def tailor(body: TailorIn, user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    async with metered(user.id, "resume_optimization", idem) as m:
        if m.replay is not None:
            return m.replay
        resume = _owned(db, user.id, body.resume_id) if body.resume_id else None
        args = {"job_id": str(body.job_id)} | ({"resume_id": str(resume.id)} if resume else {})
        # Inside this metered block the nested match is *included* (not a separate Job Matching use).
        match = (await gw.call_tool(user.id, "user", "resume", "compare_resume_to_job", args)).data
        summary, ai = None, "deterministic"
        if body.use_ai_summary and get_llm().enabled:
            summary, ai = await _ai_summary(user.id, db, args, match)
        res = (await gw.call_tool(user.id, "user", "resume", "tailor_resume", args | ({"summary": summary} if summary else {}))).data
        result = {**res, "match": match, "summary_source": ai if not res["validation"].get("llm_summary_rejected") else "deterministic (AI summary rejected by fact check)"}
        m.set_result(result)
    return with_usage(result, user.id, "resume_optimization")


async def _ai_summary(user_id, db, args, match) -> tuple[str | None, str]:
    from ..careers.context import get_job, get_resume as load

    r = load(db, user_id, args.get("resume_id"))
    job = get_job(db, args["job_id"])
    resume_block, _ = wrap_untrusted("RESUME", r.original_text, 6000)
    job_block, _ = wrap_untrusted("JOB", f"{job['title']} at {job['company']}\n{job.get('description', '')}", 3000)
    msgs = [{"role": "system", "content": "You write resume summaries. Use ONLY facts in the RESUME block. Never add employers, degrees, "
                                          "certifications, numbers, skills or years that are not in the resume. 2-3 sentences, no first person."},
            {"role": "user", "content": f"{resume_block}\n\n{job_block}\n\nMatched skills: {', '.join(match.get('matched_required', []))}.\n"
                                        "Write the summary only."}]
    try:
        out = await get_llm().complete(msgs, purpose="resume_summary", user_id=user_id, max_tokens=180)
        text = out.text.strip().strip('"')
        return (text or None), f"qwen ({out.model})"
    except LLMUnavailable:
        return None, "deterministic (Qwen unavailable)"


@router.get("/{resume_id}/versions")
def versions(resume_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    _owned(db, user.id, resume_id)
    rows = db.scalars(select(ResumeVersion).where(ResumeVersion.resume_id == resume_id).order_by(ResumeVersion.created_at.desc()))
    return {"versions": [{"id": str(v.id), "label": v.label, "created_at": v.created_at.isoformat(),
                          "valid": v.validation.get("final", {}).get("valid", True)} for v in rows]}


def _version(db, user_id, version_id: uuid.UUID) -> ResumeVersion:
    v = db.get(ResumeVersion, version_id)
    if not v or v.user_id != user_id:
        raise HTTPException(404, "Version not found")
    return v


@router.get("/versions/{version_id}")
def get_version(version_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    v = _version(db, user.id, version_id)
    return {"id": str(v.id), "label": v.label, "content": v.content, "text": v.text, "validation": v.validation}


@router.get("/versions/{a}/compare/{b}")
def compare(a: uuid.UUID, b: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    va, vb = _version(db, user.id, a), _version(db, user.id, b)
    diff = list(difflib.unified_diff(va.text.splitlines(), vb.text.splitlines(), va.label, vb.label, lineterm="", n=1))
    return {"diff": diff[:800], "a": va.label, "b": vb.label}


@router.get("/versions/{version_id}/export.pdf")
def export_pdf(version_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    v = _version(db, user.id, version_id)
    return Response(R.export_pdf(v.content), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="resume-{version_id}.pdf"'})


@router.get("/versions/{version_id}/export.docx")
def export_docx(version_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    v = _version(db, user.id, version_id)
    return Response(R.export_docx(v.content),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="resume-{version_id}.docx"'})


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=30000)
    resume_id: uuid.UUID | None = None


@router.post("/validate")
async def validate(body: TextIn, user: CurrentUser) -> dict:
    args = {"text": body.text} | ({"resume_id": str(body.resume_id)} if body.resume_id else {})
    return (await gw.call_tool(user.id, "user", "resume", "validate_resume_claims", args)).data
