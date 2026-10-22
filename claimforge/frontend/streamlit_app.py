"""ClaimForge Copilot — Streamlit UI.

Run from the ``claimforge/`` directory:  streamlit run frontend/streamlit_app.py
SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="ClaimForge Copilot", page_icon="🛡️", layout="wide")

from app.models.domain import PERSONAS  # noqa: E402
from frontend.components import ui  # noqa: E402
from frontend.components.session import init, platform  # noqa: E402
from frontend.views import claimiq, operations, sdlc, system  # noqa: E402

SECTIONS = {**sdlc.VIEWS, **operations.VIEWS, **claimiq.VIEWS, **system.VIEWS}
ORDER = ["Copilot", "Requirements", "Policy Evidence", "Impact Analysis", "Architecture", "Development Plan",
         "QA & Tests", "Claims Simulation", "Security & Governance", "Release Center", "ClaimIQ", "Root Cause",
         "Traceability", "Use Case Catalog", "System Metrics"]


def main() -> None:
    init()
    ui.inject_css()
    p = platform()
    with st.sidebar:
        st.markdown("## 🛡️ ClaimForge")
        st.caption("Agentic SDLC & Production Intelligence · ClaimIQ")
        st.session_state.persona = st.selectbox("Persona", PERSONAS, index=PERSONAS.index(st.session_state.persona))
        nav = st.session_state.get("nav", "Copilot")
        choice = st.radio("Navigate", ORDER, index=ORDER.index(nav) if nav in ORDER else 0,
                          format_func=lambda s: f"{ORDER.index(s) + 1}. {s}")
        st.session_state.nav = choice
        st.divider()
        st.markdown(f"**Mode:** {'🟢 DEMO' if p.settings.demo_mode else '🟣 LIVE AI'}")
        st.caption(p.llm.mode)
        st.caption(f"Paid LLM calls: {p.llm.paid_calls}")
        st.caption("SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION.")
        if st.button("Reset session"):
            for k in ("sdlc", "ciq", "sim_run", "clarifications"):
                st.session_state.pop(k, None)
            p.reset_production()
            st.rerun()
    if choice != "Copilot":
        ui.synthetic_banner()
    SECTIONS[choice]()


main()
