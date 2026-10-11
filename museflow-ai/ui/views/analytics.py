"""📊 Magic Analytics — measured execution metrics vs. clearly-labelled estimates."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import metrics, scenario_loader as fixtures
from ui.charts import hbar
from ui.components import kpi, section


def render() -> None:
    from ui.session import ctx

    engine = ctx().engine
    section("📊", "Magic Analytics", "Observability for this session's workflows.")
    m = metrics.measured(engine)
    est = metrics.illustrative(engine)

    st.subheader("📏 Measured execution metrics")
    st.caption("Computed directly from recorded execution events in this session.")
    row = st.columns(4)
    with row[0]:
        kpi("Total workflow executions", m["total_runs"], f"{m['completed']} completed")
    with row[1]:
        kpi("Avg run time", f"{m['avg_run_ms']:.1f} ms", f"avg node {m['avg_node_ms']:.2f} ms")
    with row[2]:
        kpi("Completion rate", f"{m['completion_rate']:.0%}", "of finished runs")
    with row[3]:
        kpi("Error / retry rate", f"{m['error_rate']:.1%}", f"{m['error_events']} failed or retried steps")
    row = st.columns(4)
    with row[0]:
        kpi("Tool calls", m["tool_calls"], "allowlisted, simulated")
    with row[1]:
        kpi("Audit entries", m["audit_entries"], "hash-chained")
    with row[2]:
        kpi("Actual LLM tokens", m["llm_tokens"], "no LLM client exists")
    with row[3]:
        kpi("Actual API cost", f"${m['llm_cost_usd']:.2f}", "no paid API calls")

    if m["agent_invocations"]:
        c1, c2 = st.columns(2)
        inv = sorted(m["agent_invocations"].items(), key=lambda kv: -kv[1])
        with c1:
            st.plotly_chart(hbar([fixtures.get_agent(k).name + " " + fixtures.get_agent(k).emoji for k, _ in inv], [v for _, v in inv],
                                 "Agent invocations"), use_container_width=True)
        with c2:
            statuses = sorted(m["status_counts"].items(), key=lambda kv: -kv[1])
            st.plotly_chart(hbar([k.replace("_", " ") for k, _ in statuses], [v for _, v in statuses], "Runs by status"), use_container_width=True)
        if m["approval_outcomes"]:
            outcomes = sorted(m["approval_outcomes"].items(), key=lambda kv: -kv[1])
            st.plotly_chart(hbar([k for k, _ in outcomes], [v for _, v in outcomes], "Approval outcomes"), use_container_width=True)
        with st.expander("Table view"):
            st.dataframe(pd.DataFrame([{"Agent": fixtures.get_agent(k).name, "Invocations": v} for k, v in inv]), hide_index=True, width="stretch")
            st.dataframe(pd.DataFrame([{"Run": r.run_id, "Workflow": r.title, "Status": r.status, "Agent steps": len(r.agent_events),
                                        "Measured ms": round(r.wall_ms, 2)} for r in engine.history()]), hide_index=True, width="stretch")
    else:
        st.info("Run a few workflows to populate the charts.")

    st.subheader("🔮 Illustrative estimates")
    st.warning("These are **synthetic estimates**, not measurements. They exist only to illustrate what a real deployment might track.")
    row = st.columns(3)
    with row[0]:
        kpi("Token equivalents", f"{est['token_equivalents']:,}", f"output chars ÷ {est['assumptions']['chars_per_token']}", kind="illustrative")
    with row[1]:
        kpi("Estimated cost avoidance", f"${est['cost_avoidance_usd']:.4f}", f"at a hypothetical ${est['assumptions']['usd_per_1k_tokens']}/1K tokens", kind="illustrative")
    with row[2]:
        kpi("Simulated time saved", f"{est['minutes_saved']} min", "per-scenario guesses", kind="illustrative")
    st.caption(f"Assumptions: {est['assumptions']['minutes_saved']}")
