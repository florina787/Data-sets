"""Achievements computed from actual demo-session interactions (no streaks, no nagging)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Achievement:
    key: str
    emoji: str
    title: str
    description: str
    rule: Callable[[dict[str, Any]], bool]


def _completed(stats: dict[str, Any], scenario: str | None = None) -> int:
    return stats["completed_by_scenario"].get(scenario, 0) if scenario else stats["completed"]


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_task", "🌸", "First Task Completed", "Complete any workflow.", lambda s: _completed(s) >= 1),
    Achievement("explorer", "🦄", "Unicorn Explorer", "Visit 8 different areas of MuseFlow.", lambda s: s["pages_visited"] >= 8),
    Achievement("wizard", "✨", "Workflow Wizard", "Complete 5 workflows.", lambda s: _completed(s) >= 5),
    Achievement("email", "💌", "Email Enchantress", "Approve a simulated email send.", lambda s: s["emails_sent"] >= 1),
    Achievement("memory", "🧠", "Memory Keeper", "Plant 3 memories in the garden.", lambda s: s["memories"] >= 3),
    Achievement("architect", "🔮", "Agent Architect", "Complete the AI dream team workflow.", lambda s: _completed(s, "dream_team") >= 1),
    Achievement("automation", "🌈", "Automation Queen", "Approve 3 simulated actions.", lambda s: s["approved"] >= 3),
]
MASTER = Achievement("master", "🏆", "Master of Magic", "Unlock every other achievement.", lambda s: False)


def session_stats(engine: Any, pages_visited: int) -> dict[str, Any]:
    by_scenario: dict[str, int] = {}
    approved = 0
    for run in engine.runs.values():
        if run.status == "completed":
            sid = run.values.get("scenario_id", "")
            by_scenario[sid] = by_scenario.get(sid, 0) + 1
        if (run.values.get("approval") or {}).get("decision") == "approved" and run.status == "completed":
            approved += 1
    return {
        "completed": sum(by_scenario.values()),
        "completed_by_scenario": by_scenario,
        "pages_visited": pages_visited,
        "emails_sent": len(engine.stores.outbox),
        "memories": len(engine.stores.memory),
        "approved": approved,
    }


def evaluate(stats: dict[str, Any]) -> dict[str, bool]:
    unlocked = {a.key: bool(a.rule(stats)) for a in ACHIEVEMENTS}
    unlocked[MASTER.key] = all(unlocked.values())
    return unlocked


def all_achievements() -> list[Achievement]:
    return [*ACHIEVEMENTS, MASTER]
