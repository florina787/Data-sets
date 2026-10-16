"""Dr. Christina - conversational front door to the patient workflow.

Christina is a virtual AI assistant, NOT a licensed physician. The conversation
state machine is deterministic; an optional LLM only rephrases replies from
structured, redacted facts. Raw chat messages are kept in memory for the session
(bounded, expiring) and are never written to the database.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.copilot import llm
from app.governance import approvals
from app.harness.core import new_id
from app.rag.pipeline import get_index
from app.schemas.domain import IMAGING, LAB, SERVICE_LABELS, RequisitionStatus, ServiceType
from app.security.guards import detect_injection
from app.security.safety import screen
from app.services import workflows
from app.services.copilot_nlu import extract
from app.services.gazetteer import resolve_location

DISCLAIMER = "Christina is a virtual AI assistant, not a licensed physician."
GREETING = ("Welcome to MedAccess AI. I'm Christina, your virtual healthcare access assistant. I can help you "
            "explore healthcare facilities and potentially earlier appointment options. What service are you "
            "looking for today?")
SESSION_TTL_S = 30 * 60
MAX_TURNS = 30


class ChatSession(BaseModel):
    id: str
    user_id: str | None
    role: str
    slots: dict = Field(default_factory=dict)
    asked_requisition: bool = False
    history: list[dict] = Field(default_factory=list)
    last_workflow_id: str | None = None
    pending: dict | None = None
    touched: float = Field(default_factory=time.time)


class ChatReply(BaseModel):
    session_id: str
    reply: str
    avatar_state: str  # greeting|idle|thinking|speaking|pointing|celebrating|explaining|warning
    quick_replies: list[str] = []
    workflow: dict | None = None
    citations: list[dict] = []
    warnings: list[str] = []
    safety: dict | None = None
    mode: str = "deterministic"
    disclaimer: str = DISCLAIMER


_sessions: dict[str, ChatSession] = {}
_lock = threading.Lock()


def _session(session_id: str | None, user_id: str | None, role: str) -> ChatSession:
    now = time.time()
    with _lock:
        for k in [k for k, v in _sessions.items() if now - v.touched > SESSION_TTL_S]:
            del _sessions[k]
        s = _sessions.get(session_id or "")
        if s is None or s.user_id != user_id:
            s = ChatSession(id=new_id("CHAT"), user_id=user_id, role=role)
            _sessions[s.id] = s
        s.touched = now
        return s


def end_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def _needs_requisition(svc: str) -> bool:
    try:
        sv = ServiceType(svc)
    except ValueError:
        return False
    return sv in IMAGING or sv in LAB or sv == ServiceType.SPECIALIST


def _say(sess: ChatSession, reply: ChatReply, facts: dict | None = None) -> ChatReply:
    if facts and llm.available():
        try:
            r = llm.complete("rephrase_reply", {"draft_reply": reply.reply, **facts}, sess.history,
                             sess.last_workflow_id)
            if r and r.text and not re.search(r"\b(booked|confirmed your|diagnos)", r.text, re.I):
                reply.reply, reply.mode = r.text.strip(), "llm"
        except Exception:  # noqa: BLE001 - LLM issues fall back to the deterministic reply
            reply.mode = "deterministic (llm unavailable)"
    sess.history.append({"role": "assistant", "content": reply.reply})
    sess.history = sess.history[-MAX_TURNS:]
    return reply


def greet(session_id: str | None, user_id: str | None, role: str) -> ChatReply:
    sess = _session(session_id, user_id, role)
    return _say(sess, ChatReply(session_id=sess.id, reply=GREETING, avatar_state="greeting",
                                quick_replies=["I need an MRI", "Blood test near me", "CT scan", "Specialist"]))


def _summarize_results(sess: ChatSession, wf: dict) -> ChatReply:
    status = wf["workflow_status"]
    if status == "SAFETY_INTERRUPTED":
        return ChatReply(session_id=sess.id, reply=wf.get("explanation") or "", avatar_state="warning",
                         workflow=wf, safety=wf.get("safety"))
    if status == "AWAITING_PATIENT_DECISION" and wf.get("pending_question"):
        opts = wf["pending_question"]["options"]
        sess.pending = {"type": "expansion", "workflow_id": wf["workflow_id"],
                        "approval_id": wf["pending_question"]["approval_id"], "options": opts}
        o = ", ".join(f"{x['radius_km']} km ({x['facilities_offering_service']} facilities)" for x in opts)
        return ChatReply(session_id=sess.id, avatar_state="explaining", workflow=wf,
                         reply=f"{wf.get('explanation')} Would you like me to search a wider area? Options: {o}.",
                         quick_replies=[f"Yes, {x['radius_km']} km" for x in opts] + ["No thanks"])
    if status in {"FAILED", "HALTED"}:
        return ChatReply(session_id=sess.id, avatar_state="warning", workflow=wf,
                         reply="Something went wrong while searching, and I stopped safely. Nothing was booked "
                               "or shared. Please try again in a moment.")
    recs = wf.get("recommendations", [])
    warnings = []
    if wf.get("unavailable_sources"):
        warnings.append("One availability source was unreachable; affected facilities show contact details only.")
    if wf.get("notice"):
        warnings.append(wf["notice"])
    confirmed = any(r["tier"] == "CONFIRMED_ALTERNATIVE" for r in recs)
    return ChatReply(session_id=sess.id, reply=wf.get("explanation") or "Search complete.",
                     avatar_state="celebrating" if confirmed else "pointing", workflow=wf, warnings=warnings,
                     quick_replies=["What does 'unverified' mean?", "Search a wider area", "Start over"])


def handle(message: str, session_id: str | None, user_id: str | None, role: str, scenario: str | None = None,
           now: datetime | None = None) -> ChatReply:
    sess = _session(session_id, user_id, role)
    text = (message or "").strip()[:1000]
    sess.history.append({"role": "user", "content": text})

    # 1. Safety first - never delayed by anything else.
    safety = screen(text)
    if safety.interrupt:
        sess.slots.clear()
        sess.pending = None
        return _say(sess, ChatReply(session_id=sess.id, reply=safety.message or "", avatar_state="warning",
                                    safety=safety.model_dump(),
                                    quick_replies=["I'm safe - continue my appointment search"]))
    warnings = [safety.message] if safety.message else []
    if detect_injection(text).suspicious:
        warnings.append("Your message contained instructions I can't follow; I treat messages as information only. "
                        "Bookings and data sharing always require your explicit approval.")

    low = text.lower()
    if re.fullmatch(r"\s*(start over|reset|new search)\s*", low):
        sess.slots.clear()
        sess.pending = None
        sess.asked_requisition = False
        return _say(sess, ChatReply(session_id=sess.id, reply="Okay, let's start fresh. What service do you need?",
                                    avatar_state="idle"))

    # 2. Pending radius-expansion decision.
    if sess.pending and sess.pending["type"] == "expansion":
        m = re.search(r"(\d{1,3})\s*km", low)
        if re.search(r"\b(no|not now|no thanks|cancel)\b", low):
            radius, decision = None, "REJECTED"
        elif m or re.search(r"\b(yes|sure|ok|okay|expand|wider)\b", low):
            radius = int(m.group(1)) if m else sess.pending["options"][0]["radius_km"]
            decision = "APPROVED"
        else:
            radius = decision = None
        if decision:
            p = sess.pending
            sess.pending = None
            approvals.decide(p["approval_id"], decision, user_id or "", role, note=f"radius={radius}")
            wf = workflows.resume(p["workflow_id"], {"decision": decision, "radius_km": radius,
                                                    "approval_id": p["approval_id"]}, user_id, role)
            if radius:
                sess.slots["radius_km"] = radius
            return _say(sess, _summarize_results(sess, wf), {"status": wf["workflow_status"]})

    # 3. Administrative questions -> RAG with citations.
    ex = extract(text, (now or datetime.now(UTC)).astimezone(ZoneInfo("America/Toronto")).date())
    if ex.is_question or re.search(r"\b(what does|what is|mean|requisition needed|do i need|cover|ohip|prepare|"
                                    r"cancel)\b", low) and not (ex.service and ex.location):
        ans = get_index().answer(text, sess.slots.get("service"))
        if ans.answered:
            r = ChatReply(session_id=sess.id, reply=ans.answer or "", avatar_state="explaining",
                          citations=[c.model_dump() for c in ans.citations], warnings=warnings + ans.warnings)
        else:
            r = ChatReply(session_id=sess.id, reply=ans.refusal_reason or "", avatar_state="idle", warnings=warnings)
        return _say(sess, r)

    if ex.greeting and not sess.slots:
        return greet(sess.id, user_id, role)

    # 4. Slot filling.
    if ex.service:
        sess.slots["service"] = ex.service.value
    if ex.location:
        sess.slots["location"] = ex.location
    if ex.radius_km:
        sess.slots["radius_km"] = ex.radius_km
    if ex.requisition_status:
        sess.slots["requisition_status"] = ex.requisition_status.value
    if ex.existing_appointment_days is not None:
        sess.slots["existing_appointment_days"] = ex.existing_appointment_days
        sess.slots["existing_appointment_date"] = ex.existing_appointment_date
    if re.search(r"wider|expand", low) and sess.slots.get("radius_km"):
        bigger = [r for r in (2, 3, 5, 10, 25, 50, 100) if r > sess.slots["radius_km"]]
        if bigger:
            sess.slots["radius_km"] = bigger[0]

    svc = sess.slots.get("service")
    if not svc:
        return _say(sess, ChatReply(session_id=sess.id, avatar_state="speaking", warnings=warnings,
                                    reply="Which service are you looking for? For example MRI, CT scan, ultrasound, "
                                          "X-ray, blood test or a specialist consultation.",
                                    quick_replies=["MRI", "CT scan", "Ultrasound", "Blood test"]))
    label = SERVICE_LABELS[ServiceType(svc)]
    if _needs_requisition(svc) and "requisition_status" not in sess.slots and not sess.asked_requisition:
        sess.asked_requisition = True
        where = "" if sess.slots.get("location") else " and which city or postal code would you like me to search around"
        return _say(sess, ChatReply(session_id=sess.id, avatar_state="speaking", warnings=warnings,
                                    reply=f"I can help you look for {label} options. Do you have a physician's "
                                          f"requisition{where}?",
                                    quick_replies=["Yes, I have a requisition", "No requisition yet"]))
    loc = sess.slots.get("location")
    if not loc or resolve_location(loc) is None:
        sess.slots.pop("location", None)
        return _say(sess, ChatReply(session_id=sess.id, avatar_state="speaking", warnings=warnings,
                                    reply="Which city or postal code should I search around? (For example "
                                          "'Toronto', 'Mississauga' or 'M5V'.)",
                                    quick_replies=["Toronto", "North York", "Mississauga", "Markham"]))

    params = workflows.SearchParams(
        service=svc, location=loc, radius_km=sess.slots.get("radius_km", 25),
        existing_appointment_days=sess.slots.get("existing_appointment_days"),
        existing_appointment_date=sess.slots.get("existing_appointment_date"),
        requisition_status=RequisitionStatus(sess.slots.get("requisition_status", "UNKNOWN")), scenario=scenario)
    wf = workflows.start_search(params, user_id, role, free_text=text, now=now)
    sess.last_workflow_id = wf["workflow_id"]
    r = _summarize_results(sess, wf)
    r.warnings = warnings + r.warnings
    return _say(sess, r, {"status": wf["workflow_status"], "summary": wf.get("wait_summary"),
                          "synthetic": wf.get("data_mode") == "SYNTHETIC"})
