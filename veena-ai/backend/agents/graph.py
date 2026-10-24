"""LangGraph orchestration.

The graph prepares a request: route it, prepare the screen frame, retrieve
evidence and compose the prompt. Token generation is streamed by the engine
afterwards so it can be cancelled mid-answer, and the governance agent reviews
the finished answer.

Routing is deterministic. Simple text questions go supervisor -> compose
without touching vision or retrieval.

    START -> supervisor -+-> screen_prep -+-> retrieve -+-> compose -> END
                         |                |             |
                         +----------------+-------------+
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ..llm.ollama import ModelInfo
from ..llm.select import resolve_text_model, resolve_vision_model
from ..rag.service import KnowledgeBase
from ..screen.frames import decode_image, encode_png_b64, resize_max
from ..security.prompt_guard import SECURITY_PREAMBLE, detect_injection, wrap_untrusted
from ..vision.ocr import run_ocr
from ..vision.redact import redact_image
from . import prompts

Mode = Literal["conversation", "screen", "interview", "meeting"]


class UnifiedRequest(BaseModel):
    """One schema for every modality."""

    session_id: str
    text: str = Field(min_length=1, max_length=20000)
    source: Literal["typed", "speech", "screen", "system"] = "typed"
    mode: Mode = "conversation"
    answer_style: str | None = None
    intent: str | None = None
    image_b64: str | None = Field(default=None, max_length=36 * 2**20)
    screen_action: str | None = None  # explain_code | find_errors | architecture | summarize | ask
    continuous: bool = False
    collection_ids: list[str] = Field(default_factory=list, max_length=20)
    resume_collection_id: str | None = None
    job_description: str | None = Field(default=None, max_length=20000)
    transcript_context: list[str] = Field(default_factory=list, max_length=40)
    model: str | None = None


SCREEN_ACTIONS = {
    "explain_code": ("code", "code", "Explain the code visible on the screen."),
    "find_errors": ("code", "code", "Identify bugs or error messages visible on the screen and how to fix them."),
    "architecture": ("architecture", "architecture", "Explain the architecture or diagram visible on the screen."),
    "summarize": ("screen", "detailed", "Summarise the document, slide or page visible on the screen."),
    "ask": ("screen", None, None),
}


class VeenaState(TypedDict, total=False):
    request: dict[str, Any]
    agent: str
    style: str
    needs_retrieval: bool
    knowledge_requested: bool
    image_b64: str | None
    ocr_text: str
    redaction: dict[str, Any]
    sensitive: bool
    evidence: list[dict[str, Any]]
    resume_text: str
    messages: list[dict[str, Any]]
    model: str
    notes: list[str]
    timings: dict[str, float]


@dataclass
class GraphDeps:
    kb: KnowledgeBase | None
    settings: dict[str, Any]
    installed: list[ModelInfo]
    history: list[dict[str, str]] = field(default_factory=list)
    max_image_side: int = 1280


def build_graph(deps: GraphDeps):
    def supervisor(state: VeenaState) -> VeenaState:
        req = state["request"]
        intent = req.get("intent")
        agent, style = "conversation", None
        if req["mode"] == "meeting":
            agent, style = "meeting", "meeting_summary"
        elif req["mode"] == "interview":
            agent, style = "interview_coach", "interview"
        elif req.get("image_b64"):
            agent, style, _ = SCREEN_ACTIONS.get(req.get("screen_action") or "ask", SCREEN_ACTIONS["ask"])
            if agent == "screen" and intent in ("coding", "architecture"):
                agent = "code" if intent == "coding" else "architecture"
        elif intent == "coding":
            agent = "code"
        elif intent == "architecture":
            agent = "architecture"
        elif req.get("collection_ids"):
            agent = "knowledge"
        if req.get("answer_style") in prompts.STYLES:
            style = req["answer_style"]
        if style is None:
            from .question_detection import ANSWER_MODE

            style = ANSWER_MODE.get(intent or "", None) or deps.settings.get("answer_style", "quick")
        return {
            "agent": agent,
            "style": style if style in prompts.STYLES else "quick",
            "knowledge_requested": bool(req.get("collection_ids")),
            "needs_retrieval": bool(req.get("collection_ids") or req.get("resume_collection_id")),
            "notes": [],
            "timings": {},
            "evidence": [],
        }

    async def screen_prep(state: VeenaState) -> VeenaState:
        req = state["request"]
        notes = list(state.get("notes", []))
        timings = dict(state.get("timings", {}))
        img = resize_max(decode_image(req["image_b64"]), deps.max_image_side)
        t0 = time.perf_counter()
        ocr = await asyncio.to_thread(run_ocr, img)
        timings["ocr_ms"] = (time.perf_counter() - t0) * 1000
        if not ocr.available:
            notes.append("OCR unavailable (Tesseract not installed); using the image only.")
        report: dict[str, Any] = {"boxes": 0, "kinds": [], "sensitive": False}
        ocr_text = ocr.text
        if deps.settings.get("redact_screens", True):
            img, ocr_text, rep = redact_image(img, ocr)
            report = {"boxes": rep.boxes, "kinds": sorted(set(rep.kinds)), "sensitive": rep.sensitive}
            if rep.boxes:
                notes.append(f"Redacted {rep.boxes} sensitive region(s) before analysis.")
        if detect_injection(ocr_text):
            notes.append("Screen text contained instructions aimed at the assistant; they were treated as data and ignored.")
        return {
            "image_b64": encode_png_b64(img),
            "ocr_text": ocr_text[:8000],
            "redaction": report,
            "sensitive": report["sensitive"],
            "notes": notes,
            "timings": timings,
        }

    async def retrieve(state: VeenaState) -> VeenaState:
        req = state["request"]
        notes = list(state.get("notes", []))
        timings = dict(state.get("timings", {}))
        evidence: list[dict[str, Any]] = []
        resume_text = ""
        if deps.kb is not None:
            query = req["text"]
            if state.get("ocr_text"):
                query += "\n" + state["ocr_text"][:400]
            if req.get("collection_ids"):
                t0 = time.perf_counter()
                hits = await asyncio.to_thread(deps.kb.search, query, req["collection_ids"], 5)
                timings["retrieval_ms"] = (time.perf_counter() - t0) * 1000
                evidence = [h.citation() | {"text": h.text} for h in hits]
                if any(detect_injection(e["text"]) for e in evidence):
                    notes.append("A retrieved document contained instructions aimed at the assistant; they were ignored.")
            if req.get("resume_collection_id"):
                resume_text = await asyncio.to_thread(deps.kb.collection_text, req["resume_collection_id"])
        return {"evidence": evidence, "resume_text": resume_text, "notes": notes, "timings": timings}

    def compose(state: VeenaState) -> VeenaState:
        req = state["request"]
        notes = list(state.get("notes", []))
        image = state.get("image_b64")
        model: str
        if image:
            vm = resolve_vision_model(req.get("model") or deps.settings.get("vision_model"), deps.installed)
            if vm:
                model = vm
            else:
                model = resolve_text_model(req.get("model") or deps.settings.get("text_model"), deps.installed)
                notes.append("No vision-capable model is installed, so this answer uses OCR text only.")
                image = None
        else:
            model = resolve_text_model(req.get("model") or deps.settings.get("text_model"), deps.installed)

        system = "\n\n".join([prompts.BASE, prompts.AGENTS[state["agent"]], prompts.STYLES[state["style"]], SECURITY_PREAMBLE])
        blocks: list[str] = []
        if req.get("transcript_context"):
            blocks.append(wrap_untrusted("transcript", "\n".join(req["transcript_context"][-20:])))
        if state.get("ocr_text"):
            blocks.append(wrap_untrusted("screen_ocr", state["ocr_text"]))
        if state.get("evidence"):
            ev = "\n\n".join(
                f"[{e['n']}] ({e['filename']}{', p.' + str(e['page']) if e.get('page') else ''})\n{e['text']}" for e in state["evidence"]
            )
            blocks.append(wrap_untrusted("documents", ev))
        elif state.get("knowledge_requested"):
            blocks.append("No passages in the selected knowledge collections matched this question.")
        if state.get("resume_text"):
            blocks.append(wrap_untrusted("resume", state["resume_text"]))
        if req.get("job_description"):
            blocks.append(wrap_untrusted("job_description", req["job_description"][:6000]))

        question = req["text"]
        if req.get("screen_action") and req["screen_action"] != "ask":
            default_q = SCREEN_ACTIONS[req["screen_action"]][2]
            question = default_q if question.strip() in ("", default_q) else f"{default_q}\nUser question: {question}"
        user_content = ("\n\n".join(blocks) + "\n\n" if blocks else "") + f"Question: {question}"
        user_msg: dict[str, Any] = {"role": "user", "content": user_content}
        if image:
            user_msg["images"] = [image]
        return {
            "model": model,
            "messages": [{"role": "system", "content": system}, *deps.history, user_msg],
            "notes": notes,
            "image_b64": image,
        }

    def after_supervisor(state: VeenaState) -> str:
        if state["request"].get("image_b64"):
            return "screen_prep"
        return "retrieve" if state.get("needs_retrieval") else "compose"

    def after_screen(state: VeenaState) -> str:
        return "retrieve" if state.get("needs_retrieval") else "compose"

    g = StateGraph(VeenaState)
    g.add_node("supervisor", supervisor)
    g.add_node("screen_prep", screen_prep)
    g.add_node("retrieve", retrieve)
    g.add_node("compose", compose)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", after_supervisor, ["screen_prep", "retrieve", "compose"])
    g.add_conditional_edges("screen_prep", after_screen, ["retrieve", "compose"])
    g.add_edge("retrieve", "compose")
    g.add_edge("compose", END)
    return g.compile()
