"""Read-only access to the synthetic enterprise datasets (projects, issues, people, metrics)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
}


class DataRepositoryError(RuntimeError):
    """Raised when synthetic data files are missing or malformed."""


class EnterpriseDataRepository:
    """Loads the JSON datasets once and offers simple lookups.

    In a real deployment this class would be replaced by clients for Jira,
    the HR directory, a PPM tool, etc. The tool layer only depends on this
    interface, so swapping the backend does not change the tools.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self.projects: list[dict[str, Any]] = self._load("projects.json", "projects")
        self.issues: list[dict[str, Any]] = self._load("issues.json", "issues")
        self.employees: list[dict[str, Any]] = self._load("employees.json", "employees")
        metrics_doc = self._load_raw("delivery_metrics.json")
        self.metrics: list[dict[str, Any]] = metrics_doc.get("delivery_metrics", [])
        self.targets: dict[str, float] = metrics_doc.get("engineering_targets", {})

    def _load_raw(self, filename: str) -> dict[str, Any]:
        path = self._data_dir / filename
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise DataRepositoryError(f"Synthetic data file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise DataRepositoryError(f"Invalid JSON in {path}: {exc}") from exc

    def _load(self, filename: str, key: str) -> list[dict[str, Any]]:
        records = self._load_raw(filename).get(key)
        if not isinstance(records, list):
            raise DataRepositoryError(f"{filename} must contain a '{key}' list")
        return records

    # --- lookups -----------------------------------------------------------
    def get_project(self, project_id: str) -> dict[str, Any] | None:
        pid = project_id.strip().upper()
        return next((p for p in self.projects if p["project_id"] == pid), None)

    def get_employee(self, employee_id: str | None) -> dict[str, Any] | None:
        return next((e for e in self.employees if e["employee_id"] == employee_id), None)

    def get_metrics(self, project_id: str) -> dict[str, Any] | None:
        pid = project_id.strip().upper()
        return next((m for m in self.metrics if m["project_id"] == pid), None)

    def match_projects(self, text: str) -> list[str]:
        """Project IDs mentioned in free text by ID, name or alias."""
        lowered = text.lower()
        found: list[str] = []
        for project in self.projects:
            names = [project["project_id"].lower(), project["name"].lower(), *project.get("aliases", [])]
            if any(re.search(rf"\b{re.escape(n)}\b", lowered) for n in names):
                found.append(project["project_id"])
        return found

    def match_release(self, text: str) -> str | None:
        """Release identifier (e.g. '2026.10') referenced by month name or ID in free text."""
        lowered = text.lower()
        explicit = re.search(r"\b(20\d\d)\.(\d\d)\b", lowered)
        if explicit:
            return explicit.group(0)
        for month, number in _MONTHS.items():
            if re.search(rf"\b{month}\b", lowered):
                for project in self.projects:
                    if project.get("release_date", "")[5:7] == number:
                        return project["target_release"]
        return None

    def projects_for_release(self, release: str) -> list[str]:
        return [p["project_id"] for p in self.projects if p.get("target_release") == release]
