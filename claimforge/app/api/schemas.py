"""API request models (validated, bounded, extra fields forbidden)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.domain import PERSONAS, Approval, Claim, ClaimContext
from app.requirements.analyzer import DEMO_REQUIREMENT


class _Req(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Clar(_Req):
    clarifications: dict[str, str] = Field(default_factory=dict)

    @field_validator("clarifications")
    @classmethod
    def _bounded(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 20 or any(len(k) > 64 or len(x) > 64 for k, x in v.items()):
            raise ValueError("clarifications must be short codes (max 20)")
        return v


class RequirementIn(_Clar):
    text: str = Field(min_length=10, max_length=4000)
    persona: str = "Business Analyst"

    @field_validator("persona")
    @classmethod
    def _persona(cls, v: str) -> str:
        if v not in PERSONAS:
            raise ValueError(f"persona must be one of {PERSONAS}")
        return v


class PolicySearchIn(_Req):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class PolicyUploadIn(_Req):
    filename: str = Field(min_length=3, max_length=100)
    content: str = Field(min_length=1, max_length=2_000_000)


class TextIn(_Clar):
    text: str = Field(default=DEMO_REQUIREMENT, min_length=10, max_length=4000)


class TestsIn(TextIn):
    __test__ = False
    ruleset_id: str | None = Field(default=None, max_length=40)


class ClaimsGenerateIn(_Req):
    n_claims: Literal[1000, 10000, 50000, 100000] = 10000
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    sample: int = Field(default=20, ge=0, le=200)


class AdjudicateIn(_Req):
    claim: Claim
    context: ClaimContext = Field(default_factory=ClaimContext)
    ruleset_id: str = Field(default="RULESET_V2", max_length=40)


class SimulationIn(_Clar):
    text: str | None = Field(default=None, min_length=10, max_length=4000)
    current_ruleset_id: str = Field(default="RULESET_V1", max_length=40)
    proposed_ruleset_id: str | None = Field(default=None, max_length=40)
    n_claims: Literal[1000, 10000, 50000, 100000] = 10000
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class ReleaseAssessIn(RequirementIn):
    n_claims: Literal[1000, 10000, 50000, 100000] = 10000


class DeployIn(ReleaseAssessIn):
    approval: Approval
    inject_defect: bool = True


class AnomalyIn(_Req):
    relative_threshold: float | None = Field(default=None, gt=0, le=10)
    z_threshold: float | None = Field(default=None, gt=0, le=50)
    baseline_mode: Literal["RELEASE_PROJECTION", "HISTORICAL"] = "RELEASE_PROJECTION"


class InvestigateIn(_Req):
    max_agent_iterations: int | None = Field(default=None, ge=1, le=50)
    persona: str = "Claims Analyst"


class WorkflowIn(RequirementIn):
    approval: Approval | None = None
    stop_after: str | None = Field(default=None, max_length=40)
    inject_defect: bool = True
    n_claims: Literal[1000, 10000, 50000, 100000] = 10000
