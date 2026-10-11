"""Research role (Aurora 🧚): synthetic evidence lookup — never live web results."""
from __future__ import annotations

from typing import Any

from agents.base import AgentResult, agent_node, prior
from services.text_analysis import find_terms
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState

DISCLAIMER = "Demo research — synthetic data, not live web results."
BUDGET_RANK = {"low": 0, "mid": 1, "high": 2}


def _brief(topic_key: str, topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "brief", "topic": topic_key, "title": topic["title"], "objective": topic["objective"],
        "plan": topic["plan"], "evidence": topic["evidence"], "findings": topic["findings"],
        "recommendations": topic["recommendations"], "limitations": topic["limitations"],
        "matrix": topic.get("matrix"), "disclaimer": DISCLAIMER,
    }


def rank_destinations(destinations: list[dict[str, Any]], budget: str, vibe: str) -> list[dict[str, Any]]:
    """Score = vibe match (2) + budget fit (2 if exact, 1 if cheaper) − travel-time penalty."""
    ranked = []
    for dest in destinations:
        score = 2.0 if dest["vibe"] == vibe else 0.0
        diff = BUDGET_RANK[budget] - BUDGET_RANK[dest["budget"]]
        score += 2.0 if diff == 0 else 1.0 if diff > 0 else -1.0
        score -= dest["travel_hours"] * 0.2
        ranked.append({**dest, "score": round(score, 2)})
    return sorted(ranked, key=lambda d: (-d["score"], d["price"], d["id"]))


@agent_node("research", "research")
def research(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    scenario = state.get("scenario_id")
    params = state.get("params") or {}

    if scenario == "travel_planning":
        destinations = tools.call("travel.list_destinations", {})
        ranked = rank_destinations(destinations, params["budget"], params["vibe"])
        best = ranked[0]
        return AgentResult(
            output={"kind": "destinations", "shortlist": ranked[:3], "selected": best, "disclaimer": DISCLAIMER,
                    "headline": f"Shortlisted {min(3, len(ranked))} fictional destinations; best match: {best['name']}."},
            message=f"Ranked {len(ranked)} fictional destinations for a {params['vibe']} {params['budget']}-budget weekend.",
        )

    if scenario == "document_analysis":
        doc = prior(state, "document")
        topic_key = doc.get("glossary_topic", "general_glossary")
        topic = tools.call("research.lookup_fixture", {"topic": topic_key})
        terms = {card["claim"].split(":")[0]: card for card in topic["evidence"]}
        hits = find_terms(doc.get("full_text", ""), list(terms))
        cards = [{**terms[h["term"]], "found_on_line": h["line"]} for h in hits]
        brief = _brief(topic_key, topic) | {"evidence": cards}
        return AgentResult(
            output=brief | {"headline": f"Explained {len(cards)} term(s) found in the document."},
            message=f"Matched {len(cards)} glossary cards to terms in the document.",
        )

    topic_key = {"interview_prep": "interview_tech"}.get(scenario or "", params.get("topic", "ai_strategy"))
    topic = tools.call("research.lookup_fixture", {"topic": topic_key})
    brief = _brief(topic_key, topic)
    return AgentResult(
        output=brief | {"headline": f"{topic['title']}: {len(topic['evidence'])} synthetic evidence cards, {len(topic['findings'])} findings."},
        message=f"Assembled brief '{topic['title']}' from fixtures.",
    )


