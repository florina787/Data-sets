"""SDLC endpoints: requirements, policy, impact, architecture, tests, release, workflow."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import (
    DeployIn,
    PolicySearchIn,
    PolicyUploadIn,
    ReleaseAssessIn,
    RequirementIn,
    TestsIn,
    TextIn,
    WorkflowIn,
)
from app.services.platform import get_platform
from app.utils.serialize import to_jsonable

router = APIRouter(tags=["sdlc"])


def _wf_view(state: dict) -> dict:
    keys = ["request_id", "status", "workflow", "halted_reason", "requirement", "policy", "ambiguity", "impact",
            "architecture", "development_plan", "tests", "simulation", "security", "governance", "release_risk",
            "release_assessment", "release", "production", "anomaly", "root_cause", "release_correlation",
            "remediation", "regression", "defect", "feedback", "summary", "observability", "trace", "errors"]
    out = {k: state.get(k) for k in keys if state.get(k) is not None}
    if "anomaly" in out:
        out["anomaly"] = {**out["anomaly"], "anomalies": out["anomaly"]["anomalies"][:8]}
    return to_jsonable(out)


@router.post("/requirements/analyze")
def analyze_requirement(body: RequirementIn) -> dict:
    req = get_platform().analyze_requirement(body.text, body.clarifications)
    return to_jsonable({"requirement": req, "blocking_ambiguities": [a.ambiguity_id for a in req.blocking_ambiguities],
                        "method": "DETERMINISTIC parser + templates"})


@router.post("/policy/search")
def policy_search(body: PolicySearchIn) -> dict:
    return to_jsonable(get_platform().search_policy(body.query, body.top_k))


@router.post("/policy/upload")
def policy_upload(body: PolicyUploadIn) -> dict:
    return to_jsonable(get_platform().upload_policy(body.filename, body.content.encode("utf-8")))


@router.post("/impact/analyze")
def impact(body: TextIn) -> dict:
    return to_jsonable(get_platform().analyze_impact(body.text, body.clarifications))


@router.post("/architecture/recommend")
def architecture(body: TextIn) -> dict:
    return to_jsonable(get_platform().recommend_architecture(body.text))


@router.post("/tests/generate")
def tests_generate(body: TestsIn) -> dict:
    return to_jsonable(get_platform().generate_tests(body.text, body.clarifications, body.ruleset_id))


@router.post("/release/assess")
def release_assess(body: ReleaseAssessIn) -> dict:
    st = get_platform().run_workflow(body.text, persona=body.persona, clarifications=body.clarifications,
                                     stop_after="human_approval", n_claims=body.n_claims)
    return _wf_view(st)


@router.post("/release/deploy-simulated")
def release_deploy(body: DeployIn) -> dict:
    p = get_platform()
    p.reset_production()
    st = p.run_workflow(body.text, persona=body.persona, clarifications=body.clarifications,
                        approval=body.approval.model_dump(), stop_after="simulated_release",
                        inject_defect=body.inject_defect, n_claims=body.n_claims)
    return _wf_view(st)


@router.post("/workflow/run")
def workflow_run(body: WorkflowIn) -> dict:
    p = get_platform()
    if body.approval is not None:
        p.reset_production()
    st = p.run_workflow(body.text, persona=body.persona, clarifications=body.clarifications,
                        approval=body.approval.model_dump() if body.approval else None, stop_after=body.stop_after,
                        inject_defect=body.inject_defect, n_claims=body.n_claims)
    return _wf_view(st)
