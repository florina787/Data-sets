"""Streamlit glue for the per-visitor ``SessionContext``."""
from __future__ import annotations

from typing import Any

import streamlit as st

from services.session import SessionContext, new_session

_KEY = "_museflow_ctx"

PAGES: list[tuple[str, str]] = [
    ("dashboard", "🏠 Dream Dashboard"),
    ("chat", "💬 Lumi AI Chat"),
    ("memory", "🧠 Memory Garden"),
    ("agents", "🤖 Agent Universe"),
    ("planner", "✨ Magic Task Planner"),
    ("research", "🔎 Research Studio"),
    ("email", "💌 Email Boutique"),
    ("calendar", "📅 Celestial Calendar"),
    ("documents", "📚 Document Wonderland"),
    ("browser", "🌐 Browser Magic"),
    ("galaxy", "🔮 Workflow Galaxy"),
    ("approvals", "💖 Human Approval Center"),
    ("analytics", "📊 Magic Analytics"),
    ("governance", "🛡️ Trust & Governance"),
    ("achievements", "🏆 Achievement Garden"),
    ("settings", "⚙️ Settings"),
]
PAGE_LABELS = dict(PAGES)


def ctx() -> SessionContext:
    """The visitor's context lives only in ``st.session_state`` — never in a shared cache."""
    if _KEY not in st.session_state:
        st.session_state[_KEY] = new_session()
    return st.session_state[_KEY]


def reset_session() -> None:
    st.session_state.clear()


def go(page: str, **preset: Any) -> None:
    """Navigation callback (safe to use as on_click)."""
    st.session_state["nav"] = page
    for key, value in preset.items():
        st.session_state[key] = value


def flash(message: str, icon: str = "✨") -> None:
    st.session_state.setdefault("_flash", []).append((message, icon))


def show_flashes() -> None:
    for message, icon in st.session_state.pop("_flash", []):
        st.toast(message, icon=icon)
