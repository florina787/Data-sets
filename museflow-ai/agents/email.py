"""Email role (Rosie 💌): template-based drafting. Sending is always a SIMULATION."""
from __future__ import annotations

from typing import Any

from agents.base import AgentResult, agent_node
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState


def compose(fixture: dict[str, Any], scenario: str, recipient_role: str, tone: str) -> dict[str, Any]:
    template = fixture["scenarios"][scenario]
    recipient = fixture["recipients"][recipient_role]
    style = fixture["tones"][tone]
    first = recipient["name"].split()[0]
    role = template.get("role") or ""
    body_lines = [line.format(role=role) for line in template["body"]]
    if tone in {"concise", "executive"}:
        body_lines = body_lines[:2]
    paragraphs = [style["greeting"].format(first=first)]
    if style["opener"]:
        paragraphs.append(style["opener"])
    paragraphs.append(" ".join(body_lines))
    paragraphs.append(f"{style['closing']}\n{fixture['sender']['name']}")
    return {
        "to": recipient["address"], "to_name": recipient["name"], "to_role": recipient["role"],
        "from": fixture["sender"]["address"], "subject": template["subject"].format(role=role),
        "body": "\n\n".join(paragraphs), "tone": tone, "scenario": scenario,
    }


@agent_node("email", "email")
def email(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    params = state.get("params") or {}
    fixture = tools.call("email.compose_draft", {"scenario": params.get("email_scenario", "project_update")})
    if state.get("scenario_id") == "dream_team":
        draft = compose(fixture, "project_update", "team_lead", "executive")
    else:
        draft = compose(fixture, params["email_scenario"], params["recipient_role"], params["tone"])
        if params.get("custom_subject"):
            draft["subject"] = params["custom_subject"]
        if params.get("custom_body"):
            draft["body"] = params["custom_body"]
            draft["edited_by_user"] = True
    action = {
        "tool": "email.simulate_send", "agent": "email",
        "summary": f"Simulate sending “{draft['subject']}” to {draft['to_name']} <{draft['to']}>. No real email leaves this app.",
        "args": {"to": draft["to"], "subject": draft["subject"], "body": draft["body"]},
    }
    return AgentResult(
        output={"kind": "draft", "draft": draft,
                "headline": f"Drafted “{draft['subject']}” for {draft['to_name']} in {'an' if draft['tone'][0] in 'aeiou' else 'a'} {draft['tone']} tone."},
        message=f"Drafted email ({draft['tone']}) and proposed email.simulate_send.",
        updates={"action": action},
    )
