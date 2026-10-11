"""💬 Lumi AI Chat — a deterministic, intent-based conversational engine (no LLM)."""
from __future__ import annotations

import time
from typing import Any, Iterator

import streamlit as st

from services import scenario_loader as fixtures
from services.validation import MAX_REQUEST_CHARS, ValidationError, clean_text
from ui.components import html, render_artifacts, render_run, section, start_run
from ui.session import PAGE_LABELS, ctx, go
from workflows.routing import classify_intent

SUGGESTIONS = [
    "Help me plan a productive week.",
    "Draft a professional follow-up email.",
    "Compare LangGraph and CrewAI.",
    "Prepare me for a technical interview.",
    "Remember that I prefer deep-work blocks in the morning.",
    "Launch my AI dream team.",
    "Plan a relaxing weekend getaway.",
    "Analyze the sample insurance policy.",
    "What's the status of my workflows?",
]

TEAM_INTRO = {
    "interview_prep": "your interview-prep team", "email_followup": "Rosie, our email artisan",
    "weekly_planning": "your planning team", "research": "Aurora's research circle", "document_analysis": "Athena's document crew",
    "travel_planning": "your travel fairies", "browser": "Wren, our browser navigator", "personal_memory": "Iris, keeper of memories",
    "memory_recall": "Iris, keeper of memories", "project_planning": "Nova's planning studio", "dream_team": "your AI dream team",
    "schedule_meeting": "Celeste, our timekeeper", "document_edit": "Athena's document crew",
}


def _status_text() -> str:
    engine = ctx().engine
    runs = engine.history()
    if not runs:
        return "No workflows have run yet in this session. Try one of the suggestions below! ✨"
    lines = [f"You've run **{len(runs)}** workflow(s) this session."]
    pending = engine.pending()
    if pending:
        lines.append(f"💖 **{len(pending)}** waiting for approval: " + ", ".join(f"{r.title} ({r.run_id})" for r in pending))
    for run in runs[:5]:
        lines.append(f"- {run.emoji} {run.title} — `{run.status}` ({run.run_id})")
    return "\n".join(lines)


def respond_to(text: str) -> dict[str, Any]:
    """Handle one user message; returns the assistant message to store."""
    match = classify_intent(text)
    if match.intent == "greeting":
        return {"content": "Hello, Dreamer! 🦄✨ I'm Lumi. I can draft emails, plan your week, research topics, analyze documents, "
                           "remember preferences and launch a whole agent team — all in a safe simulation. What shall we create?"}
    if match.intent == "help":
        return {"content": "Here's what I can do (deterministic demo — I match a fixed set of intents):\n\n"
                           + "\n".join(f"- {s.emoji} **{s.title}** — try “{s.prompt}”" for s in fixtures.list_scenarios(showcase_only=True))
                           + "\n- 📍 **Navigation** — “open the memory garden”\n- 📊 **Status** — “what's pending?”"}
    if match.intent == "navigation":
        return {"content": f"Opening **{PAGE_LABELS[match.page]}** for you. 🧭", "nav": match.page}
    if match.intent == "workflow_status":
        return {"content": _status_text()}
    if match.intent == "unsupported" or not match.scenario_id:
        return {"content": "I'm a deterministic demo, so I only understand a defined set of requests — I won't pretend to reason "
                           "about anything else. 💜 Try: “plan my week”, “draft a follow-up email”, “compare LangGraph and CrewAI”, "
                           "“remember that I love tea”, or “launch my AI dream team”. Type **help** for the full list."}
    run = start_run(None, None, request=text)
    if run is None:
        return {"content": "Hmm, that request didn't pass validation — please try a gentler example. 💜"}
    intro = f"Of course! ✨ I'll assemble {TEAM_INTRO.get(match.scenario_id, 'the team')}."
    return {"content": intro, "run_id": run.run_id}


def _stream(text: str) -> Iterator[str]:
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def _activation_list(run: Any) -> str:
    lines = []
    for index, event in enumerate(run.agent_events, start=1):
        agent = fixtures.get_agent(event["agent"])
        verb = {"intent_router": "routed your request", "respond": "composed the final response",
                "simulate_action": "executed the approved action (simulated)"}.get(event["node"], "activated")
        status = "" if event["status"] == "completed" else f" — {event['status']}"
        lines.append(f"{index}. {agent.emoji} **{agent.role}** {verb}{status}")
    return "\n".join(lines)


def _render_message(message: dict[str, Any], index: int) -> None:
    session = ctx()
    avatar = "🦄" if session.settings["show_avatar"] else None
    if message["role"] == "user":
        with st.chat_message("user", avatar="🌸" if session.settings["show_avatar"] else None):
            st.markdown(message["content"])
        return
    with st.chat_message("assistant", avatar=avatar):
        if message.get("fresh") and session.settings["typing_effect"] and not session.settings["reduced_motion"]:
            st.write_stream(_stream(message["content"]))
            message["fresh"] = False
        else:
            st.markdown(message["content"])
        if message.get("nav"):
            st.button(f"Go to {PAGE_LABELS[message['nav']]}", key=f"nav_{index}", on_click=go, args=(message["nav"],))
        run = session.engine.runs.get(message.get("run_id", ""))
        if run is not None:
            st.markdown(_activation_list(run))
            render_run(run, key=f"chat{index}")
            render_artifacts(run)


def _send(text: str) -> None:
    session = ctx()
    try:
        text = clean_text(text, max_chars=MAX_REQUEST_CHARS, field="Message")
    except ValidationError as exc:
        st.error(str(exc))
        return
    session.chat.append({"role": "user", "content": text})
    reply = respond_to(text)
    session.chat.append({"role": "assistant", "fresh": True, **reply})


def render() -> None:
    session = ctx()
    section("💬", "Lumi AI Chat", "Deterministic intent engine + real LangGraph orchestration. No LLM calls — supported intents only.")
    if session.settings["chat_style"] == "Compact":
        html('<style>.stApp [data-testid="stChatMessage"]{padding:.3rem .6rem;border-radius:12px}</style>')

    prefill = st.session_state.pop("chat_prefill", None)
    if prefill:
        _send(prefill)

    if not session.chat:
        with st.chat_message("assistant", avatar="🦄" if session.settings["show_avatar"] else None):
            st.markdown("Hi Dreamer! I'm **Lumi** 🦄 — your magical (and fully simulated) AI conductor. Pick a suggestion or type a request.")

    for index, message in enumerate(session.chat):
        _render_message(message, index)

    st.caption("✨ Suggested prompts")
    cols = st.columns(3)
    for index, suggestion in enumerate(SUGGESTIONS):
        cols[index % 3].button(suggestion, key=f"sugg_{index}", on_click=go, args=("chat",),
                               kwargs={"chat_prefill": suggestion}, width="stretch")
    typed = st.chat_input("Ask Lumi… (e.g. “Help me plan a productive week.”)", max_chars=MAX_REQUEST_CHARS)
    if typed:
        _send(typed)
        st.rerun()
    if session.chat:
        st.button("🧹 Clear conversation", on_click=session.chat.clear)
