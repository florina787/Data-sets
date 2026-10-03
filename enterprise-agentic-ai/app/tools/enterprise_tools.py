"""Demo enterprise tools with typed inputs and an MCP-ready registry.

Each tool is a plain function with a Pydantic input model. The registry can:

* execute a tool by name with validated arguments (used by the Tool Agent),
* describe tools as ``{name, description, inputSchema}`` (the shape MCP uses),
* export LangChain ``StructuredTool`` objects for tool-calling LLMs.

Exposing them through an MCP server later only requires iterating the registry.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, ValidationError

from app.models.domain import ToolCallRecord
from app.tools.repository import EnterpriseDataRepository

logger = logging.getLogger(__name__)


class ToolExecutionError(RuntimeError):
    """Raised by a tool for expected, user-facing failures (e.g. unknown project)."""


# --- Input schemas ---------------------------------------------------------


class ProjectInput(BaseModel):
    project_id: str = Field(description="Project identifier, e.g. PRJ-PHOENIX.")


class OpenIssuesInput(BaseModel):
    project_id: str | None = Field(default=None, description="Project identifier; omit for all projects.")
    blocking_only: bool = Field(default=False, description="Only return release-blocking issues.")
    release: str | None = Field(default=None, description="Filter by target release, e.g. 2026.10.")


class EmployeeSearchInput(BaseModel):
    query: str = Field(min_length=2, description="Name, role, team, skill or project to search for.")
    limit: int = Field(default=5, ge=1, le=20)


class NoInput(BaseModel):
    pass


# --- Tool implementations ----------------------------------------------------


class EnterpriseTools:
    """Tool implementations bound to a data repository (dependency-injected)."""

    def __init__(self, repo: EnterpriseDataRepository) -> None:
        self._repo = repo

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self._repo.get_project(project_id)
        if project is None:
            known = ", ".join(p["project_id"] for p in self._repo.projects)
            raise ToolExecutionError(f"Unknown project '{project_id}'. Known projects: {known}")
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects with their RAG status."""
        return [
            {"project_id": p["project_id"], "name": p["name"], "status": p["status"], "target_release": p["target_release"]}
            for p in self._repo.projects
        ]

    def get_project_status(self, project_id: str) -> dict[str, Any]:
        """Current status, completion, dates, budget and owner of a project."""
        p = self._require_project(project_id)
        owner = self._repo.get_employee(p.get("owner_employee_id"))
        open_issues = [i for i in self._repo.issues if i["project_id"] == p["project_id"] and i["status"] != "Closed"]
        return {
            "project_id": p["project_id"],
            "name": p["name"],
            "status": p["status"],
            "percent_complete": p["percent_complete"],
            "target_release": p["target_release"],
            "release_date": p["release_date"],
            "code_freeze_date": p["code_freeze_date"],
            "budget_usd": p["budget_usd"],
            "spend_to_date_usd": p["spend_to_date_usd"],
            "budget_consumed_pct": round(100 * p["spend_to_date_usd"] / p["budget_usd"]),
            "owner": f"{owner['name']} ({owner['title']})" if owner else None,
            "open_issue_count": len(open_issues),
            "release_blocker_count": sum(1 for i in open_issues if i["release_blocker"]),
            "health_summary": p["health_summary"],
            "last_updated": p["last_updated"],
        }

    def get_open_issues(
        self, project_id: str | None = None, blocking_only: bool = False, release: str | None = None
    ) -> dict[str, Any]:
        """Open (not closed) issues, optionally filtered by project, blocker flag and release."""
        if project_id:
            self._require_project(project_id)
        issues = [
            i
            for i in self._repo.issues
            if i["status"] != "Closed"
            and (project_id is None or i["project_id"] == project_id.upper())
            and (not blocking_only or i["release_blocker"])
            and (release is None or i["target_release"] == release)
        ]
        severity_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        issues.sort(key=lambda i: (severity_rank.get(i["severity"], 9), i["issue_id"]))
        out = []
        for issue in issues:
            assignee = self._repo.get_employee(issue.get("assignee_id"))
            out.append(
                {
                    "issue_id": issue["issue_id"],
                    "project_id": issue["project_id"],
                    "title": issue["title"],
                    "severity": issue["severity"],
                    "status": issue["status"],
                    "release_blocker": issue["release_blocker"],
                    "target_release": issue["target_release"],
                    "assignee": assignee["name"] if assignee else None,
                    "opened": issue["opened"],
                    "component": issue["component"],
                }
            )
        return {
            "filters": {"project_id": project_id, "blocking_only": blocking_only, "release": release},
            "count": len(out),
            "issues": out,
        }

    def search_employee_directory(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Find employees by name, title, team, skill or project. Returns work contact details only."""
        from app.rag.text_utils import content_tokens

        terms = content_tokens(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for emp in self._repo.employees:
            project_names = [
                (self._repo.get_project(pid) or {}).get("name", pid) for pid in emp.get("projects", [])
            ]
            fields = {
                "name": emp["name"],
                "title": emp["title"],
                "team": emp["team"],
                "department": emp["department"],
                "skills": " ".join(emp.get("skills", [])),
                "projects": " ".join(project_names),
            }
            weights = {"name": 3.0, "title": 2.0, "team": 1.5, "projects": 1.0, "skills": 1.0, "department": 0.5}
            score = sum(weights[f] * len(terms & content_tokens(v)) for f, v in fields.items())
            if score > 0:
                scored.append((score, emp))
        scored.sort(key=lambda x: (-x[0], x[1]["name"]))
        results = [
            {
                "employee_id": e["employee_id"],
                "name": e["name"],
                "title": e["title"],
                "team": e["team"],
                "department": e["department"],
                "email": e["email"],
                "location": e["location"],
                "projects": e.get("projects", []),
            }
            for _, e in scored[:limit]
        ]
        return {"query": query, "count": len(results), "results": results}

    def get_delivery_metrics(self, project_id: str) -> dict[str, Any]:
        """Sprint velocity, predictability and DORA-style metrics compared with engineering targets."""
        project = self._require_project(project_id)
        metrics = self._repo.get_metrics(project["project_id"])
        if metrics is None:
            raise ToolExecutionError(f"No delivery metrics recorded for {project['project_id']}.")
        targets = self._repo.targets
        sprints = metrics["sprints"]
        predictability = [
            {
                "sprint": s["sprint"],
                "planned_points": s["planned_points"],
                "completed_points": s["completed_points"],
                "predictability_pct": round(100 * s["completed_points"] / s["planned_points"], 1),
            }
            for s in sprints
        ]
        first, last = sprints[0]["completed_points"], sprints[-1]["completed_points"]
        peak = max(s["completed_points"] for s in sprints)
        # (metric, actual, target, higher_is_better)
        checks = [
            ("deployment_frequency_per_week", metrics["deployment_frequency_per_week"], True),
            ("lead_time_days", metrics["lead_time_days"], False),
            ("change_failure_rate_pct", metrics["change_failure_rate_pct"], False),
            ("mttr_hours", metrics["mttr_hours"], False),
            ("test_coverage_pct", metrics["test_coverage_pct"], True),
            ("sprint_predictability_pct", predictability[-1]["predictability_pct"], True),
        ]
        breaches = []
        for name, actual, higher_better in checks:
            target = targets.get(name)
            if target is None:
                continue
            ok = actual >= target if higher_better else actual <= target
            if not ok:
                breaches.append({"metric": name, "actual": actual, "target": target})
        return {
            "project_id": project["project_id"],
            "as_of": metrics["as_of"],
            "sprints": predictability,
            "velocity_trend": {
                "first_sprint_points": first,
                "peak_points": peak,
                "latest_points": last,
                "change_from_peak_pct": round(100 * (last - peak) / peak, 1),
            },
            "deployment_frequency_per_week": metrics["deployment_frequency_per_week"],
            "lead_time_days": metrics["lead_time_days"],
            "change_failure_rate_pct": metrics["change_failure_rate_pct"],
            "mttr_hours": metrics["mttr_hours"],
            "test_coverage_pct": metrics["test_coverage_pct"],
            "unplanned_work_pct": metrics["unplanned_work_pct"],
            "open_defects": metrics["open_defects"],
            "budget_consumed_pct": metrics["budget_consumed_pct"],
            "targets": targets,
            "target_breaches": breaches,
        }


# --- Registry ------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    func: Callable[..., Any]

    def mcp_descriptor(self) -> dict[str, Any]:
        """Tool description in Model Context Protocol shape."""
        return {"name": self.name, "description": self.description, "inputSchema": self.input_model.model_json_schema()}


class ToolRegistry:
    """Named, validated tool execution."""

    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {s.name: s for s in specs}

    @classmethod
    def from_repository(cls, repo: EnterpriseDataRepository) -> "ToolRegistry":
        tools = EnterpriseTools(repo)
        return cls(
            [
                ToolSpec("get_project_status", "Get the current status, completion, dates, budget and owner of a project.", ProjectInput, tools.get_project_status),
                ToolSpec("get_open_issues", "List open issues, optionally only release blockers, for a project and/or release.", OpenIssuesInput, tools.get_open_issues),
                ToolSpec("search_employee_directory", "Search the employee directory by name, role, team, skill or project.", EmployeeSearchInput, tools.search_employee_directory),
                ToolSpec("get_delivery_metrics", "Get sprint velocity, predictability and delivery KPIs versus engineering targets.", ProjectInput, tools.get_delivery_metrics),
                ToolSpec("list_projects", "List all projects with status and target release.", NoInput, tools.list_projects),
            ]
        )

    @property
    def names(self) -> list[str]:
        return list(self._specs)

    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def describe(self) -> list[dict[str, Any]]:
        return [s.mcp_descriptor() for s in self._specs.values()]

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolCallRecord:
        """Validate arguments and run a tool. Never raises: failures are captured in the record."""
        arguments = arguments or {}
        start = time.perf_counter()
        spec = self._specs.get(name)
        if spec is None:
            return ToolCallRecord(tool_name=name, arguments=arguments, success=False, error=f"Unknown tool '{name}'")
        try:
            validated = spec.input_model.model_validate(arguments)
            result = spec.func(**validated.model_dump())
            record = ToolCallRecord(tool_name=name, arguments=validated.model_dump(exclude_none=True), result=result)
        except ValidationError as exc:
            record = ToolCallRecord(tool_name=name, arguments=arguments, success=False, error=f"Invalid arguments: {exc.errors()[0]['msg']}")
        except ToolExecutionError as exc:
            record = ToolCallRecord(tool_name=name, arguments=arguments, success=False, error=str(exc))
        except Exception as exc:  # unexpected bug: log with stack trace, surface type only
            logger.exception("Tool %s failed", name)
            record = ToolCallRecord(tool_name=name, arguments=arguments, success=False, error=f"Internal tool error: {type(exc).__name__}")
        record.duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return record

    def as_langchain_tools(self) -> list[StructuredTool]:
        """LangChain tools (for tool-calling models or an MCP adapter)."""
        return [
            StructuredTool.from_function(func=s.func, name=s.name, description=s.description, args_schema=s.input_model)
            for s in self._specs.values()
        ]
