"""✨ Magic Task Planner — dependency-aware plans with optional approved execution."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services import scenario_loader as fixtures
from ui.components import e, html, page_run, render_run, section, start_run
from ui.session import ctx
from workflows.params import ASSIGNEES

SCENARIOS = {
    "interview": "🎤 Prepare for an interview", "vacation": "🧳 Plan a vacation", "project": "🗂️ Organize a project",
    "presentation": "🎀 Prepare a presentation", "week": "📅 Plan a productive week",
}


def dependency_dot(tasks: list[dict], critical: set[str]) -> str:
    def q(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')
    lines = ['digraph G {', 'rankdir=LR; bgcolor="transparent";',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#B79CED", fillcolor="#FFF9FD", fontcolor="#4A315E"];',
             'edge [color="#B79CED"];']
    for task in tasks:
        fill = "#F7B7D2" if task["id"] in critical else "#FFF9FD"
        agent = fixtures.get_agent(task["agent"])
        lines.append(f'"{q(task["id"])}" [label="{q(task["id"])}: {q(task["title"])}\\n{agent.emoji} {q(agent.name)} · {task["hours"]:g} h", fillcolor="{fill}"];')
        for dep in task["depends_on"]:
            lines.append(f'"{q(dep)}" -> "{q(task["id"])}";')
    lines.append("}")
    return "\n".join(lines)


def render() -> None:
    engine = ctx().engine
    section("✨", "Magic Task Planner", "Nova decomposes a goal, orders it by dependency and schedules it; Stella finds the critical path.")
    with st.form("planner"):
        c1, c2 = st.columns(2)
        template = c1.selectbox("Task scenario", list(SCENARIOS), format_func=SCENARIOS.get)
        priority = c2.select_slider("Priority", ["low", "medium", "high"], value="medium")
        c3, c4 = st.columns(2)
        target = c3.date_input("Target date", value=date.today() + timedelta(days=14), min_value=date.today())
        assignee = c4.selectbox("Assign agent", ASSIGNEES, format_func=lambda k: "✨ Auto (best fit per task)" if k == "auto" else
                                f"{fixtures.get_agent(k).emoji} {fixtures.get_agent(k).name}")
        execute = st.checkbox("Also schedule these tasks on my session task board (consequential → needs approval)", value=True)
        if st.form_submit_button("🦋 Generate task plan", type="primary"):
            page_run("planner", start_run("project_planning", {"plan_template": template, "priority": priority,
                                                               "target_date": target.isoformat(), "assignee": assignee, "execute": execute}))

    run = page_run("planner")
    if run is None:
        st.info("🦋 Choose a scenario and generate a plan to see the dependency graph.")
    else:
        plan = run.outputs.get("planning", {})
        cpm = run.outputs.get("analytics", {}).get("cpm", {})
        if plan.get("tasks"):
            html(f"<h3>{e(plan['title'])}</h3>")
            st.caption(plan.get("headline", ""))
            st.graphviz_chart(dependency_dot(plan["tasks"], set(cpm.get("critical_path", []))))
            st.caption("Pink nodes are on the critical path (zero slack). Arrows point from a dependency to the task that needs it.")
            frame = pd.DataFrame([{"Task": t["id"], "Title": t["title"], "Agent": fixtures.get_agent(t["agent"]).name,
                                   "Hours": t["hours"], "Depends on": ", ".join(t["depends_on"]) or "—",
                                   "Start": t["start_date"], "Due": t["due_date"]} for t in plan["tasks"]])
            st.dataframe(frame, hide_index=True, width="stretch")
        render_run(run, key="planner")

    board = engine.stores.task_board
    st.subheader("📋 Session task board (simulated)")
    if not board:
        st.caption("Approved plans land here. Tick tasks off as you complete them.")
    for index, task in enumerate(board):
        done = st.checkbox(f"{task['id']} · {task['title']} — due {task['due_date']} ({task['plan']})", value=task["done"], key=f"task_{index}")
        task["done"] = done
    if board:
        finished = sum(t["done"] for t in board)
        st.progress(finished / len(board), text=f"{finished}/{len(board)} tasks complete")
