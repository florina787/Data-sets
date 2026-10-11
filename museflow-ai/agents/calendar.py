"""Calendar role (Celeste 🌙): free-slot search, conflict detection, simulated scheduling."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from agents.base import AgentResult, agent_node
from services import scenario_loader as fixtures
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def busy_intervals(events: list[dict[str, Any]], day: str) -> list[tuple[int, int]]:
    return sorted((fixtures.parse_hhmm(e["start"]), fixtures.parse_hhmm(e["end"])) for e in events if e["date"] == day)


def free_windows(events: list[dict[str, Any]], day: str, start_min: int, end_min: int, min_len: int = 30) -> list[dict[str, int]]:
    windows, cursor = [], start_min
    for a, b in busy_intervals(events, day):
        if a > cursor and a - cursor >= min_len:
            windows.append({"start_min": cursor, "end_min": min(a, end_min)})
        cursor = max(cursor, b)
    if end_min - cursor >= min_len:
        windows.append({"start_min": cursor, "end_min": end_min})
    return [w for w in windows if w["end_min"] - w["start_min"] >= min_len]


def conflicts(events: list[dict[str, Any]], day: str, start: int, end: int) -> list[dict[str, Any]]:
    return [e for e in events if e["date"] == day and fixtures.parse_hhmm(e["start"]) < end and start < fixtures.parse_hhmm(e["end"])]


def find_slot(events: list[dict[str, Any]], first_day: date, duration: int, work: tuple[int, int], after_min: int = 0, days: int = 10) -> tuple[date, int] | None:
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for window in free_windows(events, day.isoformat(), *work):
            start = max(window["start_min"], after_min if offset == 0 else 0)
            start = ((start + 14) // 15) * 15
            if start + duration <= window["end_min"]:
                return day, start
    return None


@agent_node("calendar", "calendar")
def calendar(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    scenario = state.get("scenario_id")
    params = state.get("params") or {}
    events = tools.call("calendar.read_events", {"week_of": fixtures.week_start(ctx.today).isoformat()})
    hours = fixtures.calendar_fixture()["working_hours"]
    work = (fixtures.parse_hhmm(hours["start"]), fixtures.parse_hhmm(hours["end"]))
    monday = fixtures.week_start(ctx.today)

    if scenario == "schedule_meeting":
        day = monday + timedelta(days=params["day_offset"])
        start = fixtures.parse_hhmm(params["start"])
        end = start + params["duration_min"]
        clashes = conflicts(events, day.isoformat(), start, end)
        chosen_day, chosen_start = day, start
        if clashes or end > 24 * 60:
            slot = find_slot(events, day, params["duration_min"], work, after_min=start)
            if slot is None:
                raise ValueError("No free slot in the next 10 days")
            chosen_day, chosen_start = slot
        chosen_end = chosen_start + params["duration_min"]
        when = f"{WEEKDAYS[chosen_day.weekday()]} {chosen_day.isoformat()} {fixtures.format_hhmm(chosen_start)}–{fixtures.format_hhmm(chosen_end)}"
        action = {
            "tool": "calendar.simulate_create_event", "agent": "calendar",
            "summary": f"Add “{params['title']}” on {when} to your simulated calendar.",
            "args": {"title": params["title"], "date": chosen_day.isoformat(), "start": fixtures.format_hhmm(chosen_start),
                     "end": fixtures.format_hhmm(chosen_end), "category": "simulated"},
        }
        head = (f"Conflict with {', '.join(c['title'] for c in clashes)} — suggested {when} instead." if clashes
                else f"{when} is free.")
        return AgentResult(
            output={"kind": "meeting", "requested": {"date": day.isoformat(), "start": params["start"]},
                    "conflicts": clashes, "proposed": action["args"], "rescheduled": bool(clashes), "headline": head},
            message=head, updates={"action": action},
        )

    if scenario == "travel_planning":
        friday = monday + timedelta(days=4)
        window = [(friday, 17 * 60, 24 * 60), (friday + timedelta(days=1), 0, 24 * 60), (friday + timedelta(days=2), 0, 20 * 60)]
        clashes = [c for d, a, b in window for c in conflicts(events, d.isoformat(), a, b)]
        head = (f"{len(clashes)} weekend conflict(s): {', '.join(c['title'] for c in clashes)} — consider rescheduling."
                if clashes else "Your weekend is free. 🌙")
        return AgentResult(output={"kind": "weekend_check", "conflicts": clashes, "headline": head}, message=head)

    if scenario == "dream_team":
        slots: list[dict[str, str]] = []
        for _ in range(3):
            slot = find_slot(events + [{**x, "title": "focus"} for x in slots], ctx.today, 60, work)
            if not slot:
                break
            day, start = slot
            slots.append({"date": day.isoformat(), "start": fixtures.format_hhmm(start), "end": fixtures.format_hhmm(start + 60)})
        head = f"Found {len(slots)} free 60-minute focus slots: " + ", ".join(f"{s['date']} {s['start']}" for s in slots)
        return AgentResult(output={"kind": "free_slots", "slots": slots, "headline": head}, message=head)

    # weekly_planning: free windows for Mon–Fri of the current week.
    free: dict[str, list[dict[str, int]]] = {}
    busy = 0
    for offset in range(5):
        day = monday + timedelta(days=offset)
        free[WEEKDAYS[offset]] = free_windows(events, day.isoformat(), *work)
        busy += len(busy_intervals(events, day.isoformat()))
    free_hours = sum(w["end_min"] - w["start_min"] for ws in free.values() for w in ws) / 60
    head = f"{busy} existing events this week; {free_hours:g} free working hours to plan."
    return AgentResult(
        output={"kind": "week_availability", "week_of": monday.isoformat(), "free_windows": free, "busy_events": busy,
                "free_hours": free_hours, "headline": head},
        message=head,
    )


