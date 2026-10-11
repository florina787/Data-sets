"""Integration tests: real LangGraph runs, routing, state transitions and traces."""
from __future__ import annotations

import pytest

from services import scenario_loader as fixtures
from services.tool_registry import ToolRegistry, ToolSpec
from tests.conftest import nodes
from workflows.graph import build_graph, graph_topology
from workflows.routing import classify_intent

EXPECTED_ROUTES = {
    "interview_prep": ["intent_router", "planning", "research", "document", "governance", "audit", "respond"],
    "weekly_planning": ["intent_router", "memory", "calendar", "planning", "governance", "audit", "respond"],
    "research": ["intent_router", "research", "analytics", "audit", "respond"],
    "document_analysis": ["intent_router", "document", "research", "governance", "audit", "respond"],
    "personal_memory": ["intent_router", "memory", "audit", "respond"],
    "project_planning": ["intent_router", "planning", "analytics", "governance", "audit", "respond"],
    "memory_recall": ["intent_router", "memory", "audit", "respond"],
}
APPROVAL_ROUTES = {
    "email_followup": ["intent_router", "email", "governance"],
    "travel_planning": ["intent_router", "research", "planning", "calendar", "governance"],
    "browser": ["intent_router", "browser", "governance"],
    "schedule_meeting": ["intent_router", "calendar", "governance"],
    "document_edit": ["intent_router", "document", "governance"],
    "dream_team": ["intent_router", "planning", "research", "calendar", "email", "analytics", "governance"],
}


def test_graph_is_a_real_stategraph_with_expected_nodes():
    graph = build_graph()
    assert type(graph).__name__ == "CompiledStateGraph"
    topology = graph_topology()
    for node in ["intent_router", "supervisor", "respond", "planning", "research", "memory", "email", "calendar",
                 "document", "browser", "analytics", "governance", "approval", "simulate_action", "audit"]:
        assert node in topology["nodes"]
    conditional = {(s, t) for s, t, c in topology["edges"] if c}
    assert ("supervisor", "approval") in conditional and ("supervisor", "respond") in conditional


@pytest.mark.parametrize("scenario_id,expected", EXPECTED_ROUTES.items())
def test_read_only_scenarios_complete_with_expected_route(engine, scenario_id, expected):
    run = engine.start(scenario_id)
    assert run.status == "completed", run.values.get("errors")
    assert nodes(run) == expected
    assert run.final_response


@pytest.mark.parametrize("scenario_id,before", APPROVAL_ROUTES.items())
def test_consequential_scenarios_pause_then_complete(engine, scenario_id, before):
    run = engine.start(scenario_id)
    assert run.status == "awaiting_approval"
    assert nodes(run) == before
    assert run.pending["tool"] == run.values["action"]["tool"]
    run = engine.resume(run.run_id, "approved")
    assert run.status == "completed"
    assert nodes(run) == before + ["approval", "simulate_action", "audit", "respond"]
    assert run.values["action_result"]["simulated"] is True


def test_ten_required_scenarios_exist_and_run(engine):
    required = ["interview_prep", "email_followup", "weekly_planning", "research", "document_analysis",
                "travel_planning", "browser", "personal_memory", "project_planning", "dream_team"]
    for scenario_id in required:
        run = engine.start(scenario_id)
        if run.status == "awaiting_approval":
            run = engine.resume(run.run_id, "approved")
        assert run.status == "completed", (scenario_id, run.values.get("errors"))


def test_conditional_edge_research_analytics_only_with_matrix(engine):
    assert "analytics" in nodes(engine.start("research", {"topic": "architectures"}))
    assert "analytics" not in nodes(engine.start("research", {"topic": "industry"}))


def test_conditional_routing_dream_team_depends_on_goals(engine):
    read_only = engine.start("dream_team", {"goals": ["research", "analytics"]})
    assert read_only.status == "completed"
    assert nodes(read_only) == ["intent_router", "planning", "research", "analytics", "governance", "audit", "respond"]
    with_email = engine.start("dream_team", {"goals": ["email", "memory"]})
    assert with_email.status == "awaiting_approval"
    assert nodes(with_email) == ["intent_router", "planning", "memory", "email", "governance"]


def test_project_planning_execute_flag_requires_approval(engine):
    assert engine.start("project_planning", {"execute": False}).status == "completed"
    run = engine.start("project_planning", {"execute": True, "plan_template": "presentation"})
    assert run.status == "awaiting_approval"
    engine.resume(run.run_id, "approved")
    assert len(engine.stores.task_board) == 6


def test_trace_matches_execution(engine):
    run = engine.resume(engine.start("email_followup").run_id, "approved")
    seqs = [e["seq"] for e in run.trace]
    assert seqs == list(range(1, len(seqs) + 1))
    known = set(graph_topology()["nodes"])
    assert all(e["node"] in known for e in run.trace)
    routes = [e for e in run.trace if e["kind"] == "route"]
    agent_nodes = [e["node"] for e in run.trace if e["kind"] == "agent"]
    # every agent node except the first and 'respond' is preceded by a supervisor routing decision to it
    for prev, event in zip(run.trace, run.trace[1:]):
        if event["kind"] == "agent" and event["node"] != "intent_router":
            assert prev["kind"] == "route" and prev["message"].startswith(f"→ {event['node']}")
    assert len(routes) == len(agent_nodes) - 1
    assert all(e["duration_ms"] >= 0 for e in run.trace)


def test_tool_calls_are_recorded(engine):
    run = engine.start("document_analysis", {"document_id": "tech_spec"})
    doc_event = next(e for e in run.agent_events if e["node"] == "document")
    assert [c["tool"] for c in doc_event["tool_calls"]] == ["document.read_fixture"]
    assert doc_event["tool_calls"][0]["ok"] is True


def test_retry_simulation(engine):
    run = engine.start("browser", {"task": "booking"})
    browser_events = [e for e in run.agent_events if e["node"] == "browser"]
    assert [e["status"] for e in browser_events] == ["retrying", "completed"]
    assert run.outputs["browser"]["attempts"] == 2


def test_error_handling_records_failure_and_still_audits():
    from services.demo_engine import DemoEngine
    from tests.conftest import FIXED_TODAY

    registry = ToolRegistry()

    def boom(env, args):
        raise RuntimeError("fixture store unavailable")

    registry.specs["research.lookup_fixture"] = ToolSpec("research.lookup_fixture", "research", "broken", False, boom)
    engine = DemoEngine("err", tools=registry, today=FIXED_TODAY)
    run = engine.start("research")
    assert run.status == "error"
    assert nodes(run) == ["intent_router", "audit", "respond"]
    assert any("fixture store unavailable" in e for e in run.values["errors"])
    assert "went wrong" in run.final_response
    assert engine.audit.verify()


def test_unsupported_request_routes_straight_to_response(engine):
    run = engine.start(request="Compose a sonnet about quantum tax law in Klingon")
    assert run.status == "unsupported"
    assert nodes(run) == ["intent_router", "respond"]


@pytest.mark.parametrize("text,intent,scenario", [
    ("Help me plan a productive week.", "calendar_planning", "weekly_planning"),
    ("Draft a professional follow-up email.", "email", "email_followup"),
    ("Compare LangGraph and CrewAI.", "research", "research"),
    ("Prepare me for a technical interview.", "interview", "interview_prep"),
    ("Remember that I love jasmine tea", "memory_add", "personal_memory"),
    ("What do you remember about tea?", "memory_recall", "memory_recall"),
    ("Launch my AI dream team.", "agent_orchestration", "dream_team"),
    ("Plan a weekend getaway", "travel", "travel_planning"),
    ("Book the hotel for me", "browser", "browser"),
    ("Analyze the sample insurance policy.", "document", "document_analysis"),
    ("Organize my project", "task_planning", "project_planning"),
    ("Schedule a meeting with my mentor", "calendar", "schedule_meeting"),
    ("hello", "greeting", None),
    ("help", "help", None),
    ("What's the status of my workflows?", "workflow_status", None),
    ("open the memory garden", "navigation", None),
    ("Write me a symphony", "unsupported", None),
])
def test_intent_classification(text, intent, scenario):
    match = classify_intent(text)
    assert (match.intent, match.scenario_id) == (intent, scenario)


def test_chat_request_runs_through_graph(engine):
    run = engine.start(request="Help me plan a productive week.")
    assert run.values["scenario_id"] == "weekly_planning"
    assert run.status == "completed"
    assert run.outputs["planning"]["blocks"]


def test_weekly_plan_uses_memory_preference(engine):
    engine.stores.memory.add("Preferences", "I focus best in the afternoon")
    run = engine.start("weekly_planning")
    assert run.outputs["memory"]["signals"]["time_of_day"] == "afternoon"
    deep = [b for b in run.outputs["planning"]["blocks"] if b["label"] == "Deep work"]
    assert deep and all(b["start"] >= "12:00" for b in deep)


def test_schedule_meeting_conflict_suggests_free_slot(engine):
    # Wednesday 10:00 clashes with the fictional client sync (10:00-11:00)
    run = engine.start("schedule_meeting", {"title": "Planning chat", "day_offset": 2, "start": "10:00", "duration_min": 30})
    cal = run.outputs["calendar"]
    assert cal["rescheduled"] and cal["conflicts"][0]["title"].startswith("Client sync")
    assert cal["proposed"]["start"] == "11:00"
    engine.resume(run.run_id, "approved")
    assert engine.stores.calendar_events[-1]["title"] == "Planning chat"


def test_supervisor_inserts_governance_when_action_appears(engine):
    # personal_memory has no governance step; inject an action via a patched memory agent result
    from agents import memory as memory_mod
    from agents.base import AgentResult

    original = memory_mod.memory
    try:
        def fake(state, ctx, tools):
            return AgentResult(output={"headline": "x"}, updates={"action": {"tool": "email.simulate_send", "agent": "memory",
                               "summary": "s", "args": {"to": "a@example.com", "subject": "s", "body": "b"}}})
        import workflows.graph as graph_mod
        wrapped = memory_mod.agent_node("memory", "memory")(fake)
        graph_mod.NODE_FUNCTIONS["memory"] = wrapped
        engine.rebuild_graph()
        run = engine.start("personal_memory")
        assert nodes(run) == ["intent_router", "memory", "governance"]
        assert run.status == "awaiting_approval"
        assert any("inserted governance" in e["message"] for e in run.trace if e["kind"] == "route")
    finally:
        graph_mod.NODE_FUNCTIONS["memory"] = original


def test_fixture_scenarios_all_validate(engine):
    for spec in fixtures.list_scenarios():
        run = engine.start(spec.id)
        assert run.status in {"completed", "awaiting_approval"}, (spec.id, run.values.get("errors"))
