"""Adapter to Project B (archai-enterprise-advisor), reused unchanged for AI Investment Intelligence.

Project B lives next to this project in the repository. Its decision engine is imported lazily; if its
dependencies (langgraph, langchain-core, pandas) are not installed, the endpoints report the module as
unavailable instead of failing the whole API.
"""

from __future__ import annotations

import sys
from typing import Any

from florome.config import PACKAGE_DIR

ADVISOR_DIR = PACKAGE_DIR.parents[2] / "archai-enterprise-advisor"


class AdvisorUnavailable(RuntimeError):
    pass


def _load() -> tuple[Any, Any]:
    if not ADVISOR_DIR.is_dir():
        raise AdvisorUnavailable(f"Project B not found at {ADVISOR_DIR}")
    if str(ADVISOR_DIR) not in sys.path:
        sys.path.insert(0, str(ADVISOR_DIR))
    try:
        from app import scenarios, services  # type: ignore[import-not-found]
    except ImportError as exc:
        raise AdvisorUnavailable(f"Project B dependencies not installed: {exc.name}. pip install -r {ADVISOR_DIR}/requirements.txt") from exc
    return scenarios, services


def list_scenarios() -> list[dict[str, Any]]:
    scenarios, _ = _load()
    return scenarios.list_scenarios()


def assess_scenario(scenario_id: str) -> dict[str, Any]:
    scenarios, services = _load()
    result = services.run_assessment(scenarios.scenario_request(scenario_id))
    return result.model_dump(mode="json")
