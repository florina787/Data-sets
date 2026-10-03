"""Analysis agent: summarises, compares, identifies risks, extracts actions, recommends."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.evidence import EvidenceIndex, tool_key
from app.agents.prompts import ANALYSIS_SYSTEM, RESPONSE_USER
from app.agents.synthesis import OfflineSynthesizer
from app.graph.state import CopilotState
from app.llm.provider import LLMError, LLMProvider, estimate_tokens
from app.models.domain import AnalysisResult, Finding, Intent, TokenUsage

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Produces a structured :class:`AnalysisResult` from the gathered evidence."""

    def __init__(self, llm: LLMProvider | None = None, synthesizer: OfflineSynthesizer | None = None) -> None:
        self._llm = llm
        self._synth = synthesizer or OfflineSynthesizer()

    @staticmethod
    def _labels_to_keys(analysis: AnalysisResult, index: EvidenceIndex) -> AnalysisResult:
        """Convert LLM citation labels (S1/T1) back into evidence keys."""
        label_to_key: dict[str, str] = {}
        for chunk in index.chunks:
            label_to_key[index.label(chunk.chunk_id) or ""] = chunk.chunk_id
        for i in range(len(index.tool_results)):
            label = index.label(tool_key(i))
            if label:
                label_to_key[label] = tool_key(i)

        def fix(items: list[Finding]) -> list[Finding]:
            return [
                Finding(text=f.text, sources=[label_to_key[s.strip("[] ")] for s in f.sources if s.strip("[] ") in label_to_key])
                for f in items
            ]

        return AnalysisResult(
            summary=analysis.summary,
            key_findings=fix(analysis.key_findings),
            risks=fix(analysis.risks),
            action_items=fix(analysis.action_items),
            recommendations=fix(analysis.recommendations),
        )

    def __call__(self, state: CopilotState) -> dict[str, Any]:
        query = state["user_query"]
        intent = state.get("intent", Intent.GENERAL_QA)
        chunks = state.get("retrieved_documents", [])
        tools = state.get("tool_results", [])
        index = EvidenceIndex(chunks, tools)
        prompt = RESPONSE_USER.format(question=query, intent=intent.value, evidence=index.format_for_prompt(), analysis="")
        errors: list[str] = []

        if self._llm is not None and not index.is_empty:
            try:
                analysis, usage = self._llm.structured(ANALYSIS_SYSTEM, prompt, AnalysisResult)
                analysis = self._labels_to_keys(analysis, index)
                return {"analysis": analysis, "token_usage": usage, "_detail": _describe(analysis, "Claude")}
            except LLMError as exc:
                logger.warning("Analysis LLM failed, using offline analysis: %s", exc)
                errors.append(f"analysis_agent: {exc} (fell back to offline analysis)")

        analysis = self._synth.analyze(query, intent, chunks, tools)
        usage = TokenUsage(
            input_tokens=estimate_tokens(ANALYSIS_SYSTEM + prompt),
            output_tokens=estimate_tokens(analysis.model_dump_json()),
            estimated=True,
        )
        return {"analysis": analysis, "token_usage": usage, "errors": errors, "_detail": _describe(analysis, "offline")}


def _describe(analysis: AnalysisResult, engine: str) -> str:
    return (
        f"{engine}: {len(analysis.key_findings)} findings, {len(analysis.risks)} risks, "
        f"{len(analysis.action_items)} actions, {len(analysis.recommendations)} recommendations"
    )
