"""🏠 Dream Dashboard."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from services import metrics
from ui.components import html, kpi, lumi, render_artifacts, render_run
from ui.session import ctx, go

QUICK_ACTIONS = [
    ("💌", "Draft an email", "Rosie writes, you approve, we simulate the send.", "email", {}),
    ("🔎", "Research a topic", "Aurora assembles a synthetic research brief.", "research", {}),
    ("📅", "Plan my week", "Iris, Celeste & Nova time-block your week.", "chat", {"chat_prefill": "Help me plan a productive week."}),
    ("📚", "Analyze a document", "Athena extracts fields & evidence.", "documents", {}),
    ("🧠", "Remember something", "Plant a harmless memory in your garden.", "memory", {}),
    ("🤖", "Launch an agent team", "Watch conditional multi-agent routing.", "chat", {"chat_prefill": "Launch my AI dream team."}),
    ("✨", "Build a workflow", "Turn a goal into a dependency-aware plan.", "planner", {}),
]


def _greeting() -> str:
    hour = datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"


def render() -> None:
    session = ctx()
    engine = session.engine
    show_avatar = session.settings["show_avatar"]
    html(
        f'<div class="mf-card mf-hero">{lumi() if show_avatar else ""}<div>'
        f"<h1>{_greeting()}, Dreamer! 🦄✨</h1><h3>Your magical AI universe is ready.</h3>"
        '<p class="mf-quote">“Big dreams deserve brilliant little helpers.”</p>'
        '<p style="margin-top:.5rem">Twelve deterministic agent roles, orchestrated by a real LangGraph state graph — '
        "with human approval before anything consequential (all simulated).</p></div></div>"
    )
    st.button("✨ Start the Magic", type="primary", on_click=go, args=("chat",), kwargs={"chat_prefill": "Launch my AI dream team."})

    m = metrics.measured(engine)
    est = metrics.illustrative(engine)
    st.subheader("🌟 Your session at a glance")
    row1 = st.columns(4)
    with row1[0]:
        kpi("Active agents", f"{m['active_agents']} / 12", "roles invoked this session")
    with row1[1]:
        kpi("Completed tasks", m["completed"], "workflows completed")
    with row1[2]:
        kpi("Workflows executed", m["total_runs"], "graph runs started")
    with row1[3]:
        kpi("Pending approvals", m["pending_approvals"], "waiting for you")
    row2 = st.columns(3)
    with row2[0]:
        kpi("Memory entries", m["memory_entries"], "session-only memories")
    with row2[1]:
        kpi("Simulated time saved", f"{est['minutes_saved']} min", "per-scenario guesses", kind="illustrative")
    with row2[2]:
        kpi("Demo credits saved", f"${est['cost_avoidance_usd']:.4f}", f"~{est['token_equivalents']:,} token-equivalents", kind="illustrative")
    st.caption("Measured values come from this session's execution events. Illustrative estimates use stated assumptions "
               "(see Magic Analytics); actual LLM tokens and API cost are always **0**.")

    st.subheader("🪄 Quick magic")
    cols = st.columns(4)
    for index, (emoji, title, blurb, page, preset) in enumerate(QUICK_ACTIONS):
        with cols[index % 4]:
            with st.container(border=True):
                st.markdown(f"### {emoji}\n**{title}**")
                st.caption(blurb)
                st.button("Open", key=f"qa_{index}", on_click=go, args=(page,), kwargs=preset, width="stretch")

    latest = engine.latest()
    if latest:
        st.subheader("🔮 Latest workflow")
        render_run(latest, key="dash")
        render_artifacts(latest)
    else:
        st.info("🦄 No workflows yet — tap a quick-magic card or say hi to Lumi in the chat.")
