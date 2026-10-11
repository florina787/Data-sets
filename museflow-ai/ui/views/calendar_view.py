"""📅 Celestial Calendar — fictional events, conflict detection, approved (simulated) bookings."""
from __future__ import annotations

import calendar as pycal
from datetime import timedelta

import streamlit as st

from services import scenario_loader as fixtures
from ui.components import e, html, page_run, render_run, section, start_run
from ui.session import ctx

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _events() -> list[dict]:
    engine = ctx().engine
    return fixtures.resolve_calendar_events(engine.today) + list(engine.stores.calendar_events)


def month_grid(year: int, month: int, events: list[dict], today_iso: str) -> str:
    by_day: dict[str, list[dict]] = {}
    for event in sorted(events, key=lambda ev: ev["start"]):
        by_day.setdefault(event["date"], []).append(event)
    rows = []
    for week in pycal.Calendar(firstweekday=0).monthdatescalendar(year, month):
        cells = []
        for day in week:
            iso = day.isoformat()
            classes = " ".join(c for c in ("today" if iso == today_iso else "", "out" if day.month != month else "") if c)
            evs = "".join(f'<span class="ev {e(ev.get("source", ""))}" title="{e(ev["title"])}">{e(ev["start"])} {e(ev["title"])}</span>'
                          for ev in by_day.get(iso, [])[:3])
            more = len(by_day.get(iso, [])) - 3
            evs += f'<span class="ev">+{more} more</span>' if more > 0 else ""
            cells.append(f'<td class="{classes}"><span class="d">{day.day}</span>{evs}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{d}</th>" for d in WEEKDAYS)
    return f'<table class="mf-cal" aria-label="Month calendar"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def render() -> None:
    engine = ctx().engine
    section("📅", "Celestial Calendar", "Fictional schedule · Celeste detects conflicts · nothing is booked without your approval.")
    st.caption("No external calendar is connected. Events come from `data/synthetic_calendar.json` plus approved simulated bookings (green).")
    events = _events()
    monday = fixtures.week_start(engine.today)
    tab_month, tab_week, tab_book, tab_plan = st.tabs(["🗓️ Month", "📆 Week", "🌙 Schedule a meeting", "🦋 Time-block my week"])

    with tab_month:
        html(f"<h3>{pycal.month_name[monday.month]} {monday.year}</h3>")
        html(month_grid(monday.year, monday.month, events, engine.today.isoformat()))

    with tab_week:
        cols = st.columns(7)
        for offset in range(7):
            day = monday + timedelta(days=offset)
            with cols[offset]:
                html(f"<strong>{WEEKDAYS[offset]}</strong><br><small>{day.isoformat()}</small>")
                for event in sorted((ev for ev in events if ev["date"] == day.isoformat()), key=lambda ev: ev["start"]):
                    icon = "🟢" if event.get("source") == "session" else "🟣"
                    st.caption(f"{icon} {event['start']}–{event['end']} {event['title']}")

    with tab_book:
        with st.form("meeting"):
            title = st.text_input("Meeting title", "Coffee chat with Mentor", max_chars=80)
            c1, c2, c3 = st.columns(3)
            day_offset = c1.selectbox("Day", list(range(0, 14)),
                                      format_func=lambda o: f"{WEEKDAYS[(monday + timedelta(days=o)).weekday()]} {(monday + timedelta(days=o)).isoformat()}", index=2)
            start = c2.selectbox("Start", [f"{h:02d}:{m:02d}" for h in range(8, 18) for m in (0, 30)], index=4)
            duration = c3.selectbox("Duration (min)", [15, 30, 45, 60, 90, 120], index=1)
            if st.form_submit_button("🌙 Check & propose", type="primary"):
                page_run("calendar", start_run("schedule_meeting", {"title": title, "day_offset": day_offset, "start": start, "duration_min": duration}))
        run = page_run("calendar")
        if run is not None:
            cal = run.outputs.get("calendar", {})
            if cal.get("conflicts"):
                st.warning("⚠️ Conflict detected with: " + ", ".join(f"{c['title']} ({c['start']}–{c['end']})" for c in cal["conflicts"]))
            if cal.get("proposed"):
                p = cal["proposed"]
                st.success(f"Proposed slot: {p['date']} {p['start']}–{p['end']}")
            render_run(run, key="cal")

    with tab_plan:
        st.caption("Runs *Weekly Planning*: Supervisor → Memory → Calendar → Planning → Governance → Audit.")
        if st.button("🦋 Time-block my week", type="primary"):
            page_run("calendar_week", start_run("weekly_planning"))
        week_run = page_run("calendar_week")
        if week_run is not None:
            blocks = week_run.outputs.get("planning", {}).get("blocks", [])
            if blocks:
                st.dataframe([{"Day": b["day"], "Block": f"{b['emoji']} {b['label']}", "Start": b["start"], "End": b["end"]} for b in blocks],
                             hide_index=True, width="stretch")
            render_run(week_run, key="calweek")
