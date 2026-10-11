"""Reusable presentation components.

Rule: every dynamic value placed into custom HTML goes through ``e()`` (html.escape).
Custom HTML is used for presentation only; all interaction uses native Streamlit widgets.
"""
from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import streamlit as st

from services import scenario_loader as fixtures
from services.validation import ValidationError, escape as e
from ui import animations
from ui.session import ctx, flash, go
from ui.themes import css_variables, get_theme

ASSETS = Path(__file__).resolve().parent.parent / "assets"

STATUS_STYLE = {
    "completed": ("ok", "✅", "Completed"),
    "awaiting_approval": ("warn", "⏳", "Pending approval"),
    "running": ("info", "🔄", "Running"),
    "rejected": ("bad", "✋", "Rejected"),
    "cancelled": ("bad", "🚫", "Cancelled"),
    "denied": ("bad", "🛡️", "Denied by policy"),
    "error": ("bad", "⚠️", "Error"),
    "unsupported": ("info", "❔", "Unsupported"),
    "failed": ("bad", "⚠️", "Failed"),
    "retrying": ("warn", "🔁", "Retried"),
}


def no_autolink(text: str) -> str:
    """Escape and stop Markdown from turning synthetic addresses into mailto: links."""
    return e(text).replace("@", "<span>@</span>")


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


@lru_cache(maxsize=None)
def _asset_text(name: str) -> str:
    path = ASSETS / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


@lru_cache(maxsize=None)
def asset_data_uri(name: str) -> str:
    text = _asset_text(name)
    if not text:
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()


def inject_theme() -> None:
    settings = ctx().settings
    theme = get_theme(settings["theme"])
    reduced = settings["reduced_motion"]
    css = _asset_text("styles.css")
    html(f"<style>:root{{{css_variables(theme)}color-scheme:{'dark' if theme.dark else 'light'};}}\n{css}</style>")
    html(animations.sky_markup(settings["animation"], reduced))


def lumi(size: str = "mf-lumi") -> str:
    """Lumi mascot <img>. Falls back to an emoji when the asset is missing."""
    uri = asset_data_uri("unicorn.svg")
    settings = ctx().settings
    floating = " mf-floating" if settings["animation"] != "Off" and not settings["reduced_motion"] else ""
    if not uri:
        return f'<span class="{size}" style="font-size:4rem" role="img" aria-label="Lumi the unicorn">🦄</span>'
    return f'<img class="{size}{floating}" src="{uri}" alt="Lumi, the MuseFlow unicorn mascot"/>'


def section(emoji: str, title: str, subtitle: str = "") -> None:
    html(f'<h1 style="margin-bottom:.1rem">{e(emoji)} {e(title)}</h1>')
    if subtitle:
        st.caption(subtitle)


def demo_badge() -> str:
    return '<span class="mf-badge demo">PUBLIC DEMO · SIMULATED AI</span>'


def badge(text: str, tone: str = "info") -> str:
    return f'<span class="mf-badge {e(tone)}">{e(text)}</span>'


def status_badge(status: str) -> str:
    tone, icon, label = STATUS_STYLE.get(status, ("info", "•", status))
    return badge(f"{icon} {label}", tone)


def card(title: str, body: str = "", emoji: str = "", extra_html: str = "") -> None:
    html(f'<div class="mf-card"><h4>{e(emoji)} {e(title)}</h4><p>{e(body)}</p>{extra_html}</div>')


def kpi(label: str, value: Any, note: str = "", kind: str = "measured") -> None:
    tag = "measured" if kind == "measured" else "illustrative estimate" if kind == "illustrative" else kind
    html(
        f'<div class="mf-card mf-kpi"><div class="mf-kpi-label">{e(label)}</div>'
        f'<div class="mf-kpi-value">{e(value)}</div><div class="mf-kpi-label">{e(note)}</div>'
        f'<span class="mf-tag">{e(tag)}</span></div>'
    )


def agent_card(profile: Any, invocations: int = 0, last: str = "") -> None:
    html(
        f'<div class="mf-card"><div class="mf-agent"><div class="mf-avatar" style="background:{e(profile.color)}55">{e(profile.emoji)}</div>'
        f'<div><h4 style="margin:0">{e(profile.name)} <small>· {e(profile.role)}</small></h4>'
        f'<p>{e(profile.personality)}</p>'
        f'<div style="margin-top:.35rem">{badge(f"{invocations} run(s) this session", "ok" if invocations else "info")}</div>'
        f'{f"<p style=margin-top:.3rem><small>Latest: {e(last)}</small></p>" if last else ""}</div></div></div>'
    )


def timeline(items: Iterable[tuple[str, str, str]]) -> None:
    """items: (title, meta, css_class)"""
    rows = "".join(f'<li class="{e(cls)}"><strong>{e(title)}</strong><br><span class="mf-meta">{e(meta)}</span></li>' for title, meta, cls in items)
    html(f'<ul class="mf-timeline">{rows}</ul>')


def run_timeline(run: Any) -> None:
    items = []
    for event in run.agent_events:
        agent = fixtures.get_agent(event["agent"])
        tools = ", ".join(c["tool"] for c in event.get("tool_calls", [])) or "no tool calls"
        meta = f"{event['node']} · {event['status']} · {event.get('duration_ms', 0):.2f} ms · {tools} — {event.get('message', '')}"
        items.append((f"{agent.emoji} {agent.name} ({agent.role})", meta, event["status"]))
    if run.status == "awaiting_approval":
        items.append(("💖 Cora (Approval Agent)", "approval · paused at a LangGraph interrupt — waiting for your decision", "waiting"))
    timeline(items)


def _decide(run_id: str, decision: str, note_key: str) -> None:
    engine = ctx().engine
    try:
        run = engine.resume(run_id, decision, st.session_state.get(note_key, "") or "")
    except (ValidationError, KeyError) as exc:
        flash(str(exc), "⚠️")
        return
    if run.status == "completed":
        flash(f"{run.title}: approved action completed in simulation.", "💖")
    else:
        flash(f"{run.title}: {run.status}.", "✋")


def approval_box(run: Any, key: str) -> None:
    pending = run.pending or {}
    with st.container(border=True):
        html(f"{status_badge('awaiting_approval')} &nbsp; <strong>{no_autolink(pending.get('summary', ''))}</strong>")
        st.caption(f"Tool: `{pending.get('tool')}` · proposed by {fixtures.get_agent(pending.get('agent', 'supervisor')).name} · "
                   "nothing happens (even in simulation) until you decide.")
        with st.expander("Inspect the exact simulated action"):
            st.json(pending.get("args", {}))
        note_key = f"note_{key}_{run.run_id}"
        st.text_input("Optional note for the audit log", key=note_key, max_chars=200)
        c1, c2, c3 = st.columns(3)
        c1.button("💖 Approve", key=f"ap_{key}_{run.run_id}", type="primary", on_click=_decide, args=(run.run_id, "approved", note_key), width="stretch")
        c2.button("✋ Reject", key=f"rj_{key}_{run.run_id}", on_click=_decide, args=(run.run_id, "rejected", note_key), width="stretch")
        c3.button("🚫 Cancel", key=f"cx_{key}_{run.run_id}", on_click=_decide, args=(run.run_id, "cancelled", note_key), width="stretch")


def _focus_galaxy(run_id: str) -> None:
    ctx().focus_run = run_id
    go("galaxy")


def render_run(run: Any, key: str, show_response: bool = True, show_trace: bool = True) -> None:
    """Shared result block: status, final response, approval controls, and agent activity."""
    html(f"{status_badge(run.status)} &nbsp; <small>{e(run.run_id)} · {e(run.title)} · {run.wall_ms:.1f} ms measured</small>")
    if run.status == "awaiting_approval":
        approval_box(run, key)
    elif show_response and run.final_response:
        st.markdown(run.final_response)
    if show_trace:
        with st.expander(f"🔍 Agent activity — {len(run.agent_events)} executed graph nodes", expanded=False):
            run_timeline(run)
            st.button("🔮 Open in Workflow Galaxy", key=f"gal_{key}_{run.run_id}", on_click=_focus_galaxy, args=(run.run_id,))


def start_run(scenario_id: str | None, params: dict[str, Any] | None = None, request: str | None = None) -> Any:
    """Start a workflow and surface validation errors as friendly messages."""
    try:
        with st.spinner("✨ Lumi is assembling the team…"):
            return ctx().engine.start(scenario_id, params, request)
    except ValidationError as exc:
        st.error(f"🦄 {exc}")
        return None


def celebrate() -> None:
    settings = ctx().settings
    if settings["reduced_motion"] or settings["animation"] == "Off":
        return
    st.session_state["_confetti_seed"] = st.session_state.get("_confetti_seed", 0) + 1
    html(animations.confetti_markup(st.session_state["_confetti_seed"]))


def json_block(data: Any) -> None:
    st.code(json.dumps(data, indent=2, default=str), language="json")


def demo_note(text: str) -> None:
    html(f'<div class="mf-card" style="padding:.55rem .9rem"><p>🧪 {e(text)}</p></div>')


def page_run(page: str, run: Any = None) -> Any:
    """Remember the latest run started from a page so it survives reruns (e.g. after approving)."""
    key = f"_last_run_{page}"
    if run is not None:
        st.session_state[key] = run.run_id
    run_id = st.session_state.get(key)
    return ctx().engine.runs.get(run_id) if run_id else None


def render_artifacts(run: Any) -> None:
    """Show the main artefact each workflow produced (plan, draft, brief…) from its node outputs."""
    out = run.outputs
    plan = out.get("planning", {})
    if plan.get("kind") == "weekly_plan" and plan.get("blocks"):
        st.markdown("**🗓️ Your simulated weekly plan**")
        st.dataframe([{"Day": b["day"], "Block": f"{b['emoji']} {b['label']}", "Start": b["start"], "End": b["end"]}
                      for b in plan["blocks"]], hide_index=True, width="stretch")
    elif plan.get("kind") == "task_plan" and plan.get("tasks"):
        st.markdown(f"**🦋 {plan['title']}**")
        st.dataframe([{"Task": t["id"], "Title": t["title"], "Agent": fixtures.get_agent(t["agent"]).name, "Hours": t["hours"],
                       "Due": t["due_date"]} for t in plan["tasks"]], hide_index=True, width="stretch")
    elif plan.get("kind") == "itinerary":
        st.markdown(f"**🧳 Weekend in {plan['destination']} (fictional)**")
        st.dataframe(plan["itinerary"], hide_index=True, width="stretch")
    research = out.get("research", {})
    if research.get("kind") == "brief" and research.get("findings"):
        with st.expander(f"🧚 {research['title']} — {research['disclaimer']}"):
            st.markdown("\n".join(f"- {f}" for f in research["findings"]))
            st.caption("Evidence: " + ", ".join(f"{ev['id']}" for ev in research["evidence"]))
    draft = out.get("email", {}).get("draft")
    if draft:
        with st.expander(f"💌 Draft: {draft['subject']}", expanded=run.status == "awaiting_approval"):
            st.text(f"To: {draft['to_name']} <{draft['to']}>\n\n{draft['body']}")
    doc = out.get("document", {})
    if doc.get("summary"):
        with st.expander(f"📚 {doc['meta']['title']} — extractive summary"):
            st.markdown("\n".join(f"- {s['sentence']} `line {s['line']}`" for s in doc["summary"]))
    memories = out.get("memory", {}).get("memories")
    if memories:
        st.markdown("**🌸 Memories used**\n" + "\n".join(f"- *{m['category']}* — {m['text']}" for m in memories[:5]))
