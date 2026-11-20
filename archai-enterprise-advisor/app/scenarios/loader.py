"""Load the fictional demo scenarios shipped in ``scenarios/``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.settings import SCENARIOS_DIR
from app.models.inputs import AssessmentRequest


class ScenarioNotFound(KeyError):
    """Raised when a scenario id does not exist."""


@lru_cache(maxsize=1)
def _load_all(directory: str = str(SCENARIOS_DIR)) -> tuple[dict[str, Any], ...]:
    items = []
    for path in sorted(Path(directory).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        AssessmentRequest.model_validate(data["request"])  # fail fast on bad scenario files
        items.append(data)
    return tuple(sorted(items, key=lambda d: d.get("order", 0)))


def list_scenarios() -> list[dict[str, Any]]:
    """Scenario metadata (without the full request payload)."""
    return [
        {k: s[k] for k in ("id", "name", "company", "industry", "summary", "expected", "disclaimer")}
        for s in _load_all()
    ]


def get_scenario(scenario_id: str) -> dict[str, Any]:
    for s in _load_all():
        if s["id"] == scenario_id:
            return s
    raise ScenarioNotFound(scenario_id)


def scenario_request(scenario_id: str) -> AssessmentRequest:
    """A fresh, validated request for a scenario (safe to mutate)."""
    data = get_scenario(scenario_id)
    req = AssessmentRequest.model_validate(data["request"])
    req.scenario_id = scenario_id
    return req
