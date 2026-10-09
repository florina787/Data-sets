"""Reusable Streamlit UI components for ClaimForge Copilot (presentation only — no business logic)."""

from __future__ import annotations

import html
import json

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Reference categorical palette (validated slots 1–3) + reserved status colours.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
ACTION_COLORS = {"KEEP": "#8a8985", "ENHANCE": SERIES[0], "ADD": SERIES[2], "REPLACE": SERIES[1]}

CSS = """
<style>
.cf-banner{border-left:4px solid #d03b3b;padding:.55rem .9rem;border-radius:6px;margin:.2rem 0 .8rem 0;
  background:rgba(208,59,59,.08);font-size:.92rem}
.cf-card{border:1px solid rgba(128,128,128,.25);border-radius:10px;padding:.7rem .9rem;margin-bottom:.6rem}
.cf-card .lbl{font-size:.78rem;opacity:.75;text-transform:uppercase;letter-spacing:.04em}
.cf-card .val{font-size:1.45rem;font-weight:650;line-height:1.3}
.cf-card .sub{font-size:.8rem;opacity:.75}
.cf-pill{display:inline-block;padding:.08rem .5rem;border-radius:999px;font-size:.74rem;font-weight:600;
  border:1px solid rgba(128,128,128,.35);margin-right:.3rem}
.cf-step{display:inline-block;padding:.35rem .6rem;border-radius:8px;margin:.15rem;border:1px solid rgba(128,128,128,.3);font-size:.85rem}
.cf-flow{display:flex;flex-direction:column;gap:.15rem}
.cf-flow .node{border:1px solid rgba(128,128,128,.3);border-radius:8px;padding:.45rem .7rem}
.cf-flow .arrow{text-align:center;opacity:.6}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def synthetic_banner() -> None:
    st.markdown('<div class="cf-banner">⚠️ <b>Synthetic demonstration only.</b> Not for real claim adjudication. '
                'NorthStar Health Benefits and all members, providers, claims and policies are fictional.</div>',
                unsafe_allow_html=True)


def card(label: str, value: str, sub: str = "") -> None:
    st.markdown(f'<div class="cf-card"><div class="lbl">{html.escape(label)}</div>'
                f'<div class="val">{html.escape(str(value))}</div><div class="sub">{html.escape(sub)}</div></div>',
                unsafe_allow_html=True)


def cards(items: list[tuple[str, str, str]], per_row: int = 4) -> None:
    for i in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, item in zip(cols, items[i:i + per_row]):
            with col:
                card(*item)


def label(kind: str) -> None:
    """Show how a capability is implemented (DETERMINISTIC / SIMULATED / MOCKED / LLM-ASSISTED)."""
    st.caption(f"Implementation: **{kind}**")


def status_badge(status: str) -> str:
    s = status.upper()
    icon = {"PASS": "✅", "IMPLEMENTED": "✅", "READY": "✅", "WARN": "⚠️", "PARTIAL": "🟡",
            "READY WITH APPROVAL": "🟡", "FAIL": "❌", "BLOCKED": "⛔", "NOT READY": "❌", "PLANNED": "○"}.get(s, "•")
    return f"{icon} {status}"


def mermaid(code: str, height: int = 420) -> None:
    """Render Mermaid in the browser (CDN). The source is also available below if offline."""
    safe = html.escape(code)
    components.html(
        f"""<div class="mermaid">{safe}</div>
        <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        mermaid.initialize({{startOnLoad: true, theme: dark ? 'dark' : 'neutral', securityLevel: 'strict'}});
        </script>""",
        height=height, scrolling=True)
    with st.expander("Mermaid source"):
        st.code(code, language="text")


def style_fig(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40 if title else 10, b=40), title=title,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="top", y=-0.15, x=0), hovermode="x unified",
                      font=dict(size=12))
    fig.update_xaxes(showgrid=False, linecolor="rgba(128,128,128,.4)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,.15)", zeroline=False)
    return fig


def progress(state: dict | None) -> None:
    """SDLC progress strip: ✓ done, ⚠ needs attention, ○ not yet."""
    s = state or {}
    req = s.get("requirement")
    blocking = bool(req and req.blocking_ambiguities)
    gov = s.get("governance") or {}
    rr = s.get("release_risk")
    steps = [
        ("Requirement", "⚠" if blocking else ("✓" if req is not None else "○")),
        ("Policy", "✓" if s.get("policy") else "○"),
        ("Impact", "✓" if s.get("impact") else "○"),
        ("Architecture", "✓" if s.get("architecture") else "○"),
        ("Development Plan", "✓" if s.get("development_plan") else "○"),
        ("Tests", ("⚠" if s["tests"]["summary"]["failed"] else "✓") if s.get("tests") else "○"),
        ("Simulation", ("⚠" if s["simulation"].unexpected_changes else "✓") if s.get("simulation") is not None else "○"),
        ("Governance", ("⚠" if gov.get("warn") or gov.get("fail") else "✓") if gov else "○"),
        ("Approval", "✓" if (s.get("approval") or {}).get("decision") == "APPROVED" and s.get("release", {}).get("approval")
         else ("⚠" if s.get("status") == "AWAITING_APPROVAL" or (rr is not None and rr.decision.value in ("BLOCKED", "NOT READY")) else "○")),
        ("Release", "✓" if s.get("release", {}).get("status", "").startswith("DEPLOYED") else "○"),
        ("ClaimIQ", ("⚠" if s.get("anomaly", {}).get("detected") else "✓") if s.get("production") else "○"),
    ]
    st.markdown(" ".join(f'<span class="cf-step">{icon} {name}</span>' for name, icon in steps), unsafe_allow_html=True)


def json_block(obj) -> None:
    st.code(json.dumps(obj, indent=2, default=str)[:20000], language="json")


def flow(nodes: list[tuple[str, str]]) -> None:
    parts = []
    for i, (title, body) in enumerate(nodes):
        parts.append(f'<div class="node"><b>{html.escape(title)}</b><br/>{html.escape(body)}</div>')
        if i < len(nodes) - 1:
            parts.append('<div class="arrow">↓</div>')
    st.markdown(f'<div class="cf-flow">{"".join(parts)}</div>', unsafe_allow_html=True)
