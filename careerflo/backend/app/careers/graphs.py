"""Career Graph Intelligence — the "semantic spine" of a job search.

* Knowledge graph  — what is TRUE: the user's verified facts (skills, roles, education, certifications), the jobs
  they saved or applied to, companies and recruiters. Every node carries its source.
* Context graph    — what MATTERS NOW: a small subgraph scoped to one target job, with live state (match score,
  matched skills vs gaps, posting age, application status, follow-ups, interviews). Nothing else is retrieved.
* Procedural graph — what to do NEXT: (procedure, condition, procedure) triplets for a job search. The current step
  and the recommended next step are derived from the context graph. It guides, it does not dictate: the user (or an
  agent, with a stated reason) may deviate, and consequential steps always go through human approval.
* Trace & learn    — what WORKED: outcomes from the user's own history (e.g. response rate with vs. without a
  tailored resume) so the guidance improves with evidence, not guesses.

Everything here is deterministic and computed from the user's own records — no model invents graph facts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs.normalize import to_dict
from ..models import (AgentRun, Application, ApplicationEvent, ApprovalRequest, Interview, Job, Profile, Recruiter,
                      RecruiterInteraction, Resume, ResumeVersion, SavedJob, Skill, utcnow)
from .matching import match_job

ONTOLOGY = {
    "Person": "You", "Skill": "A capability you have verified", "Role": "A position you held", "Employer": "An organisation you worked for",
    "Education": "A degree or school", "Certification": "A credential", "Job": "A posting you saved or applied to",
    "Company": "A hiring organisation", "Recruiter": "A contact in your CRM", "Application": "Your application to a job",
}

# (procedure, condition, procedure) triplets.
PROCEDURE: list[tuple[str, str, str]] = [
    ("upload_resume", "resume on file", "discover"),
    ("discover", "a job is chosen", "check_fit"),
    ("check_fit", "score < 45", "upskill"),
    ("check_fit", "required gaps", "close_gaps"),
    ("check_fit", "good fit", "tailor_resume"),
    ("close_gaps", "gaps confirmed or accepted", "tailor_resume"),
    ("upskill", "skills learned", "check_fit"),
    ("tailor_resume", "fact check passed", "ats_check"),
    ("ats_check", "coverage < 60%", "tailor_resume"),
    ("ats_check", "coverage ok", "cover_letter"),
    ("cover_letter", "letter ready", "approve_submit"),
    ("approve_submit", "you approve", "applied"),
    ("approve_submit", "you decline", "you_decide"),
    ("applied", "no reply after 5 days", "follow_up"),
    ("applied", "interview scheduled", "interview_prep"),
    ("follow_up", "still no reply after 14 days", "you_decide"),
    ("follow_up", "reply received", "interview_prep"),
    ("interview_prep", "interviews done", "offer"),
    ("offer", "offer received", "negotiate"),
    ("negotiate", "terms agreed", "you_decide"),
]
STEPS: dict[str, dict[str, str]] = {
    "upload_resume": {"label": "Upload resume", "link": "/app/resume", "kind": "action"},
    "discover": {"label": "Find a target job", "link": "/app/jobs", "kind": "action"},
    "check_fit": {"label": "Check fit", "link": "/app/matching", "kind": "check"},
    "upskill": {"label": "Upskill first", "link": "/app/learning", "kind": "action"},
    "close_gaps": {"label": "Close or confirm gaps", "link": "/app/settings", "kind": "action"},
    "tailor_resume": {"label": "Tailor resume", "link": "/app/resume", "kind": "action"},
    "ats_check": {"label": "ATS check", "link": "/app/ats", "kind": "check"},
    "cover_letter": {"label": "Cover letter", "link": "/app/cover", "kind": "action"},
    "approve_submit": {"label": "Approve submission", "link": "/app/governance", "kind": "human"},
    "applied": {"label": "Applied", "link": "/app/applications", "kind": "state"},
    "follow_up": {"label": "Follow up", "link": "/app/recruiters", "kind": "action"},
    "interview_prep": {"label": "Interview prep", "link": "/app/interview", "kind": "action"},
    "offer": {"label": "Offer", "link": "/app/applications", "kind": "state"},
    "negotiate": {"label": "Negotiate", "link": "/app/salary", "kind": "action"},
    "you_decide": {"label": "You decide", "link": "/app/governance", "kind": "human"},
}
ORDER = ["upload_resume", "discover", "check_fit", "close_gaps", "upskill", "tailor_resume", "ats_check", "cover_letter",
         "approve_submit", "applied", "follow_up", "interview_prep", "offer", "negotiate", "you_decide"]


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


class _G:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    def node(self, nid: str, label: str, type_: str, source: str, **extra: Any) -> str:
        self.nodes.setdefault(nid, {"id": nid, "label": label[:60], "type": type_, "source": source, **extra})
        return nid

    def edge(self, a: str, b: str, rel: str, **extra: Any) -> None:
        if a in self.nodes and b in self.nodes and not any(e["source"] == a and e["target"] == b and e["relation"] == rel for e in self.edges):
            self.edges.append({"source": a, "target": b, "relation": rel, **extra})

    def out(self) -> dict[str, Any]:
        return {"nodes": list(self.nodes.values()), "edges": self.edges}


def _skill_id(name: str) -> str:
    return "skill:" + name.lower()


def knowledge_graph(db: Session, user_id: uuid.UUID, max_jobs: int = 12) -> tuple[dict[str, Any], dict[str, Any]]:
    g = _G()
    prof = db.scalar(select(Profile).where(Profile.user_id == user_id))
    me = g.node("person", (prof.full_name if prof and prof.full_name else "You"), "Person", "profile")
    resume = db.scalar(select(Resume).where(Resume.user_id == user_id).order_by(Resume.is_primary.desc(), Resume.created_at.desc()))
    for s in db.scalars(select(Skill).where(Skill.user_id == user_id, Skill.verified.is_(True))):
        g.edge(me, g.node(_skill_id(s.name), s.name, "Skill", s.source), "HAS_SKILL")
    if resume:
        parsed = resume.parsed or {}
        for e in parsed.get("experience", [])[:6]:
            if e.get("employer"):
                emp = g.node("employer:" + e["employer"].lower(), e["employer"], "Employer", "resume")
                g.edge(me, emp, "WORKED_AT", detail=f"{e.get('title', '')} · {e.get('start', '')}–{e.get('end', '')}")
        for ed in parsed.get("education", [])[:3]:
            g.edge(me, g.node("edu:" + ed["institution"].lower(), ed["institution"], "Education", "resume"), "STUDIED_AT", detail=ed.get("degree"))
        for c in parsed.get("certifications", [])[:4]:
            g.edge(me, g.node("cert:" + c.lower(), c, "Certification", "resume"), "CERTIFIED")
    apps = list(db.scalars(select(Application).where(Application.user_id == user_id).order_by(Application.updated_at.desc())))
    app_by_job = {a.job_id: a for a in apps if a.job_id}
    saved_ids = [s.job_id for s in db.scalars(select(SavedJob).where(SavedJob.user_id == user_id).order_by(SavedJob.created_at.desc()))]
    job_ids = list(dict.fromkeys(saved_ids + [a.job_id for a in apps if a.job_id]))[:max_jobs]
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_(job_ids)))} if job_ids else {}
    for jid in job_ids:
        j = jobs.get(jid)
        if not j:
            continue
        jn = g.node(f"job:{j.id}", j.title, "Job", j.source, company=j.company, synthetic=j.is_synthetic)
        co = g.node("company:" + j.company.lower(), j.company, "Company", j.source)
        g.edge(jn, co, "AT_COMPANY")
        a = app_by_job.get(jid)
        g.edge(me, jn, "APPLIED_TO" if a and a.status != "draft" else "SAVED", status=a.status if a else "saved")
        for s in (j.required_skills or [])[:8]:
            g.node(_skill_id(s), s, "Skill", "job posting")
            g.edge(jn, _skill_id(s), "REQUIRES")
    for r in db.scalars(select(Recruiter).where(Recruiter.user_id == user_id).limit(15)):
        rn = g.node(f"recruiter:{r.id}", r.name, "Recruiter", "crm")
        g.edge(me, rn, "KNOWS")
        if r.company and ("company:" + r.company.lower()) in g.nodes:
            g.edge(rn, "company:" + r.company.lower(), "WORKS_AT")
    meta = {"resume": resume, "apps": apps, "app_by_job": app_by_job, "jobs": jobs, "saved_ids": saved_ids, "profile": prof}
    return g.out(), meta


def _pick_focus(meta: dict[str, Any], job_id: str | None) -> Job | None:
    jobs: dict[uuid.UUID, Job] = meta["jobs"]
    if job_id:
        try:
            return jobs.get(uuid.UUID(job_id))
        except ValueError:
            return None
    active = [a for a in meta["apps"] if a.job_id in jobs and a.status in ("draft", "applied", "screening", "interviewing", "offer")]
    if active:
        return jobs[active[0].job_id]
    for sid in meta["saved_ids"]:
        if sid in jobs:
            return jobs[sid]
    return None


def context_graph(db: Session, user_id: uuid.UUID, kg: dict[str, Any], meta: dict[str, Any], job: Job | None) -> dict[str, Any]:
    if job is None:
        return {"focus": None, "nodes": [], "edges": [], "live_state": [], "scope": {"kept": 0, "of": len(kg["nodes"])},
                "message": "Save or apply to a job to scope a context graph around it."}
    g = _G()
    me = g.node("person", "You", "Person", "profile")
    jd = to_dict(job)
    jn = g.node(f"job:{job.id}", job.title, "Job", job.source, company=job.company, synthetic=job.is_synthetic)
    co = g.node("company:" + job.company.lower(), job.company, "Company", job.source)
    g.edge(jn, co, "AT_COMPANY")
    from .context import candidate_profile

    cand = candidate_profile(db, user_id, meta["resume"])
    m = match_job(cand, jd)
    have = {s.lower() for s in cand["skills"]}
    for s in (job.required_skills or []):
        sn = g.node(_skill_id(s), s, "Skill", "job posting", state="matched" if s.lower() in have else "gap")
        g.edge(jn, sn, "REQUIRES")
        if s.lower() in have:
            g.edge(me, sn, "HAS_SKILL")
    for s in (job.preferred_skills or [])[:4]:
        sn = g.node(_skill_id(s), s, "Skill", "job posting", state="matched" if s.lower() in have else "nice_to_have")
        g.edge(jn, sn, "PREFERS")
    app: Application | None = meta["app_by_job"].get(job.id)
    live: list[dict[str, Any]] = [{"key": "match", "label": f"Match {m['score']:.0f}/100", "tone": "violet"}]
    now = utcnow()
    if job.posted_at:
        days = (now - _aware(job.posted_at)).days
        live.append({"key": "posted", "label": f"Posted {days}d ago", "tone": "emerald" if days <= 3 else "neutral"})
    live.append({"key": "salary", "label": (f"{job.salary_currency} {job.salary_min:,.0f}–{(job.salary_max or job.salary_min):,.0f}"
                                            if job.salary_verified and job.salary_min else "Salary not published"), "tone": "sky"})
    if job.work_arrangement:
        live.append({"key": "arrangement", "label": job.work_arrangement.title(), "tone": "neutral"})
    events: list[ApplicationEvent] = []
    if app:
        an = g.node(f"app:{app.id}", f"Application · {app.status}", "Application", "tracker", status=app.status)
        g.edge(me, an, "SUBMITTED" if app.status != "draft" else "DRAFTED")
        g.edge(an, jn, "FOR")
        live.append({"key": "status", "label": f"Status: {app.status}", "tone": "amber"})
        events = list(db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == app.id)))
        due = [e for e in events if e.kind == "followup_scheduled" and e.due_at and _aware(e.due_at) >= now]
        if due:
            d = min(_aware(e.due_at) for e in due)
            live.append({"key": "followup", "label": f"Follow-up in {(d - now).days}d", "tone": "coral"})
        ivs = [i for i in db.scalars(select(Interview).where(Interview.application_id == app.id)) if i.scheduled_at and _aware(i.scheduled_at) >= now]
        if ivs:
            d = min(_aware(i.scheduled_at) for i in ivs)
            live.append({"key": "interview", "label": f"Interview in {(d - now).days}d", "tone": "emerald"})
    for r in db.scalars(select(Recruiter).where(Recruiter.user_id == user_id, Recruiter.company == job.company)):
        rn = g.node(f"recruiter:{r.id}", r.name, "Recruiter", "crm")
        g.edge(rn, co, "WORKS_AT")
        g.edge(me, rn, "KNOWS")
        last = db.scalar(select(RecruiterInteraction).where(RecruiterInteraction.recruiter_id == r.id).order_by(RecruiterInteraction.occurred_at.desc()))
        if last:
            live.append({"key": "recruiter", "label": f"{r.name.split(' ')[0]}: last contact {(now - _aware(last.occurred_at)).days}d", "tone": "neutral"})
    versions = db.scalar(select(ResumeVersion.id).where(ResumeVersion.user_id == user_id, ResumeVersion.job_id == job.id))
    out = g.out()
    return {"focus": {"job_id": str(job.id), "title": job.title, "company": job.company, "synthetic": job.is_synthetic},
            **out, "live_state": live, "match": {k: m[k] for k in ("score", "grade", "missing_required", "matched_required")},
            "application_status": app.status if app else None, "has_tailored_resume": bool(versions),
            "pending_approval": bool(app and db.scalar(select(ApprovalRequest.id).where(
                ApprovalRequest.user_id == user_id, ApprovalRequest.status == "pending", ApprovalRequest.action == "submit_application"))),
            "days_since_applied": (now.date() - app.applied_at).days if app and app.applied_at else None,
            "scope": {"kept": len(out["nodes"]), "of": len(kg["nodes"])},
            "note": "Only facts relevant to this decision are retrieved; everything else in your knowledge graph is left out."}


def procedural_graph(has_resume: bool, ctx: dict[str, Any]) -> dict[str, Any]:
    """Derive the current step and the next step from the context graph (deterministic guards)."""
    done: set[str] = set()
    taken: set[tuple[str, str]] = set()
    why = ""
    if not has_resume:
        current, why = "upload_resume", "No resume on file yet, so nothing can be matched or tailored."
    elif not ctx.get("focus"):
        done.add("upload_resume")
        current, why = "discover", "There is no target job to reason about yet."
    else:
        done |= {"upload_resume", "discover"}
        taken |= {("upload_resume", "discover"), ("discover", "check_fit")}
        score = ctx["match"]["score"]
        gaps = ctx["match"]["missing_required"]
        status = ctx.get("application_status")
        if status in (None, "draft"):
            if score < 45:
                current, why = "upskill", f"Match is {score:.0f}/100 — below 45, applying now is unlikely to pay off."
                done.add("check_fit"); taken.add(("check_fit", "upskill"))
            elif gaps and not ctx.get("has_tailored_resume"):
                current, why = "close_gaps", f"Required skills not verified: {', '.join(gaps[:4])}. Confirm any you have, or accept them as gaps."
                done.add("check_fit"); taken.add(("check_fit", "close_gaps"))
            elif not ctx.get("has_tailored_resume"):
                current, why = "tailor_resume", f"Good fit ({score:.0f}/100) and no tailored resume for this job yet."
                done.add("check_fit"); taken.add(("check_fit", "tailor_resume"))
            elif ctx.get("pending_approval"):
                current, why = "approve_submit", "A submission is waiting for your approval."
                done |= {"check_fit", "tailor_resume", "ats_check", "cover_letter"}
            else:
                current, why = "ats_check", "Your tailored resume exists; check ATS coverage, then write the cover letter."
                done |= {"check_fit", "tailor_resume"}; taken |= {("check_fit", "tailor_resume"), ("tailor_resume", "ats_check")}
        else:
            done |= {"check_fit", "tailor_resume", "ats_check", "cover_letter", "approve_submit", "applied"}
            taken |= {("cover_letter", "approve_submit"), ("approve_submit", "applied")}
            dsa = ctx.get("days_since_applied")
            if status == "applied":
                if dsa is not None and dsa >= 5:
                    current, why = "follow_up", f"Applied {dsa} days ago with no reply recorded — a polite follow-up is due."
                    taken.add(("applied", "follow_up"))
                else:
                    current, why = "applied", "Applied recently — give it a few days before following up."
            elif status in ("screening", "interviewing"):
                current, why = "interview_prep", "You're in the interview loop — practise the role's topics."
                taken.add(("applied", "interview_prep"))
            elif status == "offer":
                current, why = "negotiate", "You have an offer — benchmark it against published salaries before you answer."
                done |= {"interview_prep", "offer"}; taken |= {("interview_prep", "offer"), ("offer", "negotiate")}
            else:
                current, why = "you_decide", f"This application is {status}. Record what you learned and choose the next target."
    nxt = [b for a, _, b in PROCEDURE if a == current]
    nodes = [{"id": s, **STEPS[s], "state": "current" if s == current else ("done" if s in done else ("next" if s in nxt else "todo"))} for s in ORDER]
    edges = [{"source": a, "target": b, "condition": c, "taken": (a, b) in taken} for a, c, b in PROCEDURE]
    return {"nodes": nodes, "edges": edges, "current": current,
            "guidance": {"step": STEPS[current]["label"], "why": why, "link": STEPS[current]["link"],
                         "options": [{"step": STEPS[b]["label"], "condition": c, "link": STEPS[b]["link"]} for a, c, b in PROCEDURE if a == current],
                         "deviation": "The procedure guides, it does not dictate — you can take another path. Steps marked 'human' always wait for you."}}


def trace_and_learn(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    apps = [a for a in db.scalars(select(Application).where(Application.user_id == user_id)) if a.status != "draft"]
    tailored_jobs = {v for v in db.scalars(select(ResumeVersion.job_id).where(ResumeVersion.user_id == user_id)) if v}
    followed = {e.application_id for e in db.scalars(select(ApplicationEvent).where(ApplicationEvent.user_id == user_id,
                                                                                     ApplicationEvent.kind == "followup_scheduled"))}
    responded = {"screening", "interviewing", "offer", "accepted"}

    def rate(group: list[Application]) -> float | None:
        return round(sum(a.status in responded for a in group) / len(group), 2) if group else None

    lessons = []
    for name, test in (("Tailored resume", lambda a: a.job_id in tailored_jobs), ("Scheduled follow-up", lambda a: a.id in followed)):
        yes = [a for a in apps if test(a)]
        no = [a for a in apps if not test(a)]
        if len(yes) >= 2 and len(no) >= 2:
            ry, rn = rate(yes), rate(no)
            lessons.append({"factor": name, "with": ry, "without": rn, "n_with": len(yes), "n_without": len(no),
                            "insight": f"{name}: {round(ry * 100)}% response vs {round(rn * 100)}% without (n={len(yes)}/{len(no)})."})
        else:
            lessons.append({"factor": name, "with": rate(yes), "without": rate(no), "n_with": len(yes), "n_without": len(no),
                            "insight": f"{name}: not enough history yet (need ≥2 applications with and without)."})
    runs = list(db.scalars(select(AgentRun).where(AgentRun.user_id == user_id)))
    appr = list(db.scalars(select(ApprovalRequest).where(ApprovalRequest.user_id == user_id)))
    return {"applications_considered": len(apps), "lessons": lessons,
            "traces": {"agent_runs": len(runs), "completed": sum(r.status == "completed" for r in runs),
                       "failed": sum(r.status == "failed" for r in runs),
                       "approvals_approved": sum(r.status in ("approved", "executed") for r in appr),
                       "approvals_rejected": sum(r.status == "rejected" for r in appr)},
            "contains_synthetic": any(a.is_synthetic for a in apps)}


def career_graph(db: Session, user_id: uuid.UUID, job_id: str | None = None) -> dict[str, Any]:
    kg, meta = knowledge_graph(db, user_id)
    job = _pick_focus(meta, job_id)
    ctx = context_graph(db, user_id, kg, meta, job)
    proc = procedural_graph(meta["resume"] is not None, ctx)
    learn = trace_and_learn(db, user_id)
    types = sorted({n["type"] for n in kg["nodes"]})
    return {
        "knowledge": {**kg, "counts": {t: sum(1 for n in kg["nodes"] if n["type"] == t) for t in types}},
        "context": ctx, "procedure": proc, "learn": learn,
        "spine": [
            {"layer": "Ontology", "role": "Meaning", "question": "What things are", "value": f"{len(ONTOLOGY)} types"},
            {"layer": "Knowledge Graph", "role": "Facts", "question": "What's true", "value": f"{len(kg['nodes'])} facts · {len(kg['edges'])} links"},
            {"layer": "Context Graph", "role": "Context", "question": "What matters now", "value": f"{ctx['scope']['kept']} of {ctx['scope']['of']} facts"},
            {"layer": "Procedural Graph", "role": "Procedure", "question": "What to do next", "value": proc["guidance"]["step"]},
            {"layer": "AI Agents", "role": "Action", "question": "Acting, and writing it back", "value": f"{learn['traces']['agent_runs']} traced runs"},
        ],
        "ontology": ONTOLOGY,
    }
