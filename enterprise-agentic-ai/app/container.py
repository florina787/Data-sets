"""Dependency wiring (composition root).

Everything is constructed here and passed down explicitly, so tests can build a
container with a temporary vector store, hashing embeddings or a fake LLM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from app.agents.analysis_agent import AnalysisAgent
from app.agents.rag_agent import RAGAgent
from app.agents.response_agent import ResponseAgent
from app.agents.supervisor import SupervisorAgent
from app.agents.synthesis import OfflineSynthesizer
from app.agents.tool_agent import ToolAgent
from app.config.settings import Settings
from app.graph.workflow import GraphAgents, build_graph
from app.guardrails.validator import GuardrailNode, GuardrailValidator
from app.llm.provider import LLMProvider, build_llm_provider
from app.observability.tracing import TraceStore
from app.rag.embeddings import EmbeddingModel, build_embedding_model
from app.rag.ingestion import IngestionService
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.copilot import CopilotService
from app.tools.enterprise_tools import ToolRegistry
from app.tools.repository import EnterpriseDataRepository

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    llm: LLMProvider | None
    embedding_fallback_reason: str | None
    vector_store: VectorStore
    retriever: Retriever
    ingestion: IngestionService
    repository: EnterpriseDataRepository
    tools: ToolRegistry
    graph: CompiledStateGraph
    traces: TraceStore
    copilot: CopilotService


def build_container(
    settings: Settings,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingModel | None = None,
    ingest_on_start: bool = True,
) -> Container:
    """Build all application components. ``llm``/``embedding`` overrides are for tests."""
    if llm is None:
        llm = build_llm_provider(settings)
    fallback_reason = None
    if embedding is None:
        selection = build_embedding_model(settings)
        embedding, fallback_reason = selection.model, selection.fallback_reason

    store = VectorStore(settings.chroma_dir, settings.chroma_collection, embedding)
    ingestion = IngestionService(store, settings.chunk_size, settings.chunk_overlap)
    if ingest_on_start:
        ingestion.ingest_directory(settings.documents_dir)
        if settings.uploads_dir.exists():
            ingestion.ingest_directory(settings.uploads_dir)
    retriever = Retriever(store, settings.retrieval_top_k, settings.min_relevance_score)

    repo = EnterpriseDataRepository(settings.synthetic_data_dir)
    tools = ToolRegistry.from_repository(repo)
    synth = OfflineSynthesizer()
    agents = GraphAgents(
        supervisor=SupervisorAgent(repo, llm),
        rag=RAGAgent(retriever),
        tools=ToolAgent(tools, repo, llm),
        analysis=AnalysisAgent(llm, synth),
        response=ResponseAgent(llm, synth),
        guardrail=GuardrailNode(GuardrailValidator(settings.confidence_threshold, settings.corporate_email_domain)),
    )
    graph = build_graph(agents)
    traces = TraceStore(settings.trace_dir, settings.trace_buffer_size)
    copilot = CopilotService(graph, traces, settings.app_mode.value)
    logger.info(
        "Container ready: mode=%s embedding=%s chunks=%d tools=%d",
        settings.app_mode.value,
        store.embedding_name,
        store.count(),
        len(tools.names),
    )
    return Container(settings, llm, fallback_reason, store, retriever, ingestion, repo, tools, graph, traces, copilot)
