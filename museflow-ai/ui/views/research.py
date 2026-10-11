"""🔎 Research Studio — synthetic research briefs."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import scenario_loader as fixtures
from ui.charts import hbar
from ui.components import page_run, render_run, section, start_run


def render() -> None:
    section("🔎", "Research Studio", "Aurora assembles briefs from curated fixtures; Stella scores options when a matrix exists.")
    st.warning("**Demo research — synthetic data, not live web results.** No web search is performed and no real sources are cited.")
    fx = fixtures.research_fixture()
    topics = fx["studio_topics"]
    c1, c2 = st.columns([3, 1])
    topic = c1.selectbox("Research scenario", topics, format_func=lambda t: fx["topics"][t]["title"])
    c2.write("")
    if c2.button("🧚 Run research", type="primary", width="stretch"):
        page_run("research", start_run("research", {"topic": topic}))

    run = page_run("research")
    if run is None:
        st.info("Pick a scenario and run it to see the agent plan, evidence, findings and execution trace.")
        return
    brief = run.outputs.get("research", {})
    if not brief:
        render_run(run, key="research")
        return
    st.subheader(f"📜 {brief['title']}")
    st.caption(brief["disclaimer"])
    st.markdown(f"**🎯 Research objective** — {brief['objective']}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🗺️ Agent plan**\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(brief["plan"], 1)))
        st.markdown("**💡 Findings**\n" + "\n".join(f"- {f}" for f in brief["findings"]))
    with c2:
        st.markdown("**🌟 Recommendations**\n" + "\n".join(f"- {r}" for r in brief["recommendations"]))
        st.markdown("**⚠️ Limitations**\n" + "\n".join(f"- {lim}" for lim in brief["limitations"]))
    with st.expander("🧾 Simulated evidence cards", expanded=True):
        st.dataframe(pd.DataFrame(brief["evidence"]), hide_index=True, width="stretch")
    ranking = run.outputs.get("analytics", {}).get("ranking")
    if ranking:
        st.plotly_chart(hbar([r["option"] for r in ranking], [r["percent"] for r in ranking],
                             "Weighted score (illustrative opinions, not benchmarks)", "{:.1f}", "%"), use_container_width=True)
        with st.expander("Table view & criteria"):
            matrix = brief["matrix"]
            rows = [{"Criterion": c["name"], "Weight": c["weight"], **dict(zip(matrix["options"], c["scores"]))} for c in matrix["criteria"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.subheader("🔍 Execution trace")
    render_run(run, key="research")
