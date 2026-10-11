"""Planning role (Nova 🦋): task decomposition, dependency ordering and scheduling."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from agents.base import AgentResult, agent_node, prior
from services import scenario_loader as fixtures
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState

DAILY_CAPACITY_HOURS = {"high": 6.0, "medium": 4.0, "low": 2.0}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def topological_order(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kahn's algorithm; ties broken by task id for determinism. Raises on cycles."""
    by_id = {t["id"]: t for t in tasks}
    remaining = {t["id"]: set(t["depends_on"]) for t in tasks}
    for deps in remaining.values():
        unknown = deps - by_id.keys()
        if unknown:
            raise ValueError(f"Unknown dependencies: {sorted(unknown)}")
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = sorted(tid for tid, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("Dependency cycle detected in plan")
        for tid in ready:
            ordered.append(by_id[tid])
            del remaining[tid]
            for deps in remaining.values():
                deps.discard(tid)
    return ordered


def schedule_tasks(tasks: list[dict[str, Any]], start: date, priority: str) -> list[dict[str, Any]]:
    """Single-worker list scheduling: each task starts after its dependencies and the previous task."""
    capacity = DAILY_CAPACITY_HOURS[priority]
    finish_hour: dict[str, float] = {}
    cursor = 0.0
    scheduled = []
    for task in topological_order(tasks):
        begin = max([cursor, *(finish_hour[d] for d in task["depends_on"])])
        end = begin + float(task["hours"])
        finish_hour[task["id"]] = end
        cursor = end
        start_day = start + timedelta(days=int(begin // capacity))
        due_day = start + timedelta(days=int(max(end - 1e-9, 0) // capacity))
        scheduled.append({**task, "start_hour": begin, "end_hour": end, "start_date": start_day.isoformat(), "due_date": due_day.isoformat()})
    return scheduled


def place_block(windows: list[dict[str, int]], used: list[tuple[int, int]], duration: int, prefer_late: bool) -> tuple[int, int] | None:
    """Earliest (or latest) 30-minute-aligned slot inside a free window that avoids used slots."""
    candidates = []
    for window in windows:
        start = window["start_min"]
        while start + duration <= window["end_min"]:
            if not any(a < start + duration and start < b for a, b in used):
                candidates.append(start)
            start += 30
    if not candidates:
        return None
    begin = max(candidates) if prefer_late else min(candidates)
    return begin, begin + duration


def _assign(tasks: list[dict[str, Any]], assignee: str) -> list[dict[str, Any]]:
    return tasks if assignee == "auto" else [{**t, "agent": assignee} for t in tasks]


def _template_plan(state: MuseState, ctx: MuseContext, tools: ToolRecorder, template_key: str) -> dict[str, Any]:
    params = state.get("params") or {}
    templates = tools.call("planning.build_plan", {"template": template_key})["templates"]
    template = templates[template_key]
    priority = params.get("priority", "medium")
    tasks = schedule_tasks(_assign(template["tasks"], params.get("assignee", "auto")), ctx.today, priority)
    finish = max(date.fromisoformat(t["due_date"]) for t in tasks)
    plan: dict[str, Any] = {
        "title": template["title"], "priority": priority, "tasks": tasks,
        "start_date": ctx.today.isoformat(), "finish_date": finish.isoformat(),
        "total_hours": sum(float(t["hours"]) for t in tasks),
    }
    if params.get("target_date"):
        target = date.fromisoformat(params["target_date"])
        plan.update(target_date=target.isoformat(), slack_days=(target - finish).days, on_track=finish <= target)
    return plan


def _weekly_plan(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    signals = prior(state, "memory").get("signals", {})
    free = prior(state, "calendar").get("free_windows", {})
    blocks_fx = tools.call("planning.build_plan", {"template": "week"})["focus_blocks"]
    prefer = signals.get("time_of_day", "morning")
    blocks = []
    for day, windows in free.items():
        used: list[tuple[int, int]] = []
        for block in blocks_fx:
            slot = place_block(windows, used, block["duration_min"], prefer_late=(prefer != "morning"))
            if slot is None:
                continue
            used.append(slot)
            blocks.append({"day": day, "label": block["label"], "emoji": block["emoji"],
                           "start": fixtures.format_hhmm(slot[0]), "end": fixtures.format_hhmm(slot[1])})
    blocks.sort(key=lambda b: (WEEKDAYS.index(b["day"]), b["start"]))
    deep = sum(1 for b in blocks if b["label"] == "Deep work")
    personal = f" (using your preference for {prefer} focus)" if signals.get("time_of_day") else ""
    return AgentResult(
        output={"kind": "weekly_plan", "blocks": blocks, "preference_used": prefer,
                "headline": f"Planned {len(blocks)} time blocks including {deep} deep-work sessions{personal}."},
        message=f"Allocated {len(blocks)} blocks into free calendar windows.",
    )


def _travel_itinerary(state: MuseState, ctx: MuseContext) -> AgentResult:
    dest = prior(state, "research").get("selected")
    if not dest:
        raise ValueError("Research did not select a destination")
    friday = fixtures.week_start(ctx.today) + timedelta(days=4)
    itinerary = [
        {"when": "Friday 18:00", "what": f"Depart for {dest['name']} ({dest['travel_hours']} h)"},
        {"when": "Saturday 10:00", "what": dest["highlights"][0]},
        {"when": "Saturday 15:00", "what": dest["highlights"][1]},
        {"when": "Saturday 20:00", "what": dest["highlights"][2]},
        {"when": "Sunday 16:00", "what": "Return home"},
    ]
    action = {
        "tool": "travel.simulate_hold_itinerary", "agent": "planning",
        "summary": f"Hold a fictional weekend at {dest['stay']} in {dest['name']} for {dest['price']} ✦ (simulated).",
        "args": {"destination": dest["name"], "stay": dest["stay"], "price_credits": dest["price"],
                 "from": friday.isoformat(), "to": (friday + timedelta(days=2)).isoformat()},
    }
    return AgentResult(
        output={"kind": "itinerary", "destination": dest["name"], "itinerary": itinerary, "weekend_start": friday.isoformat(),
                "headline": f"Drafted a 3-day itinerary for {dest['name']} ({dest['price']} ✦ fictional)."},
        message=f"Itinerary drafted for {dest['name']}; proposed a simulated hold.",
        updates={"action": action},
    )


def _dream_team(state: MuseState, ctx: MuseContext) -> AgentResult:
    goals = (state.get("params") or {}).get("goals", [])
    recruits = [g for g in ["memory", "research", "document", "calendar", "browser", "email", "analytics"] if g in goals]
    team = [fixtures.get_agent(k) for k in recruits]
    return AgentResult(
        output={"kind": "team_plan", "recruits": recruits,
                "mission": [f"{a.emoji} {a.name} ({a.role})" for a in team],
                "headline": f"Recruited {len(recruits)} specialists: {', '.join(a.name for a in team)}."},
        message=f"Supervisor will route conditionally to: {', '.join(recruits)}.",
        queue_insert=recruits,
    )


@agent_node("planning", "planning")
def planning(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    scenario = state.get("scenario_id")
    params = state.get("params") or {}
    if scenario == "weekly_planning":
        return _weekly_plan(state, ctx, tools)
    if scenario == "travel_planning":
        return _travel_itinerary(state, ctx)
    if scenario == "dream_team":
        return _dream_team(state, ctx)
    if scenario == "interview_prep":
        plan = _template_plan({**state, "params": {"priority": "medium"}}, ctx, tools, "interview")
        days = int(params.get("days_until", 7))
        plan["interview_date"] = (ctx.today + timedelta(days=days)).isoformat()
        plan["on_track"] = plan["finish_date"] <= plan["interview_date"]
        return AgentResult(
            output={"kind": "task_plan", **plan,
                    "headline": f"Study plan: {len(plan['tasks'])} steps, {plan['total_hours']:g} h, ready by {plan['finish_date']}."},
            message=f"Built {len(plan['tasks'])}-step interview plan.",
        )
    # project_planning (Magic Task Planner)
    plan = _template_plan(state, ctx, tools, params.get("plan_template", "project"))
    updates: dict[str, Any] = {}
    if params.get("execute"):
        updates["action"] = {
            "tool": "planning.simulate_schedule_tasks", "agent": "planning",
            "summary": f"Schedule {len(plan['tasks'])} tasks for '{plan['title']}' on your session task board (simulated).",
            "args": {"plan_title": plan["title"], "tasks": [{"id": t["id"], "title": t["title"], "due_date": t["due_date"], "agent": t["agent"]} for t in plan["tasks"]]},
        }
    status = "" if "on_track" not in plan else (" — on track ✅" if plan["on_track"] else f" — {abs(plan['slack_days'])} day(s) late ⚠️")
    return AgentResult(
        output={"kind": "task_plan", **plan,
                "headline": f"'{plan['title']}': {len(plan['tasks'])} tasks, {plan['total_hours']:g} h, finishing {plan['finish_date']}{status}."},
        message=f"Ordered {len(plan['tasks'])} tasks by dependency and scheduled them.",
        updates=updates,
    )
