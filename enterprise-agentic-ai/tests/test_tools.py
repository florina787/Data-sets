"""Enterprise tools and the MCP-ready registry."""

from __future__ import annotations


def test_registry_lists_mcp_descriptors(demo_container) -> None:
    descriptors = demo_container.tools.describe()
    names = {d["name"] for d in descriptors}
    assert {"get_project_status", "get_open_issues", "search_employee_directory", "get_delivery_metrics"} <= names
    for d in descriptors:
        assert d["description"]
        assert d["inputSchema"]["type"] == "object"


def test_get_project_status(demo_container) -> None:
    record = demo_container.tools.execute("get_project_status", {"project_id": "prj-phoenix"})
    assert record.success
    assert record.result["status"] == "AMBER"
    assert record.result["release_blocker_count"] == 3
    assert record.duration_ms >= 0


def test_get_open_issues_blockers_for_release(demo_container) -> None:
    record = demo_container.tools.execute("get_open_issues", {"blocking_only": True, "release": "2026.10"})
    ids = [i["issue_id"] for i in record.result["issues"]]
    assert ids == ["PHX-214", "PHX-221", "PHX-230"]


def test_closed_issues_excluded(demo_container) -> None:
    record = demo_container.tools.execute("get_open_issues", {"project_id": "PRJ-PHOENIX"})
    assert "PHX-198" not in {i["issue_id"] for i in record.result["issues"]}


def test_search_employee_directory(demo_container) -> None:
    record = demo_container.tools.execute("search_employee_directory", {"query": "SSO identity engineer"})
    assert record.result["results"][0]["name"] == "Tomas Lindqvist"
    assert "manager_id" not in record.result["results"][0]


def test_delivery_metrics_breaches(demo_container) -> None:
    result = demo_container.tools.execute("get_delivery_metrics", {"project_id": "PRJ-PHOENIX"}).result
    breached = {b["metric"] for b in result["target_breaches"]}
    assert {"test_coverage_pct", "change_failure_rate_pct", "sprint_predictability_pct"} <= breached
    assert result["velocity_trend"]["peak_points"] == 47
    assert result["velocity_trend"]["latest_points"] == 38


def test_unknown_project_is_reported_not_raised(demo_container) -> None:
    record = demo_container.tools.execute("get_project_status", {"project_id": "PRJ-NOPE"})
    assert not record.success
    assert "Unknown project" in (record.error or "")


def test_invalid_arguments_and_unknown_tool(demo_container) -> None:
    assert not demo_container.tools.execute("search_employee_directory", {"query": ""}).success
    assert not demo_container.tools.execute("delete_everything", {}).success


def test_langchain_tool_export(demo_container) -> None:
    tools = {t.name: t for t in demo_container.tools.as_langchain_tools()}
    assert tools["get_project_status"].invoke({"project_id": "PRJ-ATLAS"})["status"] == "GREEN"
