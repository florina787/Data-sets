"""Claims endpoints: synthetic generation, deterministic adjudication, simulation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import AdjudicateIn, ClaimsGenerateIn, SimulationIn
from app.services.platform import get_platform
from app.utils.serialize import to_jsonable

router = APIRouter(tags=["claims"])


@router.post("/claims/generate")
def claims_generate(body: ClaimsGenerateIn) -> dict:
    return to_jsonable(get_platform().generate_claims(body.n_claims, body.seed, body.sample))


@router.post("/claims/adjudicate")
def claims_adjudicate(body: AdjudicateIn) -> dict:
    return to_jsonable(get_platform().adjudicate(body.claim, body.context, body.ruleset_id))


@router.post("/simulation/run")
def simulation_run(body: SimulationIn) -> dict:
    run = get_platform().run_simulation(body.text, body.clarifications or None,
                                        current_ruleset_id=body.current_ruleset_id,
                                        proposed_ruleset_id=body.proposed_ruleset_id,
                                        n_claims=body.n_claims, seed=body.seed)
    return to_jsonable(run.result)


@router.get("/rulesets")
def rulesets() -> dict:
    return to_jsonable(get_platform().ruleset_info())
