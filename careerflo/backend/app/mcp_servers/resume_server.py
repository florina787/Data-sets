"""MCP Server B — Resume Intelligence."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..careers import resume as R
from ..careers.context import as_uuid, candidate_profile, get_job, get_resume
from ..careers.matching import match_job
from ..db import SessionLocal
from ..jobs.skills import extract_skills as _extract
from ..models import JobMatch, ResumeVersion

VERSION = "1.0.0"
mcp = FastMCP("careerflo-resume")


@mcp.tool(description="Parse resume text into contact, skills, experience, education, certifications and projects.")
def parse_resume(text: str) -> dict:
    return R.parse_resume(text[:60000])


@mcp.tool(description="Extract canonical skills from any text.")
def extract_skills(text: str) -> dict:
    return {"skills": _extract(text[:60000])}


@mcp.tool(description="Analyse the user's resume for gaps and strengths.")
def analyze_resume(user_id: str, resume_id: str | None = None) -> dict:
    with SessionLocal() as db:
        r = get_resume(db, as_uuid(user_id), resume_id)
        return {"resume_id": str(r.id), **R.analyze_resume(r.parsed)}


@mcp.tool(description="Explainable match between the user's verified resume and a job.")
def compare_resume_to_job(user_id: str, job_id: str, resume_id: str | None = None) -> dict:
    with SessionLocal() as db:
        uid = as_uuid(user_id)
        r = get_resume(db, uid, resume_id)
        job = get_job(db, job_id)
        m = match_job(candidate_profile(db, uid, r), job)
        db.add(JobMatch(user_id=uid, job_id=as_uuid(job_id), resume_id=r.id, score=m["score"], breakdown=m))
        db.commit()
        return {"job": {k: job[k] for k in ("id", "title", "company")}, **m}


@mcp.tool(description="Tailor the user's resume to a job using only facts already in the resume; saves a new version.")
def tailor_resume(user_id: str, job_id: str, resume_id: str | None = None, summary: str | None = None) -> dict:
    with SessionLocal() as db:
        uid = as_uuid(user_id)
        r = get_resume(db, uid, resume_id)
        job = get_job(db, job_id)
        tailored = R.tailor_resume(r.parsed, job)
        validation = {"valid": True, "issues": []}
        if summary:
            v = R.validate_claims(r.original_text, r.parsed, summary)
            if v["valid"]:
                tailored["summary"] = summary
            validation = {"valid": True, "issues": [], "llm_summary_rejected": not v["valid"], "rejected_issues": v["issues"]}
        text = R.render_text(tailored)
        final = R.validate_claims(r.original_text, r.parsed, text)
        validation["final"] = final
        v_row = ResumeVersion(user_id=uid, resume_id=r.id, job_id=as_uuid(job_id), label=f"{job['title']} — {job['company']}"[:200],
                              content=tailored, text=text, validation=validation)
        db.add(v_row)
        db.commit()
        return {"version_id": str(v_row.id), "tailored": tailored, "text": text, "validation": validation,
                "downloads": {"pdf": f"/api/resumes/versions/{v_row.id}/export.pdf", "docx": f"/api/resumes/versions/{v_row.id}/export.docx"}}


@mcp.tool(description="Check generated text for claims (numbers, skills, degrees, employers) the resume does not support.")
def validate_resume_claims(user_id: str, text: str, resume_id: str | None = None) -> dict:
    with SessionLocal() as db:
        r = get_resume(db, as_uuid(user_id), resume_id)
        return R.validate_claims(r.original_text, r.parsed, text[:30000])


def _version(user_id: str, version_id: str) -> ResumeVersion:
    with SessionLocal() as db:
        v = db.get(ResumeVersion, as_uuid(version_id, "version id"))
        if v is None or v.user_id != as_uuid(user_id):
            raise LookupError("Resume version not found")
        return v


@mcp.tool(description="Render a resume version to PDF; returns the download URL.")
def generate_pdf(user_id: str, version_id: str) -> dict:
    v = _version(user_id, version_id)
    size = len(R.export_pdf(v.content))
    return {"url": f"/api/resumes/versions/{v.id}/export.pdf", "bytes": size}


@mcp.tool(description="Render a resume version to DOCX; returns the download URL.")
def generate_docx(user_id: str, version_id: str) -> dict:
    v = _version(user_id, version_id)
    size = len(R.export_docx(v.content))
    return {"url": f"/api/resumes/versions/{v.id}/export.docx", "bytes": size}
