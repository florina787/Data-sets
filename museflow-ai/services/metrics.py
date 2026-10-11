"""Observability metrics derived from a session's actual run records.

``measured`` values come straight from execution events. ``illustrative`` values are
clearly-labelled estimates built on stated assumptions — never production measurements.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from services import scenario_loader as fixtures

# Assumptions for illustrative estimates (shown in the UI next to every estimate).
CHARS_PER_TOKEN = 4
ILLUSTRATIVE_USD_PER_1K_TOKENS = 0.01
ACTUAL_LLM_TOKENS = 0  # No LLM client exists in this codebase.
ACTUAL_LLM_COST_USD = 0.0


def _runs(engine: Any) -> list[Any]:
    return list(engine.runs.values())


def measured(engine: Any) -> dict[str, Any]:
    runs = _runs(engine)
    events = [e for r in runs for e in r.agent_events]
    statuses = Counter(r.status for r in runs)
    finished = [r for r in runs if r.status in {"completed", "rejected", "cancelled", "error", "denied"}]
    approvals = Counter((r.values.get("approval") or {}).get("decision") for r in runs if r.values.get("approval"))
    failed = sum(1 for e in events if e["status"] in {"failed", "retrying"})
    return {
        "total_runs": len(runs),
        "status_counts": dict(statuses),
        "completed": statuses.get("completed", 0),
        "pending_approvals": statuses.get("awaiting_approval", 0),
        "completion_rate": (statuses.get("completed", 0) / len(finished)) if finished else 0.0,
        "agent_invocations": dict(Counter(e["agent"] for e in events)),
        "node_invocations": dict(Counter(e["node"] for e in events)),
        "tool_calls": sum(len(e.get("tool_calls", [])) for e in events),
        "avg_run_ms": (sum(r.wall_ms for r in runs) / len(runs)) if runs else 0.0,
        "avg_node_ms": (sum(e.get("duration_ms", 0.0) for e in events) / len(events)) if events else 0.0,
        "approval_outcomes": {k: v for k, v in approvals.items() if k},
        "error_events": failed,
        "error_rate": (failed / len(events)) if events else 0.0,
        "active_agents": len({e["agent"] for e in events}),
        "llm_tokens": ACTUAL_LLM_TOKENS,
        "llm_cost_usd": ACTUAL_LLM_COST_USD,
        "memory_entries": len(engine.stores.memory),
        "audit_entries": len(engine.audit),
    }


def illustrative(engine: Any) -> dict[str, Any]:
    runs = _runs(engine)
    chars = sum(len(json.dumps(r.outputs, default=str)) + len(r.final_response) for r in runs)
    tokens = chars // CHARS_PER_TOKEN
    minutes = sum(fixtures.get_scenario(r.values["scenario_id"]).minutes_saved_estimate
                  for r in runs if r.status == "completed" and r.values.get("scenario_id"))
    return {
        "token_equivalents": tokens,
        "cost_avoidance_usd": round(tokens / 1000 * ILLUSTRATIVE_USD_PER_1K_TOKENS, 4),
        "minutes_saved": minutes,
        "assumptions": {
            "chars_per_token": CHARS_PER_TOKEN,
            "usd_per_1k_tokens": ILLUSTRATIVE_USD_PER_1K_TOKENS,
            "minutes_saved": "Per-scenario guesses in data/scenarios/registry.json (minutes_saved_estimate).",
        },
    }
