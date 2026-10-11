"""Approval binding: what an approval or review is bound to. Recomputed from files and records at
check time, so tampering with an artifact, a config, the policy or the dataset invalidates it."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import ChangeRequest, CodeRevision
from app.services import fixtures


def current_binding(db: Session, ch: ChangeRequest) -> dict:
    rev = db.get(CodeRevision, ch.code_revision_id) if ch.code_revision_id else None
    cfg_digest = None
    if ch.evaluation_config_id:
        try:
            cfg_digest = fixtures.eval_config(ch.evaluation_config_id)[1]
        except Exception:
            cfg_digest = "missing"
    pol, pol_digest = fixtures.policy()
    return {
        "requirement_version_id": ch.current_requirement_version_id,
        "model_id": ch.candidate_model_id,
        "model_artifact_digest": fixtures.compute_artifact_digest(ch.candidate_model_id) if ch.candidate_model_id else None,
        "code_revision_id": ch.code_revision_id,
        "code_revision_digest": rev.diff_digest if rev else None,
        "dataset_snapshot_id": ch.dataset_snapshot_id,
        "dataset_digest": fixtures.dataset_digest() if ch.dataset_snapshot_id else None,
        "evaluation_config_id": ch.evaluation_config_id,
        "evaluation_config_digest": cfg_digest,
        "evaluation_run_id": ch.latest_evaluation_run_id,
        "policy_version": pol["policy_version"],
        "policy_digest": pol_digest,
        "deployment_target": ch.deployment_target,
    }


def code_review_binding(db: Session, ch: ChangeRequest) -> dict:
    rev = db.get(CodeRevision, ch.code_revision_id) if ch.code_revision_id else None
    return {"code_revision_id": ch.code_revision_id, "code_revision_digest": rev.diff_digest if rev else None}


def diff_fields(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def digest(binding: dict) -> str:
    return fixtures.canonical_digest(binding)
