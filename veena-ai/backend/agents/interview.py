"""Interview practice: question generation, answer evaluation and session review.

This is for rehearsal. It is not designed or offered as covert help during
real assessments that prohibit AI assistance.
"""

from __future__ import annotations

import json
import re
import statistics
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import col, select

from ..llm.ollama import OllamaClient
from ..memory.db import session as db_session
from ..memory.tables import InterviewSession, InterviewTurn
from ..security.prompt_guard import SECURITY_PREAMBLE, wrap_untrusted

ROLES = {
    "senior_ai_engineer": "Senior AI Engineer",
    "principal_ai_engineer": "Principal AI Engineer",
    "ai_architect": "AI Architect",
    "forward_deployed_ai_engineer": "Forward Deployed AI Engineer",
    "data_scientist": "Data Scientist",
    "ml_engineer": "Machine Learning Engineer",
    "software_engineer": "Software Engineer",
    "solutions_architect": "Solutions Architect",
}
CATEGORIES = ("behavioral", "coding", "architecture", "leadership", "technical")

# A small curated bank, used when no model is available or as seed questions.
QUESTION_BANK: dict[str, list[str]] = {
    "behavioral": [
        "Tell me about a time you disagreed with a technical decision. What did you do?",
        "Describe a project that failed or slipped. What did you learn?",
        "Tell me about a time you had to deliver with incomplete requirements.",
    ],
    "coding": [
        "Write a function that returns the k most frequent elements in a list. What is its complexity?",
        "How would you detect a cycle in a linked list? Walk through the code.",
        "Implement an LRU cache. Which data structures do you use and why?",
    ],
    "architecture": [
        "Design a retrieval-augmented generation system for 10 million internal documents.",
        "How would you serve an LLM-backed feature with a p95 latency budget of two seconds?",
        "Design a real-time transcription pipeline for meetings. Where are the bottlenecks?",
    ],
    "leadership": [
        "How do you decide what your team should not build?",
        "Tell me about a time you grew someone on your team.",
        "How do you handle a stakeholder pushing an unrealistic deadline?",
    ],
    "technical": [
        "How do you evaluate an LLM application before shipping it?",
        "Explain the bias-variance tradeoff with a practical example.",
        "What causes hallucination in RAG systems and how do you reduce it?",
    ],
}

GEN_PROMPT = (
    "You are a mock interviewer preparing PRACTICE questions for the role {role}. Focus: {focus}. "
    "Use the resume and job description only to tailor topics; do not assume facts not present. "
    'Return JSON only: {{"questions": [{{"category": one of {cats}, "question": string}}]}} with exactly {n} questions.'
)

EVAL_PROMPT = (
    "You are an interview coach scoring a PRACTICE answer for the role {role}. Score 0-10 against: "
    "relevance, structure (STAR for behavioural), technical correctness, specificity, and communication. "
    "Base specific claims only on the answer and resume. Return JSON only: "
    '{{"score": number, "strengths": [string], "improvements": [string], '
    '"model_answer_outline": [string], "follow_up_question": string}}'
)


def _as_list(value: Any) -> list[str]:
    """Small models sometimes return a string where the schema asks for a list.
    Iterating that string would yield single characters, so split it into items."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"\n+|(?<=[.;])\s+(?=[A-Z0-9])", value)
        return [p.strip(" -•*\t") for p in parts if p.strip(" -•*\t")]
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value)]


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model did not return JSON")
    return json.loads(raw[start : end + 1])


class InterviewCoach:
    def __init__(self, engine: Engine, llm: OllamaClient):
        self.engine = engine
        self.llm = llm

    def create(self, chat_session_id: str, role: str, focus: str, resume_collection_id: str | None, jd: str | None) -> InterviewSession:
        if role not in ROLES:
            raise ValueError(f"role must be one of {list(ROLES)}")
        if focus not in (*CATEGORIES, "mixed"):
            raise ValueError("invalid focus")
        with db_session(self.engine) as s:
            iv = InterviewSession(
                chat_session_id=chat_session_id,
                role=role,
                focus=focus,
                resume_collection_id=resume_collection_id,
                job_description=(jd or "")[:20000] or None,
            )
            s.add(iv)
            s.commit()
            s.refresh(iv)
            return iv

    def get(self, interview_id: str) -> InterviewSession | None:
        with db_session(self.engine) as s:
            return s.get(InterviewSession, interview_id)

    def turns(self, interview_id: str) -> list[InterviewTurn]:
        with db_session(self.engine) as s:
            return list(
                s.exec(select(InterviewTurn).where(InterviewTurn.interview_id == interview_id).order_by(col(InterviewTurn.ordinal)))
            )

    async def generate_questions(self, iv: InterviewSession, model: str | None, resume_text: str, n: int = 5) -> dict[str, Any]:
        source = "bank"
        questions: list[dict[str, str]] = []
        if model:
            focus = "a mix of behavioral, coding, architecture and leadership" if iv.focus == "mixed" else iv.focus
            ctx = []
            if resume_text:
                ctx.append(wrap_untrusted("resume", resume_text[:4000]))
            if iv.job_description:
                ctx.append(wrap_untrusted("job_description", iv.job_description[:4000]))
            try:
                raw = await self.llm.chat(
                    model,
                    [
                        {
                            "role": "system",
                            "content": GEN_PROMPT.format(role=ROLES[iv.role], focus=focus, cats=list(CATEGORIES), n=n)
                            + "\n\n"
                            + SECURITY_PREAMBLE,
                        },
                        {"role": "user", "content": "\n\n".join(ctx) or "No resume or job description provided."},
                    ],
                    fmt="json",
                    options={"temperature": 0.6, "num_predict": 700},
                )
                for q in _parse_json(raw).get("questions", [])[:n]:
                    if isinstance(q, dict) and str(q.get("question", "")).strip():
                        cat = q.get("category") if q.get("category") in CATEGORIES else "technical"
                        questions.append({"category": cat, "question": str(q["question"]).strip()[:600]})
                source = "model"
            except Exception:  # noqa: BLE001 - fall back to the bank
                questions = []
        if not questions:
            cats = list(CATEGORIES) if iv.focus == "mixed" else [iv.focus]
            for i in range(n):
                cat = cats[i % len(cats)]
                bank = QUESTION_BANK[cat]
                questions.append({"category": cat, "question": bank[(i // len(cats)) % len(bank)]})
            source = "bank"
        existing = len(self.turns(iv.id))
        with db_session(self.engine) as s:
            rows = [
                InterviewTurn(interview_id=iv.id, ordinal=existing + i, category=q["category"], question=q["question"])
                for i, q in enumerate(questions)
            ]
            s.add_all(rows)
            s.commit()
            for r in rows:
                s.refresh(r)
        return {"source": source, "turns": [r.model_dump(mode="json") for r in rows]}

    async def evaluate(self, turn_id: int, answer: str, model: str, resume_text: str) -> dict[str, Any]:
        with db_session(self.engine) as s:
            turn = s.get(InterviewTurn, turn_id)
            if not turn:
                raise LookupError("turn not found")
            iv = s.get(InterviewSession, turn.interview_id)
        ctx = [f"Question ({turn.category}): {turn.question}", wrap_untrusted("candidate_answer", answer[:8000])]
        if resume_text:
            ctx.append(wrap_untrusted("resume", resume_text[:4000]))
        raw = await self.llm.chat(
            model,
            [
                {"role": "system", "content": EVAL_PROMPT.format(role=ROLES[iv.role]) + "\n\n" + SECURITY_PREAMBLE},
                {"role": "user", "content": "\n\n".join(ctx)},
            ],
            fmt="json",
            options={"temperature": 0.2, "num_predict": 600},
        )
        fb = _parse_json(raw)
        try:
            score = max(0.0, min(10.0, float(fb.get("score", 0))))
        except (TypeError, ValueError):
            score = 0.0
        feedback = {
            "score": score,
            "strengths": _as_list(fb.get("strengths"))[:6],
            "improvements": _as_list(fb.get("improvements"))[:6],
            "model_answer_outline": _as_list(fb.get("model_answer_outline"))[:8],
            "follow_up_question": str(fb.get("follow_up_question", ""))[:400],
            "model": model,
        }
        with db_session(self.engine) as s:
            turn = s.get(InterviewTurn, turn_id)
            turn.answer = answer[:8000]
            turn.score = score
            turn.feedback_json = json.dumps(feedback)
            s.add(turn)
            s.commit()
        return feedback

    def review(self, interview_id: str) -> dict[str, Any]:
        turns = self.turns(interview_id)
        scored = [t for t in turns if t.score is not None]
        by_cat: dict[str, list[float]] = {}
        for t in scored:
            by_cat.setdefault(t.category, []).append(t.score)
        improvements: list[str] = []
        for t in scored:
            improvements += json.loads(t.feedback_json or "{}").get("improvements", [])[:2]
        return {
            "answered": len(scored),
            "total": len(turns),
            "average_score": statistics.fmean([t.score for t in scored]) if scored else None,
            "by_category": {k: statistics.fmean(v) for k, v in by_cat.items()},
            "top_improvements": improvements[:6],
            "turns": [
                {
                    **t.model_dump(mode="json", exclude={"feedback_json"}),
                    "feedback": json.loads(t.feedback_json) if t.feedback_json else None,
                }
                for t in turns
            ],
        }

    def all_scores(self) -> list[dict[str, Any]]:
        with db_session(self.engine) as s:
            rows = list(
                s.exec(
                    select(InterviewTurn, InterviewSession).where(
                        InterviewTurn.interview_id == InterviewSession.id, col(InterviewTurn.score).is_not(None)
                    )
                )
            )
        return [{"role": iv.role, "category": t.category, "score": t.score, "at": t.created_at.isoformat()} for t, iv in rows]
