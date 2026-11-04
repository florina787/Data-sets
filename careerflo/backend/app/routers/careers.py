"""Metered career-intelligence endpoints: matching, ATS, cover letters, interviews, coding, company, salary, portfolio, analytics."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import mcp_gateway as gw
from ..billing.metering import metered
from ..careers import ats as ATS
from ..careers import cover_letter as CL
from ..careers import interview as IV
from ..careers.coding import EXERCISES, UnsafeCode, public_exercises, run_solution
from ..careers.context import NotFound, get_job, get_resume
from ..careers.salary import negotiation_scenarios
from ..llm.qwen import LLMUnavailable, get_llm
from ..models import Interview, utcnow
from ..security.auth import CurrentUser, DB
from ..security.sanitize import wrap_untrusted
from .common import IdemKey, with_usage

router = APIRouter(prefix="/api", tags=["career intelligence"])


def _nf(fn):
    try:
        return fn()
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


# ---------------------------------------------------------------- matching
class MatchIn(BaseModel):
    job_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    resume_id: uuid.UUID | None = None


@router.post("/match")
async def match(body: MatchIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "job_matching", idem) as m:
        if m.replay is not None:
            return m.replay
        ranked = []
        for jid in body.job_ids:
            args = {"job_id": str(jid)} | ({"resume_id": str(body.resume_id)} if body.resume_id else {})
            ranked.append((await gw.call_tool(user.id, "user", "resume", "compare_resume_to_job", args)).data)
        ranked.sort(key=lambda r: -r["score"])
        result = {"ranked": ranked, "methodology": ranked[0]["methodology"] if ranked else None}
        m.set_result(result)
    return with_usage(result, user.id, "job_matching")


# ---------------------------------------------------------------- ATS
class AtsIn(BaseModel):
    job_id: uuid.UUID | None = None
    resume_id: uuid.UUID | None = None
    job_description: str | None = Field(None, max_length=20000)


@router.post("/ats/analyze")
async def ats(body: AtsIn, user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    async with metered(user.id, "ats_intelligence", idem) as m:
        if m.replay is not None:
            return m.replay
        r = _nf(lambda: get_resume(db, user.id, str(body.resume_id) if body.resume_id else None))
        job: dict[str, Any] | None = None
        if body.job_id:
            job = _nf(lambda: get_job(db, str(body.job_id)))
        elif body.job_description:
            from ..jobs.skills import split_required_preferred

            req, pref = split_required_preferred(body.job_description)
            job = {"title": body.job_description.splitlines()[0][:120], "required_skills": req, "preferred_skills": pref,
                   "description": body.job_description}
        result = ATS.ats_check(r.original_text, r.parsed, job)
        m.set_result(result)
    return with_usage(result, user.id, "ats_intelligence")


# ---------------------------------------------------------------- cover letters
class CoverIn(BaseModel):
    job_id: uuid.UUID
    resume_id: uuid.UUID | None = None
    tone: str = Field("professional", pattern="^(professional|warm|concise)$")
    use_ai: bool = True


@router.post("/cover-letters")
async def cover_letter(body: CoverIn, user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    async with metered(user.id, "cover_letter", idem) as m:
        if m.replay is not None:
            return m.replay
        r = _nf(lambda: get_resume(db, user.id, str(body.resume_id) if body.resume_id else None))
        job = _nf(lambda: get_job(db, str(body.job_id)))
        letter = CL.draft_cover_letter(r.parsed, job, body.tone)
        source = "deterministic"
        if body.use_ai and get_llm().enabled:
            resume_block, _ = wrap_untrusted("RESUME", r.original_text, 5000)
            msgs = [{"role": "system", "content": "Polish the DRAFT cover letter for clarity and tone. Keep every fact; add NO new "
                                                  "employers, numbers, skills, degrees or achievements. Return only the letter."},
                    {"role": "user", "content": f"{resume_block}\n\nDRAFT:\n{letter}"}]
            try:
                out = await get_llm().complete(msgs, purpose="cover_letter", user_id=user.id, max_tokens=600)
                v = (await gw.call_tool(user.id, "user", "resume", "validate_resume_claims", {"text": out.text})).data
                if out.text and v["valid"]:
                    letter, source = out.text, f"qwen ({out.model}), fact-checked"
                else:
                    source = "deterministic (AI draft rejected by fact check)"
            except LLMUnavailable:
                source = "deterministic (Qwen unavailable)"
        check = (await gw.call_tool(user.id, "user", "resume", "validate_resume_claims", {"text": letter})).data
        result = {"letter": letter, "recruiter_message": CL.recruiter_message(r.parsed, job), "validation": check, "source": source,
                  "job": {"title": job["title"], "company": job["company"]}}
        m.set_result(result)
    return with_usage(result, user.id, "cover_letter")


# ---------------------------------------------------------------- mock interviews
class MockIn(BaseModel):
    role: str = Field(min_length=2, max_length=200)
    topics: list[str] | None = None
    questions: int = Field(5, ge=1, le=10)


@router.get("/interviews/topics")
def topics() -> dict:
    return {"topics": IV.TOPICS}


@router.post("/interviews/mock", status_code=201)
async def start_mock(body: MockIn, user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    if body.topics and any(t not in IV.BANK for t in body.topics):
        raise HTTPException(422, f"Unknown topic. Choose from: {', '.join(IV.TOPICS)}")
    async with metered(user.id, "mock_interview", idem) as m:
        if m.replay is not None:
            return m.replay
        qs = IV.plan_interview(body.role, body.topics, body.questions)
        iv = Interview(user_id=user.id, kind="mock", role=body.role, topic=",".join(sorted({q["topic"] for q in qs}))[:100],
                       status="in_progress", transcript=[{"q": q, "answer": None, "evaluation": None} for q in qs])
        db.add(iv)
        db.commit()
        result = {"interview_id": str(iv.id), "role": body.role, "question_count": len(qs), "current": 0,
                  "question": {k: qs[0][k] for k in ("question", "topic", "kind")}}
        m.set_result(result)
    return with_usage(result, user.id, "mock_interview")


def _iv(db, user_id, iid: uuid.UUID) -> Interview:
    iv = db.get(Interview, iid)
    if not iv or iv.user_id != user_id:
        raise HTTPException(404, "Interview not found")
    return iv


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    ai_feedback: bool = True


@router.post("/interviews/{iid}/answer")
async def answer(iid: uuid.UUID, body: AnswerIn, user: CurrentUser, db: DB) -> dict:
    """Answers inside a started session are part of that session (no extra charge)."""
    iv = _iv(db, user.id, iid)
    if iv.status != "in_progress":
        raise HTTPException(409, "This interview is finished")
    transcript = [dict(t) for t in iv.transcript]
    idx = next((i for i, t in enumerate(transcript) if t["answer"] is None), None)
    if idx is None:
        raise HTTPException(409, "All questions answered")
    q = transcript[idx]["q"]
    ev = IV.evaluate_answer(q, body.answer)
    if body.ai_feedback and get_llm().enabled:
        ans_block, _ = wrap_untrusted("CANDIDATE_ANSWER", body.answer, 4000)
        msgs = [{"role": "system", "content": "You are a fair technical interviewer. Give 2-3 sentences of specific, constructive feedback. "
                                              "Do not score; do not invent facts about the candidate."},
                {"role": "user", "content": f"Question: {q['question']}\nKey concepts: {', '.join(q['concepts'])}\n{ans_block}"}]
        try:
            out = await get_llm().complete(msgs, purpose="interview_feedback", user_id=user.id, max_tokens=160)
            ev["ai_feedback"] = out.text
        except LLMUnavailable:
            ev["ai_feedback"] = None
    transcript[idx] = {**transcript[idx], "answer": body.answer, "evaluation": ev}
    iv.transcript = transcript
    nxt = idx + 1 if idx + 1 < len(transcript) else None
    if nxt is None:
        scores = [t["evaluation"]["score"] for t in transcript if t["evaluation"]]
        iv.score = round(sum(scores) / len(scores), 1)
        iv.status = "completed"
        iv.feedback = {"average": iv.score, "strongest": max(transcript, key=lambda t: t["evaluation"]["score"])["q"]["topic"],
                       "weakest": min(transcript, key=lambda t: t["evaluation"]["score"])["q"]["topic"]}
    db.commit()
    return {"evaluation": ev, "next": None if nxt is None else {"index": nxt, **{k: transcript[nxt]["q"][k] for k in ("question", "topic", "kind")}},
            "completed": nxt is None, "score": iv.score, "feedback": iv.feedback}


@router.get("/interviews")
def list_interviews(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(Interview).where(Interview.user_id == user.id, Interview.kind.in_(["mock", "real"]))
                      .order_by(Interview.created_at.desc()).limit(100))
    return {"interviews": [{"id": str(i.id), "kind": i.kind, "role": i.role, "topic": i.topic, "status": i.status, "score": i.score,
                            "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                            "created_at": i.created_at.isoformat(), "is_synthetic": i.is_synthetic} for i in rows]}


@router.get("/interviews/{iid}")
def get_interview(iid: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    iv = _iv(db, user.id, iid)
    return {"id": str(iv.id), "role": iv.role, "status": iv.status, "score": iv.score, "feedback": iv.feedback,
            "transcript": [{"question": t["q"]["question"], "topic": t["q"].get("topic"), "answer": t["answer"], "evaluation": t["evaluation"]}
                           for t in iv.transcript]}


# ---------------------------------------------------------------- live coding coach
@router.get("/coding/exercises")
def exercises() -> dict:
    return {"exercises": public_exercises()}


class CodingSessionIn(BaseModel):
    exercise_id: str


@router.post("/coding/sessions", status_code=201)
async def coding_session(body: CodingSessionIn, user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    if body.exercise_id not in EXERCISES:
        raise HTTPException(404, "Unknown exercise")
    async with metered(user.id, "coding_coach", idem) as m:
        if m.replay is not None:
            return m.replay
        s = Interview(user_id=user.id, kind="coding", topic=body.exercise_id, status="in_progress", transcript=[])
        db.add(s)
        db.commit()
        ex = next(e for e in public_exercises() if e["id"] == body.exercise_id)
        result = {"session_id": str(s.id), "exercise": ex, "max_runs": 30}
        m.set_result(result)
    return with_usage(result, user.id, "coding_coach")


class RunIn(BaseModel):
    code: str = Field(min_length=1, max_length=20000)


@router.post("/coding/sessions/{sid}/run")
def coding_run(sid: uuid.UUID, body: RunIn, user: CurrentUser, db: DB) -> dict:
    s = db.get(Interview, sid)
    if not s or s.user_id != user.id or s.kind != "coding":
        raise HTTPException(404, "Session not found")
    if len(s.transcript) >= 30:
        raise HTTPException(429, "Run limit for this session reached; start a new session.")
    try:
        res = run_solution(s.topic, body.code)
    except UnsafeCode as exc:
        res = {"passed": 0, "total": len(EXERCISES[s.topic]["tests"]), "results": [], "error": str(exc)}
    s.transcript = [*s.transcript, {"at": utcnow().isoformat(), "passed": res["passed"], "total": res["total"]}]
    if res["total"] and res["passed"] == res["total"]:
        s.status, s.score = "completed", 10.0
    db.commit()
    return res


# ---------------------------------------------------------------- company research
class CompanyIn(BaseModel):
    company: str = Field(min_length=2, max_length=100)
    use_web: bool = True


@router.post("/company/research")
async def company_research(body: CompanyIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "company_research", idem) as m:
        if m.replay is not None:
            return m.replay
        result = (await gw.call_tool(user.id, "user", "company", "retrieve_company_information",
                                     {"company": body.company, "use_web": body.use_web})).data
        m.set_result(result)
    return with_usage(result, user.id, "company_research")


class CompareIn(BaseModel):
    companies: list[str] = Field(min_length=2, max_length=5)


@router.post("/company/compare")
async def company_compare(body: CompareIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "company_research", idem) as m:
        if m.replay is not None:
            return m.replay
        result = (await gw.call_tool(user.id, "user", "company", "compare_companies", {"companies": body.companies})).data
        m.set_result(result)
    return with_usage(result, user.id, "company_research")


# ---------------------------------------------------------------- salary
class SalaryIn(BaseModel):
    title_keyword: str = Field("", max_length=80)
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    city: str | None = Field(None, max_length=80)
    offer: float | None = Field(None, gt=0, le=5_000_000)


@router.post("/salary/report")
async def salary_report(body: SalaryIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "salary_intelligence", idem) as m:
        if m.replay is not None:
            return m.replay
        dist = (await gw.call_tool(user.id, "user", "analytics", "analyze_salary_distribution",
                                   {"title_keyword": body.title_keyword, "currency": body.currency, "city": body.city})).data
        result = {"distribution": dist, "negotiation": negotiation_scenarios(body.offer, dist) if body.offer else None}
        m.set_result(result)
    return with_usage(result, user.id, "salary_intelligence")


# ---------------------------------------------------------------- GitHub portfolio
class PortfolioIn(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9-]{1,39}$")
    job_id: uuid.UUID | None = None


@router.post("/portfolio/analyze")
async def portfolio(body: PortfolioIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "portfolio_analysis", idem) as m:
        if m.replay is not None:
            return m.replay
        try:
            summary = (await gw.call_tool(user.id, "user", "portfolio", "generate_portfolio_summary", {"username": body.username})).data
            matches = None
            if body.job_id:
                matches = (await gw.call_tool(user.id, "user", "portfolio", "match_project_to_job",
                                              {"username": body.username, "job_id": str(body.job_id)})).data
        except gw.ToolFailed as exc:
            raise HTTPException(502, f"GitHub analysis failed: {exc}") from exc
        result = {"summary": summary, "matches": matches}
        m.set_result(result)
    return with_usage(result, user.id, "portfolio_analysis")


# ---------------------------------------------------------------- career analytics
@router.get("/analytics/summary")
def analytics_summary(user: CurrentUser, db: DB) -> dict:
    """Free: counts of the user's own records."""
    from ..careers.analytics import application_metrics
    from ..models import Application, SavedJob

    apps = list(db.scalars(select(Application).where(Application.user_id == user.id)))
    return {"applications": application_metrics(apps),
            "saved_jobs": db.query(SavedJob).filter(SavedJob.user_id == user.id).count(),
            "interviews": db.query(Interview).filter(Interview.user_id == user.id, Interview.kind == "real").count()}


@router.post("/analytics/report")
async def analytics_report(user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "career_analytics", idem) as m:
        if m.replay is not None:
            return m.replay
        result = (await gw.call_tool(user.id, "user", "analytics", "generate_dashboard_data", {})).data
        m.set_result(result)
    return with_usage(result, user.id, "career_analytics")


# ---------------------------------------------------------------- roadmap / skills planner (part of analytics report allowance)
@router.post("/analytics/roadmap")
async def roadmap(user: CurrentUser, idem: IdemKey = None) -> dict:
    async with metered(user.id, "career_analytics", idem) as m:
        if m.replay is not None:
            return m.replay
        gaps = (await gw.call_tool(user.id, "user", "analytics", "identify_skill_gaps", {})).data
        plan = []
        for i, g in enumerate(gaps["gaps"][:6]):
            plan.append({"week": f"{i * 2 + 1}-{i * 2 + 2}", "skill": g["skill"], "demand": g["demand"],
                         "activities": [f"Build a small project that uses {g['skill']}", f"Add {g['skill']} to your profile once you have used it",
                                        f"Practise interview questions involving {g['skill']}"]})
        result = {"roadmap": plan, "based_on_jobs": gaps["based_on_jobs"],
                  "note": "Ordered by how often stored postings require each skill you have not verified yet."}
        m.set_result(result)
    return with_usage(result, user.id, "career_analytics")
