"""⚙️ Settings — theme, motion, appearance and session reset."""
from __future__ import annotations

import streamlit as st

from ui.components import section
from ui.session import ctx, reset_session
from ui.themes import THEMES


def render() -> None:
    settings = ctx().settings
    section("⚙️", "Settings", "Personalise your universe. Settings live in this session only.")
    before = dict(settings)
    with st.container(border=True):
        settings["theme"] = st.radio("🎨 Theme", list(THEMES), index=list(THEMES).index(settings["theme"]),
                                     format_func=lambda n: f"{THEMES[n].emoji} {n}", horizontal=True)
        settings["animation"] = st.select_slider("✨ Animation intensity", ["Off", "Gentle", "Sparkly"], value=settings["animation"])
        settings["reduced_motion"] = st.toggle("🧘 Reduced-motion mode (also honoured automatically from your OS setting)", value=settings["reduced_motion"])
        settings["show_avatar"] = st.toggle("🦄 Show Lumi avatar", value=settings["show_avatar"])
        settings["chat_style"] = st.radio("💬 Chat appearance", ["Bubbles", "Compact"], index=["Bubbles", "Compact"].index(settings["chat_style"]), horizontal=True)
        settings["typing_effect"] = st.toggle("⌨️ Typing animation in chat", value=settings["typing_effect"])
        settings["viz_style"] = st.radio("🔮 Default workflow view", ["Graph", "Timeline"], index=["Graph", "Timeline"].index(settings["viz_style"]), horizontal=True)
    if settings != before:
        st.rerun()  # re-render with the new theme / motion settings immediately
    st.caption("All five themes are tested for WCAG AA text contrast.")
    with st.container(border=True):
        st.markdown("**🧹 Demo session**")
        st.caption("Clears memories, runs, checkpoints, audit log, chat and settings for this browser session.")
        if st.button("Reset my demo session", type="primary"):
            reset_session()
            st.rerun()
