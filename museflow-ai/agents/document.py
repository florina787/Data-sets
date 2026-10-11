"""Document role (Athena 📚): deterministic extraction over bundled synthetic documents."""
from __future__ import annotations

import difflib
from typing import Any

from agents.base import AgentResult, agent_node
from services import text_analysis as ta
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState

SKILL_HEADINGS = ("required skills", "responsibilities", "nice to have")


def analyze(text: str, key_fields: list[str] | None) -> dict[str, Any]:
    summary = ta.extractive_summary(text, 3)
    fields = ta.extract_fields(text, key_fields)
    evidence = [{"kind": "summary", "line": s["line"], "snippet": s["sentence"]} for s in summary]
    evidence += [{"kind": "field", "line": f["line"], "snippet": f"{f['field']}: {f['value']}"} for f in fields]
    return {
        "summary": summary,
        "fields": fields,
        "entities": ta.extract_entities(text),
        "sections": ta.extract_sections(text),
        "action_items": ta.extract_action_items(text),
        "keywords": ta.top_keywords(text),
        "stats": ta.document_stats(text),
        "evidence": sorted(evidence, key=lambda e: e["line"]),
    }


def skill_topics(text: str) -> list[str]:
    """Collect bullet lines under skill-like headings of a job description."""
    topics, active = [], False
    for _, line in ta.body_lines(text):
        if line.startswith("#"):
            active = line.lstrip("#").strip().lower() in SKILL_HEADINGS
        elif active and line.strip().startswith("-"):
            topics.append(line.strip().lstrip("- ").rstrip("."))
    return topics


def propose_edit(text: str, edit: str, summary: list[dict[str, Any]]) -> str:
    if edit == "add_summary_header":
        tldr = " ".join(s["sentence"] for s in summary)
        lines = text.splitlines()
        return "\n".join([lines[0], "", f"> **TL;DR (MuseFlow demo):** {tldr}", *lines[1:]]) + "\n"
    return text.rstrip("\n") + "\n\n> Review note (simulated): reviewed in the MuseFlow AI demo — no issues flagged by the deterministic checks.\n"


@agent_node("document", "document")
def document(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    params = state.get("params") or {}
    scenario = state.get("scenario_id")
    doc_id = "project_requirements" if scenario == "dream_team" else params.get("document_id", "insurance_policy")

    if doc_id == "upload":
        meta = {"id": "upload", "title": params["upload_name"], "type": "Uploaded text (processed locally)",
                "emoji": "📄", "glossary_topic": "general_glossary", "key_fields": None}
        text = params["upload_text"]
    else:
        loaded = tools.call("document.read_fixture", {"document_id": doc_id})
        meta, text = loaded["meta"], loaded["text"]

    result = analyze(text, meta.get("key_fields"))
    output: dict[str, Any] = {
        "kind": "analysis", "document_id": doc_id, "meta": meta, "glossary_topic": meta["glossary_topic"],
        "full_text": text, **result,
        "headline": f"Analyzed “{meta['title']}”: {len(result['fields'])} key fields, {len(result['evidence'])} evidence snippets.",
    }
    updates: dict[str, Any] = {}
    message = f"Extracted {len(result['fields'])} fields and a {len(result['summary'])}-sentence extractive summary."

    if scenario == "interview_prep":
        output["skill_topics"] = skill_topics(text)
        message += f" Found {len(output['skill_topics'])} skill/responsibility bullets."
    if scenario == "document_edit":
        new_text = propose_edit(text, params["edit"], result["summary"])
        diff = list(difflib.unified_diff(text.splitlines(), new_text.splitlines(), "original", "proposed", lineterm="", n=1))
        output["diff"] = diff
        updates["action"] = {
            "tool": "document.simulate_modify", "agent": "document",
            "summary": f"Apply a '{params['edit'].replace('_', ' ')}' redline to the session copy of “{meta['title']}”.",
            "args": {"document_id": doc_id, "new_text": new_text},
        }
        output["headline"] = f"Proposed a redline for “{meta['title']}” ({len(diff)} diff lines)."
        message = "Prepared a deterministic redline and proposed document.simulate_modify."
    return AgentResult(output=output, message=message, updates=updates)
