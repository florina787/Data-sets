"""🏆 Achievement Garden — earned from real demo-session interactions."""
from __future__ import annotations

import streamlit as st

from services.achievements import all_achievements, evaluate, session_stats
from ui.components import e, html, section
from ui.session import ctx


def render() -> None:
    session = ctx()
    section("🏆", "Achievement Garden", "Badges bloom from what you actually do in this session. No streaks, no nagging.")
    stats = session_stats(session.engine, len(session.pages_visited))
    unlocked = evaluate(stats)
    count = sum(unlocked.values())
    st.progress(count / len(unlocked), text=f"{count} of {len(unlocked)} achievements unlocked")
    cols = st.columns(4)
    for index, ach in enumerate(all_achievements()):
        got = unlocked[ach.key]
        with cols[index % 4]:
            html(f'<div class="mf-card" style="text-align:center;opacity:{1 if got else .55}">'
                 f'<div class="mf-flower" style="font-size:2.6rem">{e(ach.emoji) if got else "🔒"}</div>'
                 f"<h4>{e(ach.title)}</h4><p>{e(ach.description)}</p>"
                 f'<span class="mf-badge {"ok" if got else "info"}">{"Unlocked ✨" if got else "Locked"}</span></div>')
    with st.expander("How progress is measured"):
        st.json(stats)
