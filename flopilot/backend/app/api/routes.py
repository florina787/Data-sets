"""HTTP API. Every workbook-scoped route re-checks workspace access via the services layer."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response

from .. import audit, db
from ..agent import context as C
from ..agent import supervisor
from ..auth import DEMO_USERS, Principal, current_principal
from ..common import AppError
from ..config import get_settings
from ..llm.providers import provider_status
from ..schemas import ApprovalRequest, ChatRequest, DemoLoginRequest, RestoreRequest, all_schemas
from ..services import operations as ops
from ..services import workbooks as W
from ..workbook import grid, recalc
from ..workbook.ingest import validate_upload
from ..workbook.security import sheet_to_csv

router = APIRouter(prefix="/api")

_rate: dict[str, deque] = defaultdict(deque)


def rate_limit(principal: Principal, bucket: str, per_minute: int) -> None:
    key = f"{principal.user_id}:{bucket}"
    now = time.monotonic()
    q = _rate[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_minute:
        raise AppError("rate_limited", "Too many requests. Wait a moment and try again.", 429, retryable=True)
    q.append(now)


# ----------------------------------------------------------------------------- meta
@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config")
def config() -> dict:
    s = get_settings()
    return {
        "product": "FloPilot", "subtitle": "Florina’s Excel Copilot",
        "llm": provider_status(),
        "recalc_engine": recalc.engine_name(),
        "limits": {"max_upload_mb": s.max_upload_mb, "max_cells": s.max_cells, "max_sheets": s.max_sheets,
                   "max_steps": s.max_steps, "max_tokens_per_run": s.max_tokens_per_run, "max_cost_per_run_usd": s.max_cost_per_run_usd},
        "supported_formats": [".xlsx", ".csv"],
        "unsupported_formats": [".xls", ".xlsm", ".xlsb", ".ods", "password-protected workbooks"],
        "auth_mode": s.auth_mode,
        "demo_users": [{"key": uid.split("_")[1], "name": name, "role": role, "workspace": ws}
                       for uid, name, _, ws, role in DEMO_USERS] if s.auth_mode == "demo" else [],
        "retention_days": s.retention_days,
        "integrations": {"excel_add_in": "not implemented (extension interface only)", "onedrive_sharepoint": "not implemented",
                         "microsoft_graph": "not implemented", "enterprise_identity": "interface only"},
    }


@router.get("/schemas")
def schemas() -> dict:
    return all_schemas()


@router.post("/auth/demo-login")
def demo_login(body: DemoLoginRequest) -> dict:
    if get_settings().auth_mode != "demo":
        raise AppError("not_available", "Demo sign-in is disabled.", 404)
    uid = f"usr_{body.user}"
    for user_id, name, token, ws, role in DEMO_USERS:
        if user_id == uid:
            return {"token": token, "user": {"id": user_id, "name": name, "role": role, "workspace_id": ws}}
    raise AppError("unknown_user", "Unknown demo user.", 404)


@router.get("/me")
def me(p: Principal = Depends(current_principal)) -> dict:
    return {"id": p.user_id, "name": p.name, "role": p.role, "workspace_id": p.workspace_id}


# ----------------------------------------------------------------------------- workbooks
@router.get("/workbooks")
def list_workbooks(p: Principal = Depends(current_principal)) -> list[dict]:
    return W.list_workbooks(p)


@router.post("/workbooks")
async def upload_workbook(file: UploadFile = File(...), p: Principal = Depends(current_principal)) -> dict:
    rate_limit(p, "upload", get_settings().upload_rate_per_min)
    limit = get_settings().max_upload_bytes
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise AppError("file_too_large", f"The file is larger than the {get_settings().max_upload_mb} MB limit.", 413)
        chunks.append(chunk)
    upload = validate_upload(file.filename or "upload", b"".join(chunks))
    return W.create_workbook(p, upload)


@router.post("/workbooks/demo")
def load_demo(p: Principal = Depends(current_principal)) -> dict:
    return W.create_demo_workbook(p)


@router.get("/workbooks/{workbook_id}")
def get_workbook(workbook_id: str, p: Principal = Depends(current_principal)) -> dict:
    return W.get_workbook(p, workbook_id)


@router.delete("/workbooks/{workbook_id}")
def delete_workbook(workbook_id: str, p: Principal = Depends(current_principal)) -> dict:
    W.delete_workbook(p, workbook_id)
    return {"deleted": True}


@router.get("/workbooks/{workbook_id}/profile")
def get_profile(workbook_id: str, version: int | None = None, p: Principal = Depends(current_principal)) -> dict:
    return W.get_profile(p, workbook_id, version)


@router.get("/workbooks/{workbook_id}/sheets/{sheet}/cells")
def get_cells(workbook_id: str, sheet: str, version: int | None = None, r0: int = Query(1, ge=1), r1: int = Query(100, ge=1),
              c0: int = Query(1, ge=1), c1: int = Query(60, ge=1), p: Principal = Depends(current_principal)) -> dict:
    model = W.get_model(p, workbook_id, version)
    return grid.window(model, sheet, r0, r1, c0, c1)


@router.get("/workbooks/{workbook_id}/sheets/{sheet}/find")
def find(workbook_id: str, sheet: str, q: str = Query(..., max_length=100), version: int | None = None,
         p: Principal = Depends(current_principal)) -> dict:
    return grid.find_rows(W.get_model(p, workbook_id, version), sheet, q)


@router.get("/workbooks/{workbook_id}/versions")
def versions(workbook_id: str, p: Principal = Depends(current_principal)) -> list[dict]:
    return W.list_versions(p, workbook_id)


@router.get("/workbooks/{workbook_id}/versions/{version}/download")
def download(workbook_id: str, version: int, format: str = "xlsx", sheet: str | None = None,
             p: Principal = Depends(current_principal)) -> Response:
    p.require("export")
    row = W.get_workbook_row(p, workbook_id)
    base = row["name"].rsplit(".", 1)[0]
    if format == "csv":
        model = W.get_model(p, workbook_id, version)
        target = model.resolve_sheet(sheet or model.sheet_names[0])
        if target is None:
            raise AppError("sheet_not_found", "Sheet not found.", 404)
        body = sheet_to_csv(model, target).encode("utf-8-sig")
        filename, media = f"{base} - {target} (v{version}).csv", "text/csv"
    else:
        body = W.version_bytes(workbook_id, version)
        filename, media = f"{base} (FloPilot v{version}).xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    audit.record("export", user_id=p.user_id, workspace_id=p.workspace_id, workbook_id=workbook_id, workbook_version=version,
                 format=format, size_bytes=len(body))
    return Response(body, media_type=media, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}", "Cache-Control": "no-store"})


@router.get("/workbooks/{workbook_id}/analysis-summary", response_class=PlainTextResponse)
def analysis_summary(workbook_id: str, conversation_id: str | None = None, p: Principal = Depends(current_principal)) -> str:
    p.require("export")
    wb = W.get_workbook(p, workbook_id)
    profile = W.get_profile(p, workbook_id)
    lines = [f"# FloPilot analysis summary — {wb['name']}", "", f"Workbook version: {wb['current_version']}",
             "Generated by FloPilot (Florina’s Excel Copilot). Charts shown in the FloPilot app are not embedded in this summary.", "",
             "## Data-quality findings", ""]
    lines += [f"- [{i['severity']}] {i['sheet']}: {i['message']}" for i in profile["issues"][:40]] or ["- None"]
    if conversation_id:
        lines += ["", "## Answers", ""]
        for m in C.list_messages(p, conversation_id):
            c = m["content"]
            if m["role"] == "user":
                lines += [f"**Q:** {c.get('text', '')}", ""]
            elif c.get("text"):
                lines += [c["text"], ""]
                for s in c.get("sources", [])[:6]:
                    lines.append(f"  - Source: {s['label']} (version {s['version']})")
                for a in c.get("assumptions", []):
                    lines.append(f"  - Assumption: {a}")
                lines.append("")
    audit.record("export", user_id=p.user_id, workspace_id=p.workspace_id, workbook_id=workbook_id, format="analysis-summary")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- copilot runs
@router.post("/workbooks/{workbook_id}/chat")
def chat(workbook_id: str, body: ChatRequest, p: Principal = Depends(current_principal)) -> dict:
    rate_limit(p, "chat", get_settings().chat_rate_per_min)
    return supervisor.start_run(p, workbook_id, body.message, body.conversation_id,
                                body.selection.model_dump(exclude_none=True) if body.selection else None)


@router.get("/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(current_principal)) -> dict:
    return supervisor.get_run(p, run_id)


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, p: Principal = Depends(current_principal)) -> dict:
    return supervisor.cancel_run(p, run_id)


@router.get("/workbooks/{workbook_id}/runs")
def list_runs(workbook_id: str, p: Principal = Depends(current_principal)) -> list[dict]:
    return supervisor.list_runs(p, workbook_id)


@router.get("/workbooks/{workbook_id}/conversations")
def conversations(workbook_id: str, p: Principal = Depends(current_principal)) -> list[dict]:
    W.get_workbook_row(p, workbook_id)
    return C.list_conversations(p, workbook_id)


@router.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: str, p: Principal = Depends(current_principal)) -> list[dict]:
    return C.list_messages(p, conversation_id)


# ----------------------------------------------------------------------------- operations
@router.get("/workbooks/{workbook_id}/operations")
def list_operations(workbook_id: str, p: Principal = Depends(current_principal)) -> list[dict]:
    return ops.list_operations(p, workbook_id)


@router.get("/operations/{op_id}")
def get_operation(op_id: str, p: Principal = Depends(current_principal)) -> dict:
    return ops.get_operation(p, op_id)


@router.post("/operations/{op_id}/approve")
def approve(op_id: str, body: ApprovalRequest, p: Principal = Depends(current_principal),
            idempotency_key: str | None = Header(default=None, max_length=80)) -> dict:
    return ops.approve_and_apply(p, op_id, body.expected_version, body.change_set_hash, body.acknowledge_risks, idempotency_key)


@router.post("/operations/{op_id}/reject")
def reject(op_id: str, p: Principal = Depends(current_principal)) -> dict:
    return ops.reject(p, op_id)


@router.post("/operations/{op_id}/refresh")
def refresh(op_id: str, p: Principal = Depends(current_principal)) -> dict:
    """Re-prepare a STALE proposal against the current version (a new operation needing new approval)."""
    op = ops.get_operation(p, op_id)
    if op["status"] not in ("STALE", "FAILED") and not op["out_of_date"]:
        raise AppError("not_stale", "Only out-of-date or failed proposals can be prepared again.", 409)
    builder = (op.get("details") or {}).get("builder")
    if not builder:
        raise AppError("not_refreshable", "This proposal cannot be prepared again automatically. Ask FloPilot again.", 422)
    answer = supervisor.run_tool_directly(p, op["workbook_id"], builder["name"], builder["args"], f"Prepare again: {op['title']}")
    ops.supersede(p, op_id)
    return answer


@router.post("/workbooks/{workbook_id}/restore")
def restore(workbook_id: str, body: RestoreRequest, p: Principal = Depends(current_principal)) -> dict:
    p.require("restore")
    return supervisor.run_tool_directly(p, workbook_id, "propose_restore", {"version": body.version}, f"Restore version {body.version}")


# ----------------------------------------------------------------------------- activity / audit
@router.get("/workbooks/{workbook_id}/activity")
def activity(workbook_id: str, p: Principal = Depends(current_principal)) -> dict:
    W.get_workbook_row(p, workbook_id)
    events = audit.list_for_workbook(workbook_id, limit=200)
    visible = {"workbook_uploaded", "operation_proposed", "operation_approved", "operation_rejected", "operation_applied",
               "operation_failed", "validation_failed", "approval_rejected_stale", "export", "run_started", "run_cancel_requested"}
    readable = [{k: e[k] for k in ("ts", "event_type", "workbook_version", "user_id", "run_id")} | {"detail": {
        k: v for k, v in e["detail"].items() if k in ("operation_id", "action_type", "affected_cells", "format", "failed_checks", "mode", "code")}}
        for e in events if e["event_type"] in visible]
    return {"events": readable}


@router.get("/admin/audit")
def admin_audit(limit: int = Query(200, le=1000), p: Principal = Depends(current_principal)) -> list[dict]:
    p.require("audit")
    rows = db.fetchall("SELECT * FROM audit_events WHERE workspace_id = ? OR workspace_id IS NULL ORDER BY ts DESC LIMIT ?",
                       (p.workspace_id, limit))
    for r in rows:
        r["detail"] = db.loads(r["detail"], {})
    return rows


@router.get("/admin/metrics")
def admin_metrics(p: Principal = Depends(current_principal)) -> dict:
    p.require("audit")
    from ..workbook.model import model_cache

    runs = db.fetchall("SELECT state, COUNT(*) AS n, SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, SUM(cost_estimate_usd) AS cost "
                       "FROM runs WHERE workspace_id = ? GROUP BY state", (p.workspace_id,))
    return {"runs_by_state": runs, "model_cache": {"hits": model_cache.hits, "misses": model_cache.misses}}


def request_id(request: Request) -> str:
    return request.headers.get("x-correlation-id", "")[:64]
