"""Exact analytical answers on the hand-built fixture (expected values computed by hand in build_fixture.py)."""

import pytest

from app.analytics.query_registry import OperationError, run_operation
from app.analytics.time_windows import resolve_window
from app.schemas.analysis import Scope
from tests.fixtures.build_fixture import EXPECTED


@pytest.fixture()
def feb(db):
    return Scope(window=resolve_window(db, "original", {"type": "last_month"}))


def m(result, metric_id):
    return result.metric(metric_id).value


def test_rank_negative_topics_counts_ranks_and_denominators(db, feb):
    r = run_operation(db, "rank_negative_topics", feb, {"top_n": 5})
    assert m(r, "conversations_in_scope") == EXPECTED["feb_conversations"]
    assert m(r, "negative_conversations") == EXPECTED["feb_negative"]
    assert [row["name"] for row in r.table.rows] == EXPECTED["feb_ranking_by_count"]
    dup = r.table.rows[0]
    assert (dup["negative"], dup["conversations"]) == (EXPECTED["feb_duplicate_negative"], EXPECTED["feb_duplicate_conversations"])
    assert dup["negative_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert dup["share_of_negative"] == pytest.approx(0.5)
    assert [row["rank"] for row in r.table.rows] == [1, 2, 3, 4, 5]
    groups = r.series["all_groups"].rows
    assert sum(g["conversations"] for g in groups) == 7 and sum(g["negative"] for g in groups) == 4
    assert set(r.evidence_refs) <= {"C0000001", "C0000003", "C0000006", "C0000007"}


def test_rank_by_rate_and_dimension(db, feb):
    r = run_operation(db, "rank_negative_topics", feb, {"rank_by": "rate", "min_conversations": 1})
    assert r.table.rows[0]["negative_rate"] == 1.0
    p = run_operation(db, "rank_negative_topics", feb, {"dimension": "domain"})
    assert p.table.rows[0]["name"] == "Financial services"


def test_date_filter_excludes_january(db, feb):
    r = run_operation(db, "list_conversations", feb, {"limit": 50})
    ids = {row["conversation_id"] for row in r.table.rows}
    assert ids == {f"C000000{i}" for i in range(1, 8)}


def test_coaching_agent_metrics_and_sample_size_gate(db):
    r = run_operation(db, "agent_coaching_review", Scope(), {"min_conversations": 3})
    agents = {a["agent_id"]: a for a in r.series["agents"].rows}
    assert set(agents) == {"AgentAAAA", "AgentBBBB"}
    for aid, exp in EXPECTED["coaching_all"].items():
        assert (agents[aid]["negative_turns"], agents[aid]["empathic_replies"]) == (exp["negative_turns"], exp["empathic_replies"])
    assert r.series["agents"].rows[0]["agent_id"] == EXPECTED["coaching_top_agent"]
    assert any("Decision support" in n for n in r.uncertainty_notes)
    feb_only = run_operation(db, "agent_coaching_review", Scope(window=resolve_window(db, "original", {"type": "last_month"})), {"min_conversations": 3})
    assert m(feb_only, "eligible_agents") == 1  # only AgentAAAA has 3 conversations in February
    strict = run_operation(db, "agent_coaching_review", Scope(), {"min_conversations": 10})
    assert m(strict, "eligible_agents") == 0 and "No agent has 10 or more" in strict.uncertainty_notes[0]


def test_sentiment_trajectory_turning_points_follow_turn_order(db):
    r = run_operation(db, "sentiment_trajectory", Scope(), {"conversation_id": "C0000002"})
    assert [t["turn_index"] for t in r.series["turning_points"].rows] == EXPECTED["trajectory_C0000002_turning_points"]
    assert m(r, "first_followup_score") == -1.0 and m(r, "final_score") == 1.0 and m(r, "net_change") == 2.0
    tp = r.series["turning_points"].rows[0]
    assert tp["direction"] == "improved" and tp["preceding_agent_text"].startswith("I understand")


def test_trajectory_without_selection_suggests_conversations(db):
    r = run_operation(db, "sentiment_trajectory", Scope(), {})
    assert r.status == "insufficient_data" and r.table.rows


def test_trajectory_unknown_conversation(db):
    assert run_operation(db, "sentiment_trajectory", Scope(), {"conversation_id": "C9999999"}).status == "insufficient_data"


def test_leadership_priorities_are_transparent_and_consistent(db):
    r = run_operation(db, "leadership_priorities", Scope(), {"top_n": 3})
    rows = r.table.rows
    assert sum(r.params["weights"].values()) == pytest.approx(1.0)
    assert all(rows[i]["priority_score"] >= rows[i + 1]["priority_score"] for i in range(len(rows) - 1))
    assert sum(x["conversations"] for x in rows) == m(r, "conversations_in_scope") == 11
    contrib = sum(rows[0][f"contrib_{k}"] for k in r.params["weights"])
    assert contrib == pytest.approx(rows[0]["priority_score"], abs=0.2)
    recs = r.series["recommendations"].rows
    assert len(recs) == 3 and all(x["decision_owner"] and x["suggested_action"] and x["evidence"] is not None for x in recs)
    assert len(r.series["sensitivity"].rows) == 13
    assert any("Financial impact" in n for n in r.uncertainty_notes)


def test_custom_weights_change_ranking_inputs(db):
    r = run_operation(db, "leadership_priorities", Scope(), {"weights": {"frequency": 1.0, "negative_rate": 0, "escalation_rate": 0,
                                                                          "unresolved_rate": 0, "resolution_misfit_rate": 0, "trend": 0}})
    assert r.table.rows[0]["name"] == "Duplicate charge"  # largest volume (3)


def test_compare_topics_and_distribution(db):
    r = run_operation(db, "compare_topics", Scope(), {"topics": ["duplicate_charge", "coupon_not_applied"]})
    assert r.table.rows[0]["name"] == "Duplicate charge"
    d = run_operation(db, "sentiment_distribution", Scope(), {"group_by": "topic"})
    assert sum(x["conversations"] for x in d.table.rows) == 11


def test_registry_rejects_unknown_ops_and_bad_args(db):
    with pytest.raises(OperationError):
        run_operation(db, "drop_table", Scope(), {})
    with pytest.raises(OperationError):
        run_operation(db, "rank_negative_topics", Scope(), {"top_n": 500})
    with pytest.raises(OperationError):
        run_operation(db, "rank_negative_topics", Scope(), {"dimension": "1; DROP TABLE conversations"})


def test_sql_injection_in_filter_values_is_inert(db):
    s = Scope(topics=["duplicate_charge' OR '1'='1"])
    assert run_operation(db, "list_conversations", s, {}).metric("conversations_in_scope").value == 0
