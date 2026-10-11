"""Persistent navigation sidebar."""
from __future__ import annotations

import streamlit as st

from ui.components import asset_data_uri, demo_badge, html
from ui.session import PAGE_LABELS, PAGES, ctx


def render_sidebar() -> str:
    session = ctx()
    with st.sidebar:
        logo = asset_data_uri("logo.svg")
        logo_html = f'<img src="{logo}" alt="" style="width:44px;height:44px"/>' if logo else "🦄"
        html(
            f'<div style="display:flex;gap:.6rem;align-items:center">{logo_html}<div>'
            '<div class="mf-display" style="font-size:1.45rem;font-weight:700;color:var(--mf-heading)">MuseFlow AI</div>'
            '<div style="font-style:italic;color:var(--mf-muted);font-size:.86rem">Your Magical AI Universe</div></div></div>'
        )
        html(f'<div style="margin:.6rem 0 .2rem 0">{demo_badge()}</div>')
        if "nav" not in st.session_state:
            st.session_state["nav"] = "dashboard"
        page = st.radio("Navigate", [key for key, _ in PAGES], format_func=PAGE_LABELS.get, key="nav", label_visibility="collapsed")
        pending = len(session.engine.pending())
        if pending:
            html(f'<div class="mf-card" style="padding:.5rem .8rem"><p>💖 {pending} approval(s) waiting</p></div>')
        st.caption("All AI reasoning, integrations and actions are simulated. No API keys. No real emails, bookings or calendar changes.")
    session.pages_visited.add(page)
    return page
