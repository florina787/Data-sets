"""🦄 MuseFlow AI — Your Magical AI Universe.

Public demo: every AI behaviour, integration and real-world action is SIMULATED.
No API keys, no paid LLM calls, no external accounts.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="MuseFlow AI 🦄", page_icon="🦄", layout="wide", initial_sidebar_state="auto")

from services.achievements import all_achievements, evaluate, session_stats  # noqa: E402
from ui.components import celebrate, html, inject_theme  # noqa: E402
from ui.session import ctx, show_flashes  # noqa: E402
from ui.sidebar import render_sidebar  # noqa: E402

# Page modules are imported lazily so heavy pages (Plotly, pandas) load only when visited.
PAGE_MODULES = {
    "dashboard": "ui.dashboard", "chat": "ui.chat", "memory": "ui.views.memory", "agents": "ui.views.agents",
    "planner": "ui.views.planner", "research": "ui.views.research", "email": "ui.views.email",
    "calendar": "ui.views.calendar_view", "documents": "ui.views.documents", "browser": "ui.views.browser",
    "galaxy": "ui.views.galaxy", "approvals": "ui.views.approvals", "analytics": "ui.views.analytics",
    "governance": "ui.views.governance", "achievements": "ui.views.achievements", "settings": "ui.views.settings",
}

DISCLOSURE = (
    "MuseFlow AI is an independent educational demonstration of agentic AI orchestration. It is not affiliated with Meta. "
    "All AI reasoning, external integrations, and real-world actions are simulated in the public version."
)


def _achievement_check() -> None:
    session = ctx()
    unlocked = evaluate(session_stats(session.engine, len(session.pages_visited)))
    fresh = [a for a in all_achievements() if unlocked[a.key] and a.key not in session.celebrated]
    for ach in fresh:
        session.celebrated.add(ach.key)
        st.toast(f"Achievement unlocked: {ach.title}", icon=ach.emoji)
    if fresh:
        celebrate()


def main() -> None:
    inject_theme()
    page = render_sidebar()
    show_flashes()
    module = importlib.import_module(PAGE_MODULES.get(page, "ui.dashboard"))
    module.render()
    _achievement_check()
    st.divider()
    html(f'<p style="font-size:.8rem;color:var(--mf-muted);text-align:center">🦄 {DISCLOSURE}</p>')


main()
