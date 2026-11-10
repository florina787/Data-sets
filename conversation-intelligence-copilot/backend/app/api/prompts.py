"""Prompt library endpoints (read-only; lifecycle changes are made by pull request)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.observability.store import get_telemetry
from app.prompts.registry import STATUSES, load_all

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


def _usage() -> dict:
    rows = get_telemetry()._all("""SELECT prompt_id, prompt_version, COUNT(*) calls, SUM(status='ok') ok, SUM(cache_hit) cache_hits,
                                   AVG(latency_ms) avg_ms, SUM(total_tokens) tokens FROM llm_calls GROUP BY 1, 2""")
    return {(r["prompt_id"], r["prompt_version"]): r for r in rows}


@router.get("")
def list_prompts() -> dict:
    usage = _usage()
    evals_file = get_settings().manifests_dir / "evaluation_results.json"
    evals = json.loads(evals_file.read_text()).get("prompt_evaluations", {}) if evals_file.exists() else {}
    out = []
    for pid, versions in load_all().items():
        for v in versions:
            d = v.to_dict()
            d["usage"] = usage.get((pid, v.version))
            d["evaluation"] = evals.get(pid)
            out.append(d)
    return {"statuses": STATUSES, "prompts": out}


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str) -> list[dict]:
    versions = load_all().get(prompt_id)
    if not versions:
        raise HTTPException(404, "Prompt not found")
    return [v.to_dict() for v in versions]
