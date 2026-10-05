"""Session helpers: one shared platform instance + workflow runners (UI calls services, never re-implements logic)."""

from __future__ import annotations

import streamlit as st

from app.models.domain import PERSONAS
from app.requirements.analyzer import DEMO_REQUIREMENT, DEMO_REQUIREMENT_EXPLICIT
from app.services.platform import ClaimForgePlatform

EXAMPLES = {
    "BR-391 (ambiguous wording — triggers human clarification)": DEMO_REQUIREMENT,
    "BR-391 (explicit wording)": DEMO_REQUIREMENT_EXPLICIT,
    "Chiropractic limit change": "Increase chiropractic annual maximum from $500 to $600.",
    "Ambiguous visit status": "Increase physiotherapy annual maximum from $750 to $1,000 and require prior authorization after 10 visits.",
    "Unstructured request": "Please make the claims portal better for members.",
}


@st.cache_resource(show_spinner=False)
def platform() -> ClaimForgePlatform:
    return ClaimForgePlatform()


def init() -> None:
    ss = st.session_state
    ss.setdefault("request_text", DEMO_REQUIREMENT)
    ss.setdefault("persona", PERSONAS[0])
    ss.setdefault("clarifications", {})
    ss.setdefault("sdlc", None)
    ss.setdefault("ciq", None)
    ss.setdefault("n_claims", 10_000)


def run_sdlc(stop_after: str | None, approval: dict | None = None, inject_defect: bool = True) -> dict:
    ss = st.session_state
    p = platform()
    if approval is not None:
        p.reset_production()
        ss.ciq = None
    with st.spinner("ClaimForge Copilot working… (deterministic engines, zero LLM calls in DEMO_MODE)"):
        state = p.run_workflow(ss.request_text, persona=ss.persona, clarifications=ss.clarifications,
                               approval=approval, stop_after=stop_after, inject_defect=inject_defect,
                               n_claims=ss.n_claims)
    ss.sdlc = state
    return state


def run_investigation(stop_after: str | None = None) -> dict:
    ss = st.session_state
    with st.spinner("ClaimIQ investigating… (bounded agent loop over deterministic tools)"):
        state = platform().run_workflow("Investigate the production anomaly in claim denials (ClaimIQ).",
                                        persona=ss.persona, workflow="CLAIMIQ_INVESTIGATION", stop_after=stop_after)
    ss.ciq = state
    return state


def need(key: str, stage: str, button_label: str) -> dict | None:
    """Return the SDLC state if it contains ``key``; else offer to run the workflow up to ``stage``."""
    s = st.session_state.sdlc
    if s and s.get(key) is not None:
        return s
    if s and s.get("status") == "NEEDS_CLARIFICATION":
        st.warning("The requirement has an unresolved CRITICAL ambiguity. Resolve it on the **Copilot** or "
                   "**Requirements** page first (human-in-the-loop gate).")
        return None
    st.info("Not generated yet for the current request.")
    if st.button(button_label, type="primary", key=f"need-{key}"):
        s = run_sdlc(stage)
        if s.get(key) is None:
            st.rerun()
        return s
    return None
