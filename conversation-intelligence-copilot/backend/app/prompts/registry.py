"""Versioned prompt registry backed by JSON files in prompts/versions/.

Lifecycle: draft -> test -> review -> active -> deprecated. In this prototype the
lifecycle is a status field on versioned files changed by pull request; there is
no in-app approval workflow.
"""

from __future__ import annotations

import json
import string
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

VERSIONS_DIR = Path(__file__).parent / "versions"
STATUSES = ["draft", "test", "review", "active", "deprecated"]


@dataclass
class PromptVersion:
    id: str
    name: str
    purpose: str
    version: str
    status: str
    owner: str
    created_at: str
    system: str
    user_template: str
    input_variables: list[str]
    output_schema: str | None
    model_config: dict
    test_cases: list[dict] = field(default_factory=list)
    changelog: str = ""

    def render(self, **variables) -> str:
        missing = set(self.input_variables) - variables.keys()
        if missing:
            raise KeyError(f"Prompt {self.id}@{self.version} missing variables: {sorted(missing)}")
        return string.Template(self.user_template).substitute(**variables)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@lru_cache
def load_all() -> dict[str, list[PromptVersion]]:
    prompts: dict[str, list[PromptVersion]] = {}
    for f in sorted(VERSIONS_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        if data["status"] not in STATUSES:
            raise ValueError(f"{f.name}: invalid status {data['status']}")
        prompts.setdefault(data["id"], []).append(PromptVersion(**data))
    for versions in prompts.values():
        versions.sort(key=lambda p: [int(x) for x in p.version.split(".")])
    return prompts


def get_prompt(prompt_id: str, version: str | None = None) -> PromptVersion:
    versions = load_all().get(prompt_id)
    if not versions:
        raise KeyError(f"Unknown prompt {prompt_id}")
    if version:
        return next(p for p in versions if p.version == version)
    active = [p for p in versions if p.status == "active"]
    if not active:
        raise KeyError(f"Prompt {prompt_id} has no active version")
    return active[-1]
