"""Versioned API contracts (schema_version "1.0").

Request bodies are validated with these models. Response shapes for plans, operations,
approvals, errors and results are published at GET /api/schemas so clients can validate them.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Selection(Strict):
    sheet: str | None = Field(None, max_length=64)
    cell: str | None = Field(None, max_length=12)
    range: str | None = Field(None, max_length=32)


class ChatRequest(Strict):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = Field(None, max_length=40)
    selection: Selection | None = None


class ApprovalRequest(Strict):
    """An approval is bound to one operation, one workbook version and one change-set hash."""
    expected_version: int = Field(..., ge=1)
    change_set_hash: str = Field(..., min_length=64, max_length=64)
    acknowledge_risks: bool = False


class RestoreRequest(Strict):
    version: int = Field(..., ge=1)


class DemoLoginRequest(Strict):
    user: Literal["florina", "viewer", "admin", "other"] = "florina"


class ErrorResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    code: str
    message: str
    details: dict[str, Any] = {}
    retryable: bool = False
    correlation_id: str | None = None


class PlanStep(BaseModel):
    tool: str
    args: dict[str, Any] | None = None
    from_step: int | None = None


class PlanContract(BaseModel):
    intent: str
    role: str
    steps: list[PlanStep]
    assumptions: list[str]
    clarification: bool
    sheet: str | None


class CellState(BaseModel):
    formula: str | None
    type: Literal["blank", "bool", "number", "date", "datetime", "text"]
    value: Any


class CellChange(BaseModel):
    sheet: str
    cell: str
    before: CellState
    after: CellState
    number_format: str | None


class OperationContract(BaseModel):
    """What a proposed/applied operation looks like (GET /api/operations/{id})."""
    schema_version: str = SCHEMA_VERSION
    id: str
    workbook_id: str
    base_version: int
    action_type: str
    mutating: bool
    status: Literal["PROPOSED", "APPLYING", "APPLIED", "FAILED", "REJECTED", "STALE"]
    title: str
    sheet: str | None
    target_range: str | None
    affected_cells: int
    flags: dict[str, Any]
    destructive: bool
    changes_sample: list[CellChange] = []
    change_set_hash: str
    approval_required: bool
    requires_acknowledgement: bool
    preconditions: list[str]
    validation_rules: list[str]
    validation: dict[str, Any] | None
    result_version: int | None


class SourceRef(BaseModel):
    id: str
    workbook_id: str
    version: int
    sheet: str
    range: str
    header: str | None
    label: str
    status: Literal["current", "relocated", "stale"]


class ResultContract(BaseModel):
    """The final result of a run (GET /api/runs/{id} -> result)."""
    schema_version: str = SCHEMA_VERSION
    type: Literal["answer", "proposal", "clarification", "info", "error", "cancelled"]
    text: str
    intent: str | None = None
    sources: list[SourceRef] = []
    assumptions: list[str] = []
    warnings: list[str] = []
    method: str | None = None
    missing_treatment: str | None = None
    operations: list[dict[str, Any]] = []
    chart: dict[str, Any] | None = None
    engine: str | None = None
    usage: dict[str, Any] | None = None


def all_schemas() -> dict:
    return {name: model.model_json_schema() for name, model in {
        "Plan": PlanContract, "Operation": OperationContract, "Approval": ApprovalRequest, "Error": ErrorResponse,
        "Result": ResultContract, "ChatRequest": ChatRequest, "CellChange": CellChange, "Source": SourceRef,
    }.items()} | {"schema_version": SCHEMA_VERSION}
