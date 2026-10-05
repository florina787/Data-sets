"""Traceability, Use Case Catalog and System Metrics views."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from frontend.components.session import platform


def traceability() -> None:
    st.title("Traceability")
    ui.label("DETERMINISTIC traceability graph — forward and reverse tracing")
    g = platform().trace_graph
    ids = sorted(g.nodes)
    focus = st.session_state.get("trace_focus", "BR-391")
    node = st.selectbox("Trace from", ids, index=ids.index(focus) if focus in ids else 0,
                        format_func=lambda i: f"{i} ({g.nodes[i]['type']})")
    t = platform().traceability(node)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Upstream (reverse trace)**")
        st.dataframe(pd.DataFrame(t["upstream"])[["id", "type", "label"]] if t["upstream"] else pd.DataFrame(),
                     width="stretch", hide_index=True)
    with c2:
        st.markdown("**Downstream (forward trace)**")
        st.dataframe(pd.DataFrame(t["downstream"])[["id", "type", "label"]] if t["downstream"] else pd.DataFrame(),
                     width="stretch", hide_index=True)
    if t["feedback_links"]:
        st.markdown("**SDLC feedback links:** " + ", ".join(f"{e['source_id']} → {e['target_id']}" for e in t["feedback_links"]))
    ui.mermaid(t["mermaid"], 560)
    st.caption("Expected chain: Requirement → Policy → Business Rule → Component → Implementation → Test → Release → "
               "Production Metric → Anomaly → Incident → Defect (→ feedback to Requirement).")


def catalog() -> None:
    st.title("Use Case Catalog")
    ucs = platform().use_cases()
    df = pd.DataFrame(ucs)
    counts = df.status.value_counts().to_dict()
    ui.cards([("Implemented", str(counts.get("IMPLEMENTED", 0)), ""), ("Partial", str(counts.get("PARTIAL", 0)), ""),
              ("Planned", str(counts.get("PLANNED", 0)), "not implemented")], per_row=3)
    stage = st.multiselect("Lifecycle stage", sorted(df.lifecycle_stage.unique()))
    if stage:
        df = df[df.lifecycle_stage.isin(stage)]
    df = df.assign(status=df.status.map(ui.status_badge), demo_available=df.demo_available.map(lambda b: "Yes" if b else "No"))
    st.dataframe(df.rename(columns={"id": "ID", "use_case": "Use Case", "lifecycle_stage": "Lifecycle Stage",
                                    "agent_engine": "Agent / Engine", "status": "Status", "demo_available": "Demo Available",
                                    "where": "Where", "note": "Note"}),
                 width="stretch", hide_index=True, height=600)


def system_metrics() -> None:
    st.title("System Metrics")
    m = platform().system_metrics()
    ui.cards([("Paid LLM calls", str(m["paid_llm_calls"]), m["llm_mode"]), ("Workflow runs", str(m["counters"].get("workflow.runs", 0)), ""),
              ("Trace graph", f"{m['trace_nodes']} nodes", f"{m['trace_edges']} edges"),
              ("Approvals / deployments / defects", f"{m['approvals']} / {m['deployments']} / {m['defects']}", "")])
    last = st.session_state.get("ciq") or st.session_state.get("sdlc")
    if last:
        tr = pd.DataFrame(last.get("trace", []))
        if not tr.empty:
            fig = go.Figure(go.Bar(x=tr.latency_ms, y=tr.node, orientation="h",
                                   marker_color=[ui.SERIES[0] if k == "AGENT" else ui.SERIES[2] for k in tr.kind],
                                   hovertemplate="%{y}: %{x} ms<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(hovermode="closest")
            st.plotly_chart(ui.style_fig(fig, 520, "Last workflow — node order & latency (blue = agent, aqua = deterministic)"),
                            width="stretch")
            st.json(last.get("observability", {}))
    with st.expander("Settings (secret-free)"):
        st.json(m["settings"])
    with st.expander("Tool allowlist"):
        st.dataframe(pd.DataFrame(m["tools"]), width="stretch", hide_index=True)
    with st.expander("Audit log (tail)"):
        st.dataframe(pd.DataFrame(m["audit_tail"]), width="stretch", hide_index=True)
    with st.expander("Node latency"):
        st.json(m["latency"])
    with st.expander("LangGraph workflow (Mermaid)"):
        st.code(platform().workflow_diagram(), language="text")


VIEWS = {"Traceability": traceability, "Use Case Catalog": catalog, "System Metrics": system_metrics}
