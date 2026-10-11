"""Versioned action catalog. Values are configurable synthetic rules."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from ..config import get_settings


@dataclass(frozen=True)
class ActionSpec:
    action_type: str
    label: str
    classification: str  # read | write
    mvp_behavior: str  # executable | proposal_only | disabled
    risk: str
    approver_roles: tuple[str, ...]
    executor_roles: tuple[str, ...]
    separation_of_duties: bool
    evidence_requirements: tuple[str, ...]
    connector: str
    description: str
    forbidden_when: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Catalog:
    version: str
    effective_date: str
    actions: dict[str, ActionSpec]


@lru_cache
def load_catalog() -> Catalog:
    path = get_settings().data_dir / "synthetic" / "action_catalog.json"
    raw = json.loads(path.read_text())
    actions = {}
    for a in raw["actions"]:
        actions[a["action_type"]] = ActionSpec(
            action_type=a["action_type"], label=a["label"], classification=a["classification"],
            mvp_behavior=a["mvp_behavior"], risk=a["risk"],
            approver_roles=tuple(a["approver_roles"]), executor_roles=tuple(a["executor_roles"]),
            separation_of_duties=a["separation_of_duties"],
            evidence_requirements=tuple(a["evidence_requirements"]), connector=a["connector"],
            description=a["description"], forbidden_when=tuple(a.get("forbidden_when", [])),
        )
    return Catalog(version=raw["version"], effective_date=raw["effective_date"], actions=actions)
