"""Bridge to the Conversation Intelligence Copilot (Project A, ../../conversation-intelligence-copilot).

Project A stays an independent service (its own FastAPI app, DuckDB data and dependencies); Florome calls its
documented ``POST /api/chat`` endpoint and translates the response into Florome's answer contract:

  headline        -> statement            key_points -> bullets
  first bar chart -> bars visual (else headline metrics -> kpis)
  evidence        -> evidence chips (conversation id + quoted excerpt; Project A has no Florome page to link to)
  follow_up_questions -> follow_ups       token_usage.model_calls -> source.model_calls

Its own status is passed through unchanged: "unsupported" or "insufficient_data" answers are shown as such, never
re-worded into something more confident. If the service is not configured or not reachable, the answer says so.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from florome.config import Settings

SOURCE = "Conversation Intelligence Copilot"
CUSTOMER_STARTERS = ["What are customers most negative about?", "Which customer concerns need leadership attention?",
                     "Which agents could use coaching?", "How did sentiment change in a conversation?"]
_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(" ,:;") + "…"


async def health(settings: Settings) -> dict[str, Any]:
    if not settings.copilot_url:
        return {"configured": False, "reachable": False, "status": "not configured"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(settings.copilot_url.rstrip("/") + "/health")
        body = r.json() if r.status_code == 200 else {}
        return {"configured": True, "reachable": r.status_code == 200, "status": body.get("status", f"HTTP {r.status_code}")}
    except (httpx.HTTPError, ValueError):
        return {"configured": True, "reachable": False, "status": "unreachable"}


def unavailable(reason: str) -> dict[str, Any]:
    return {"statement": f"I can't answer customer-conversation questions right now: the {SOURCE} is {reason}.",
            "bullets": ["It runs as a separate service (Project A); start it and ask again",
                        "Florome's own areas (outages, security, money, governance) are unaffected"],
            "visual": None, "evidence": [], "follow_ups": ["What's broken right now?", "Which vulnerabilities are confirmed?",
                                                             "Where does the money go?", "Is the audit log intact?"],
            "source": {"name": SOURCE, "status": reason, "model_calls": None}, "focus": {}}


async def ask(settings: Settings, question: str, session_id: str | None) -> dict[str, Any]:
    if not settings.copilot_url:
        return unavailable("not configured (set FLOROME_COPILOT_URL)")
    body: dict[str, Any] = {"question": question[:4000]}
    if session_id and _SESSION.match(session_id):
        body["session_id"] = session_id
    try:
        async with httpx.AsyncClient(timeout=settings.copilot_timeout_seconds) as c:
            r = await c.post(settings.copilot_url.rstrip("/") + "/api/chat", json=body)
    except httpx.HTTPError:
        return unavailable("not reachable")
    if r.status_code != 200:
        return unavailable(f"returning HTTP {r.status_code}")
    try:
        return translate(r.json())
    except (ValueError, KeyError, TypeError):
        return unavailable("returning a response Florome could not read")


def translate(d: dict[str, Any]) -> dict[str, Any]:
    status = d.get("status", "completed")
    visual = None
    for ch in d.get("charts") or []:
        series = ch.get("series") or []
        if "bar" in str(ch.get("chart_type")) and ch.get("x_field") and series and ch.get("data"):
            key = series[0]["key"]
            items = [{"label": _clip(row.get(ch["x_field"]), 40), "value": float(row[key])} for row in ch["data"][:8]
                     if isinstance(row.get(key), int | float)]
            if items:
                visual = {"type": "bars", "unit": f"{series[0].get('label', key)} · {ch.get('title', '')}".strip(" ·"), "items": items}
                break
    if visual is None and d.get("metrics"):
        visual = {"type": "kpis", "items": [{"label": _clip(m["label"], 30), "value": m["value"]} for m in d["metrics"][:3]
                                             if isinstance(m.get("value"), int | float | str)]}
    evidence = []
    for e in (d.get("evidence") or [])[:4]:
        quote = next((x["text"] for x in e.get("excerpts") or [] if x.get("role") == "customer"), "")
        label = f"{e.get('conversation_id')} · {e.get('topic') or ''}".strip(" ·")
        evidence.append({"label": _clip(f"{label}: “{quote}”" if quote else label, 70), "href": None})
    bullets = [_clip(x, 190) for x in (d.get("key_points") or [])[:4]]
    if status != "completed":
        bullets = [f"The {SOURCE} reported: {status.replace('_', ' ')}"] + bullets
    follow = [_clip(q, 90) for q in (d.get("follow_up_questions") or [])][:4]
    follow += [q for q in CUSTOMER_STARTERS if q not in follow][: 4 - len(follow)]
    usage = d.get("token_usage") or {}
    return {"statement": _clip(d.get("headline") or d.get("answer") or "No answer was returned.", 240), "bullets": bullets[:5],
            "visual": visual, "evidence": evidence, "follow_ups": follow[:4],
            "source": {"name": SOURCE, "status": status, "model_calls": usage.get("model_calls"),
                       "dataset": (d.get("dataset_scope") or {}).get("dataset_mode")},
            "focus": {"copilot_session": d.get("session_id"), "copilot_followups": d.get("follow_up_questions") or []}}
