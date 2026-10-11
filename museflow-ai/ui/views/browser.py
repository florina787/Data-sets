"""🌐 Browser Magic — simulated navigation over fictional fixture pages."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import scenario_loader as fixtures
from ui.components import page_run, render_run, section, start_run, timeline
from ui.session import ctx


def render() -> None:
    engine = ctx().engine
    section("🌐", "Browser Magic", "Wren reads fictional pages from fixtures. No real browser, no network, no transactions.")
    tasks = fixtures.browser_fixture()["tasks"]
    c1, c2 = st.columns([3, 1])
    task = c1.selectbox("Scenario", list(tasks), format_func=lambda k: tasks[k]["title"], index=list(tasks).index("booking"))
    c2.write("")
    if c2.button("🧭 Run", type="primary", width="stretch"):
        page_run("browser", start_run("browser", {"task": task}))
    st.caption("The booking scenario deliberately simulates a page-load timeout on the first attempt so you can see retry handling.")

    run = page_run("browser")
    if run is not None:
        out = run.outputs.get("browser", {})
        if out:
            with st.container(border=True):
                st.markdown(f"🔒 `{out['url']}` &nbsp; *(fictional site)*")
                steps = [(s["step"], s["detail"], "completed") for s in out["steps"]]
                retries = [ev for ev in run.agent_events if ev["node"] == "browser" and ev["status"] == "retrying"]
                for ev in retries:
                    steps.insert(1, ("Retry after simulated failure", ev["message"], "retrying"))
                if run.status == "completed" and run.values.get("action_result"):
                    steps.append(("Action completed in simulation", run.values["action_result"].get("confirmation", ""), "completed"))
                elif run.status == "awaiting_approval":
                    steps.append(("Waiting for your approval", "Nothing is submitted until you decide", "waiting"))
                timeline(steps)
                if out["results"]:
                    st.dataframe(pd.DataFrame(out["results"]), hide_index=True, width="stretch")
                if out.get("form"):
                    st.markdown("**Form populated (in memory):**")
                    st.json(out["form"])
        render_run(run, key="browser")
    if engine.stores.bookings or engine.stores.form_submissions:
        st.subheader("🧾 Simulated confirmations")
        st.dataframe(pd.DataFrame([{k: v for k, v in b.items() if k != "form"} for b in engine.stores.bookings + engine.stores.form_submissions]),
                     hide_index=True, width="stretch")
