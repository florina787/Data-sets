"""🤖🌌 Agent Universe — the twelve agent roles."""
from __future__ import annotations

import streamlit as st

from services import scenario_loader as fixtures
from ui.components import agent_card, html, page_run, render_run, section, start_run
from ui.session import ctx


def render() -> None:
    engine = ctx().engine
    section("🤖", "Agent Universe", "Twelve deterministic agent roles — plain Python functions orchestrated as LangGraph nodes, not autonomous LLMs.")
    counts: dict[str, int] = {}
    last: dict[str, str] = {}
    for run in sorted(engine.runs.values(), key=lambda r: r.run_id):
        for event in run.agent_events:
            counts[event["agent"]] = counts.get(event["agent"], 0) + 1
            last[event["agent"]] = f"{run.title}: {event.get('message', '')}"

    agents = fixtures.list_agents()
    selected = st.session_state.get("agent_selected", "supervisor")
    cols = st.columns(3)
    for index, profile in enumerate(agents):
        with cols[index % 3]:
            agent_card(profile, counts.get(profile.key, 0), last.get(profile.key, ""))
            if st.button(f"Explore {profile.name}", key=f"agent_{profile.key}", width="stretch"):
                st.session_state["agent_selected"] = profile.key
                selected = profile.key

    profile = fixtures.get_agent(selected)
    st.divider()
    html(f'<h2>{profile.emoji} {profile.name} — {profile.role}</h2>')
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Capabilities**\n" + "\n".join(f"- {c}" for c in profile.capabilities))
        st.markdown("**Allowlisted tools**\n" + ("\n".join(f"- `{t}`" for t in profile.tools) or "- (no tools — pure routing/computation)"))
        if profile.key in {"supervisor", "audit"}:
            st.caption("Participates in every workflow.")
    with c2:
        st.markdown("**Try a workflow that features this agent**")
        options = [s for s in fixtures.list_scenarios() if profile.key in s.specialists or s.id in profile.scenarios]
        if not options:
            options = fixtures.list_scenarios(showcase_only=True)
        choice = st.selectbox("Workflow", options, format_func=lambda s: f"{s.emoji} {s.title}", key=f"wf_{profile.key}")
        st.caption(choice.description)
        if st.button(f"▶️ Run “{choice.title}”", type="primary", key=f"run_{profile.key}"):
            page_run("agents", start_run(choice.id))
    last = page_run("agents")
    if last is not None:
        render_run(last, key="agents")
