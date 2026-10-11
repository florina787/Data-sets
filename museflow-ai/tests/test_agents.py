"""Unit tests for the deterministic agent-role logic."""
from __future__ import annotations

from datetime import date

import pytest

from agents.analytics import critical_path, weighted_matrix
from agents.calendar import conflicts, find_slot, free_windows
from agents.document import analyze, propose_edit, skill_topics
from agents.email import compose
from agents.memory import derive_signals
from agents.planning import place_block, schedule_tasks, topological_order
from agents.research import rank_destinations
from services import scenario_loader as fixtures
from services import text_analysis as ta

TASKS = [
    {"id": "A", "title": "a", "hours": 2, "depends_on": [], "agent": "planning"},
    {"id": "B", "title": "b", "hours": 3, "depends_on": ["A"], "agent": "research"},
    {"id": "C", "title": "c", "hours": 1, "depends_on": ["A"], "agent": "research"},
    {"id": "D", "title": "d", "hours": 2, "depends_on": ["B", "C"], "agent": "planning"},
]


def test_topological_order_respects_dependencies():
    order = [t["id"] for t in topological_order(TASKS)]
    assert order == ["A", "B", "C", "D"]


def test_topological_order_detects_cycles_and_unknown_deps():
    with pytest.raises(ValueError, match="cycle"):
        topological_order([{"id": "X", "hours": 1, "depends_on": ["Y"]}, {"id": "Y", "hours": 1, "depends_on": ["X"]}])
    with pytest.raises(ValueError, match="Unknown"):
        topological_order([{"id": "X", "hours": 1, "depends_on": ["Z"]}])


def test_schedule_uses_priority_capacity():
    start = date(2026, 10, 7)
    high = schedule_tasks(TASKS, start, "high")  # 6 h/day → 8 h of work ends day 2
    low = schedule_tasks(TASKS, start, "low")  # 2 h/day → ends day 4
    assert high[-1]["due_date"] == "2026-10-08"
    assert low[-1]["due_date"] == "2026-10-10"
    for task in high:
        for dep in task["depends_on"]:
            assert next(t for t in high if t["id"] == dep)["end_hour"] <= task["start_hour"]


def test_critical_path():
    result = critical_path(topological_order(TASKS))
    assert result["critical_path"] == ["A", "B", "D"]
    assert result["duration_hours"] == 7
    assert next(r for r in result["rows"] if r["id"] == "C")["slack"] == 2


def test_weighted_matrix_ranking():
    matrix = fixtures.research_fixture()["topics"]["ai_frameworks"]["matrix"]
    ranking = weighted_matrix(matrix)
    assert ranking[0]["option"] == "LangGraph"
    assert ranking[0]["score"] == pytest.approx(0.25 * 5 + 0.25 * 5 + 0.2 * 3 + 0.1 * 2 + 0.2 * 5)


def test_rank_destinations_prefers_vibe_and_budget():
    ranked = rank_destinations(fixtures.travel_fixture()["destinations"], "mid", "relaxing")
    assert ranked[0]["id"] == "moonlit_bay"
    assert rank_destinations(fixtures.travel_fixture()["destinations"], "high", "adventurous")[0]["vibe"] == "adventurous"


def test_calendar_free_windows_and_conflicts():
    events = [{"date": "2026-10-07", "start": "09:30", "end": "10:00", "title": "x"},
              {"date": "2026-10-07", "start": "10:00", "end": "11:00", "title": "y"}]
    windows = free_windows(events, "2026-10-07", 8 * 60, 18 * 60)
    assert windows == [{"start_min": 480, "end_min": 570}, {"start_min": 660, "end_min": 1080}]
    assert [c["title"] for c in conflicts(events, "2026-10-07", 9 * 60 + 45, 10 * 60 + 15)] == ["x", "y"]
    day, start = find_slot(events, date(2026, 10, 7), 60, (480, 1080), after_min=570)
    assert (day.isoformat(), start) == ("2026-10-07", 660)


def test_place_block_prefers_morning_or_afternoon():
    windows = [{"start_min": 480, "end_min": 720}, {"start_min": 780, "end_min": 1080}]
    assert place_block(windows, [], 120, prefer_late=False) == (480, 600)
    assert place_block(windows, [], 120, prefer_late=True) == (960, 1080)
    assert place_block(windows, [(480, 720), (780, 1080)], 30, prefer_late=False) is None


@pytest.mark.parametrize("tone", ["professional", "warm", "confident", "friendly", "executive", "concise"])
def test_email_compose_all_tones(tone):
    draft = compose(fixtures.email_fixture(), "interview_follow_up", "hiring_manager", tone)
    assert draft["to"].endswith("@example.com")
    assert "Senior Python Engineer" in draft["subject"]
    assert draft["body"].startswith(fixtures.email_fixture()["tones"][tone]["greeting"].format(first="Jordan"))


def test_document_analysis_extracts_fields_with_lines():
    text = fixtures.get_document_text("insurance_policy")
    meta = fixtures.get_document_meta("insurance_policy")
    result = analyze(text, meta.key_fields)
    fields = {f["field"]: f for f in result["fields"]}
    assert fields["Deductible"]["value"] == "$500"
    assert text.splitlines()[fields["Deductible"]["line"] - 1].startswith("Deductible:")
    assert len(result["summary"]) == 3
    assert all(e["line"] >= 1 for e in result["evidence"])


def test_skill_topics_and_redline():
    topics = skill_topics(fixtures.get_document_text("job_description"))
    assert "5+ years of professional Python experience" in topics
    text = fixtures.get_document_text("meeting_notes")
    assert "Review note (simulated)" in propose_edit(text, "add_review_note", [])
    assert "TL;DR" in propose_edit(text, "add_summary_header", [{"sentence": "S.", "line": 1}])


def test_memory_signals():
    signals = derive_signals([{"text": "I love morning yoga", "category": "Preferences"}, {"text": "Ship v1", "category": "Goals"}])
    assert signals == {"time_of_day": "morning", "wellness": True, "goals": ["Ship v1"]}


def test_text_analysis_entities_and_actions():
    text = fixtures.get_document_text("meeting_notes")
    entities = ta.extract_entities(text)
    assert {"value": "2026-10-06", "line": 3} in entities["dates"]
    actions = ta.extract_action_items(text)
    assert sum(1 for a in actions if a["kind"] == "Action") == 3
