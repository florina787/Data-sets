"""🔮 Workflow Galaxy — visualises *actual* execution events of a LangGraph run."""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache

import pandas as pd
import streamlit as st

from services import scenario_loader as fixtures
from ui.charts import timeline
from ui.components import badge, html, section, status_badge
from ui.session import ctx, go
from workflows.graph import NODE_AGENT, graph_topology

STATUS_FILL = {"completed": "#C8F7E5", "retrying": "#FFF0D5", "retried": "#FFF0D5", "failed": "#FFC9D6", "waiting": "#FFE1A8"}


@lru_cache(maxsize=1)
def _topology() -> tuple[tuple[str, ...], tuple[tuple[str, str, bool], ...]]:
    topo = graph_topology()
    return tuple(topo["nodes"]), tuple(tuple(edge) for edge in topo["edges"])


def galaxy_dot(run) -> str:
    nodes, edges = _topology()
    visits: dict[str, list[int]] = {}
    status: dict[str, str] = {}
    for event in run.trace:
        visits.setdefault(event["node"], []).append(event["seq"])
        previous = status.get(event["node"])
        if "failed" in (previous, event["status"]):
            status[event["node"]] = "failed"
        elif previous in ("retrying", "retried") or event["status"] == "retrying":
            status[event["node"]] = "retried" if event["status"] == "completed" else "retrying"
        else:
            status[event["node"]] = event["status"]
    if run.status == "awaiting_approval":
        status["approval"] = "waiting"
    traversed = set()
    order = [e["node"] for e in run.trace]
    for a, b in zip(order, order[1:]):
        traversed.add((a, b))
    if order and run.status != "awaiting_approval":
        traversed.add((order[-1], "__end__"))
    traversed.add(("__start__", "intent_router"))
    if run.status == "awaiting_approval" and order:
        traversed.add((order[-1], "approval"))

    lines = ['digraph G {', 'bgcolor="transparent"; rankdir=LR; nodesep=0.18; ranksep=0.9;',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, color="#B79CED", fillcolor="#FFF9FD", fontcolor="#4A315E"];',
             'edge [color="#D8CCEE", arrowsize=0.6];']
    for node in nodes:
        if node in ("__start__", "__end__"):
            lines.append(f'"{node}" [shape=circle, label="{"▶" if node == "__start__" else "■"}", width=0.35, fillcolor="#DCC8FF"];')
            continue
        agent = fixtures.get_agent(NODE_AGENT.get(node, "supervisor"))
        seqs = visits.get(node, [])
        state = status.get(node)
        fill = STATUS_FILL.get(state, "#FFFFFF")
        pen = "3" if state else "1"
        border = "#E0587F" if state == "failed" else "#EDA100" if state in ("waiting", "retrying", "retried") else "#6250d6" if state else "#D8CCEE"
        order_label = f"\\n#{', #'.join(map(str, seqs[:4]))}{'…' if len(seqs) > 4 else ''}" if seqs else ""
        lines.append(f'"{node}" [label="{agent.emoji} {node}\\n{agent.name}{order_label}", fillcolor="{fill}", color="{border}", penwidth={pen}];')
    for source, target, conditional in edges:
        hit = (source, target) in traversed
        style = "dashed" if conditional else "solid"
        color = "#6250d6" if hit else "#E6DDF5"
        width = "2.4" if hit else "0.8"
        lines.append(f'"{source}" -> "{target}" [style={style}, color="{color}", penwidth={width}];')
    lines.append("}")
    return "\n".join(lines)


def timeline_rows(run) -> list[dict]:
    events = run.trace
    if not events:
        return []
    t0 = datetime.fromisoformat(events[0]["started_at"])
    return [{"seq": ev["seq"], "node": ev["node"], "status": ev["status"], "duration_ms": ev.get("duration_ms", 0.0),
             "start_ms": (datetime.fromisoformat(ev["started_at"]) - t0).total_seconds() * 1000} for ev in events]


def render() -> None:
    session = ctx()
    engine = session.engine
    section("🔮", "Workflow Galaxy", "Every node, edge and timing below is read from the run's recorded LangGraph execution events.")
    runs = engine.history()
    if not runs:
        html('<div class="mf-card"><h4>🌌 The galaxy is quiet</h4><p>Run any workflow and its execution graph will light up here.</p></div>')
        st.button("✨ Launch the AI dream team", type="primary", on_click=go, args=("chat",), kwargs={"chat_prefill": "Launch my AI dream team."})
        return
    ids = [r.run_id for r in runs]
    default = ids.index(session.focus_run) if session.focus_run in ids else 0
    run_id = st.selectbox("Workflow run", ids, index=default, format_func=lambda r: f"{engine.runs[r].emoji} {engine.runs[r].title} · {r} · {engine.runs[r].status}")
    session.focus_run = run_id
    run = engine.runs[run_id]

    agent_events = run.agent_events
    route_events = [e for e in run.trace if e["kind"] == "route"]
    cols = st.columns(5)
    cols[0].metric("Agent nodes executed", len(agent_events))
    cols[1].metric("Supervisor routing hops", len(route_events))
    cols[2].metric("Tool calls", sum(len(e.get("tool_calls", [])) for e in agent_events))
    cols[3].metric("Measured duration", f"{run.wall_ms:.1f} ms")
    cols[4].metric("Checkpoints saved", engine.checkpoints.checkpoint_count(run_id))
    html(f"{status_badge(run.status)} &nbsp; {badge('thread ' + run.thread_id[:14] + '…', 'info')}")
    if run.status == "awaiting_approval":
        st.warning("⏸️ Active step: **approval** — the graph is paused at a LangGraph `interrupt` and checkpointed. "
                   "Approving resumes this exact thread from the checkpoint (it does not restart).")

    view = session.settings["viz_style"]
    tab_graph, tab_time = st.tabs(["🌌 Graph", "⏱️ Timeline"] if view == "Graph" else ["⏱️ Timeline", "🌌 Graph"])
    graph_tab, time_tab = (tab_graph, tab_time) if view == "Graph" else (tab_time, tab_graph)
    with graph_tab:
        st.graphviz_chart(galaxy_dot(run), use_container_width=True)
        st.caption("Bold violet edges were traversed; dashed edges are conditional (supervisor routing). "
                   "Green = completed · amber = retried/waiting · pink = failed. #n = execution sequence numbers.")
    with time_tab:
        rows = timeline_rows(run)
        st.plotly_chart(timeline(rows, "Node execution timeline (measured)"), use_container_width=True)

    st.subheader("🔁 State transitions & routing decisions")
    frame = pd.DataFrame([{"#": e["seq"], "Node": e["node"], "Agent": fixtures.get_agent(e["agent"]).name, "Kind": e["kind"],
                           "Status": e["status"], "ms": round(e.get("duration_ms", 0.0), 3), "Message": e.get("message", "")} for e in run.trace])
    st.dataframe(frame, hide_index=True, width="stretch")

    st.subheader("🔬 Node inspector")
    choice = st.selectbox("Inspect an execution event", range(len(run.trace)),
                          format_func=lambda i: f"#{run.trace[i]['seq']} · {run.trace[i]['node']} · {run.trace[i]['status']}")
    event = run.trace[choice]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Input (state the node received)**")
        st.json(event.get("input", {}))
    with c2:
        st.markdown("**Output (state update it produced)**")
        st.json(event.get("output", {}))
    if event.get("tool_calls"):
        st.markdown("**Tool calls**")
        st.dataframe(pd.DataFrame(event["tool_calls"]), hide_index=True, width="stretch")
