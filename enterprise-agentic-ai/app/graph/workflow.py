"""LangGraph workflow definition.

    START → supervisor ─┬→ rag_agent ──────┐
                        ├→ tool_agent ─────┤ (each specialist returns to the supervisor)
                        ├→ analysis_agent ─┘
                        └→ response_agent → guardrail → END
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.analysis_agent import AnalysisAgent
from app.agents.rag_agent import RAGAgent
from app.agents.response_agent import ResponseAgent
from app.agents.supervisor import SupervisorAgent, route_from_supervisor
from app.agents.tool_agent import ToolAgent
from app.graph.instrumentation import instrument
from app.graph.state import CopilotState
from app.guardrails.validator import GuardrailNode
from app.models.domain import AgentName


@dataclass(frozen=True)
class GraphAgents:
    """The agents a graph is built from (injected, so tests can swap any of them)."""

    supervisor: SupervisorAgent
    rag: RAGAgent
    tools: ToolAgent
    analysis: AnalysisAgent
    response: ResponseAgent
    guardrail: GuardrailNode


def build_graph(agents: GraphAgents) -> CompiledStateGraph:
    """Compile the copilot state graph with explicit nodes and conditional edges."""
    graph = StateGraph(CopilotState)

    graph.add_node(AgentName.SUPERVISOR.value, instrument(AgentName.SUPERVISOR.value, agents.supervisor))
    graph.add_node(AgentName.RAG.value, instrument(AgentName.RAG.value, agents.rag))
    graph.add_node(AgentName.TOOLS.value, instrument(AgentName.TOOLS.value, agents.tools))
    graph.add_node(AgentName.ANALYSIS.value, instrument(AgentName.ANALYSIS.value, agents.analysis))
    graph.add_node(AgentName.RESPONSE.value, instrument(AgentName.RESPONSE.value, agents.response))
    graph.add_node(AgentName.GUARDRAIL.value, instrument(AgentName.GUARDRAIL.value, agents.guardrail))

    graph.add_edge(START, AgentName.SUPERVISOR.value)
    graph.add_conditional_edges(
        AgentName.SUPERVISOR.value,
        route_from_supervisor,
        {
            AgentName.RAG.value: AgentName.RAG.value,
            AgentName.TOOLS.value: AgentName.TOOLS.value,
            AgentName.ANALYSIS.value: AgentName.ANALYSIS.value,
            AgentName.RESPONSE.value: AgentName.RESPONSE.value,
        },
    )
    for specialist in (AgentName.RAG, AgentName.TOOLS, AgentName.ANALYSIS):
        graph.add_edge(specialist.value, AgentName.SUPERVISOR.value)
    graph.add_edge(AgentName.RESPONSE.value, AgentName.GUARDRAIL.value)
    graph.add_edge(AgentName.GUARDRAIL.value, END)

    return graph.compile()
