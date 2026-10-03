"""HTTP routes. All agent work is delegated to the LangGraph workflow via CopilotService."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app import __version__
from app.container import Container
from app.models.api import (
    ChatRequest,
    ChatResponse,
    DocumentInfo,
    HealthResponse,
    MetricsResponse,
    ToolInfo,
    UploadResponse,
)
from app.observability.tracing import langsmith_enabled
from app.rag.loader import SUPPORTED_EXTENSIONS, DocumentLoadError
from app.services.copilot import CopilotError

logger = logging.getLogger(__name__)
router = APIRouter()


def get_container(request: Request) -> Container:
    """Dependency: the application container created at startup."""
    return request.app.state.container


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(container: Container = Depends(get_container)) -> HealthResponse:
    """Liveness plus non-sensitive configuration (never returns secrets)."""
    docs = container.vector_store.list_documents()
    s = container.settings
    return HealthResponse(
        status="ok",
        version=__version__,
        mode=s.app_mode.value,
        live_llm_configured=container.llm is not None,
        llm_model=s.anthropic_model if container.llm is not None else None,
        embedding_backend=container.vector_store.embedding_name,
        embedding_fallback_reason=container.embedding_fallback_reason,
        documents_indexed=len(docs),
        chunks_indexed=container.vector_store.count(),
        tools_available=len(container.tools.names),
        langsmith_tracing=langsmith_enabled(),
    )


@router.post("/chat", response_model=ChatResponse, tags=["copilot"])
def chat(payload: ChatRequest, container: Container = Depends(get_container)) -> ChatResponse:
    """Run a question through the LangGraph workflow.

    Declared as a sync endpoint: FastAPI runs it in a worker thread, so the
    (blocking) LLM and vector-store calls never block the event loop.
    """
    try:
        return container.copilot.ask(payload.question, top_k=payload.top_k)
    except CopilotError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": str(exc), "request_id": exc.request_id},
        ) from exc


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@router.post("/documents/upload", response_model=UploadResponse, tags=["documents"])
async def upload_document(file: UploadFile, container: Container = Depends(get_container)) -> UploadResponse:
    """Upload a .md, .txt or .pdf document and index it for retrieval."""
    settings = container.settings
    if not settings.allow_uploads:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Document uploads are disabled on this deployment.")
    filename = _SAFE_NAME_RE.sub("_", Path(file.filename or "upload.txt").name)
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )
    max_bytes = int(settings.max_upload_mb * 1024 * 1024)
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {settings.max_upload_mb} MB.")

    try:
        result = await run_in_threadpool(container.ingestion.ingest_bytes, filename, data)
    except DocumentLoadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    (settings.uploads_dir / filename).write_bytes(data)  # persisted so it is re-indexed on restart
    logger.info("Uploaded %s (%d chunks)", filename, result.chunks_indexed)
    return UploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        chunks_indexed=result.chunks_indexed,
        replaced_existing=result.replaced_existing,
    )


@router.get("/documents", response_model=list[DocumentInfo], tags=["documents"])
def list_documents(container: Container = Depends(get_container)) -> list[DocumentInfo]:
    """Documents currently indexed in the vector store."""
    return [DocumentInfo(**d) for d in container.vector_store.list_documents()]


@router.get("/tools", response_model=list[ToolInfo], response_model_by_alias=True, tags=["tools"])
def list_tools(container: Container = Depends(get_container)) -> list[ToolInfo]:
    """Enterprise tools in MCP-compatible shape (name, description, inputSchema)."""
    return [ToolInfo(name=t["name"], description=t["description"], input_schema=t["inputSchema"]) for t in container.tools.describe()]


@router.get("/metrics", response_model=MetricsResponse, tags=["observability"])
def metrics(container: Container = Depends(get_container)) -> MetricsResponse:
    """Aggregated request metrics and the most recent traces."""
    return MetricsResponse(**container.traces.summary())
