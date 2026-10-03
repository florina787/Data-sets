"""Response agent: combines question, evidence, tool results and analysis into the answer."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.agents.evidence import EvidenceIndex
from app.agents.prompts import RESPONSE_SYSTEM, RESPONSE_USER
from app.agents.synthesis import OfflineSynthesizer, _dedupe
from app.graph.state import CopilotState
from app.llm.provider import LLMError, LLMProvider, estimate_tokens
from app.models.domain import AnalysisResult, Finding, Intent, TokenUsage

logger = logging.getLogger(__name__)

INSUFFICIENT_EVIDENCE = (
    "More information is required: I could not find evidence for this question in the indexed "
    "documents or the enterprise tools. Try rephrasing, naming a project, or uploading a relevant document."
)


class ResponseAgent:
    """Writes the answer (Claude in LIVE mode, offline synthesizer in DEMO mode).

    The *Sources* section is always generated from the citation labels that
    actually appear in the answer body, so sources can never be hallucinated.
    """

    def __init__(self, llm: LLMProvider | None = None, synthesizer: OfflineSynthesizer | None = None) -> None:
        self._llm = llm
        self._synth = synthesizer or OfflineSynthesizer()

    # --- DEMO mode composition ----------------------------------------------
    def _compose_offline(self, state: CopilotState, index: EvidenceIndex) -> str:
        query = state["user_query"]
        intent = state.get("intent", Intent.GENERAL_QA)
        chunks = state.get("retrieved_documents", [])
        tools = state.get("tool_results", [])
        analysis: AnalysisResult | None = state.get("analysis")

        lead = self._synth.lead_paragraph(query, intent, chunks, tools, analysis, index.markers)
        if not lead.strip():
            return INSUFFICIENT_EVIDENCE

        if analysis is not None:
            findings = analysis.key_findings or analysis.risks
            actions = analysis.action_items + analysis.recommendations
        else:
            focus = self._synth.focus_terms(tools)
            findings = self._synth.tool_findings(tools) + self._synth.relevant_findings(query, chunks, limit=3, focus=focus)
            actions = self._synth.tool_actions(tools) + self._synth.action_findings(query, chunks)[:3]
            if intent is Intent.PEOPLE_LOOKUP:
                findings = self._people_findings(tools)
        findings = _dedupe(findings, limit=6)
        actions = _dedupe(actions, limit=5)

        def bullets(items: list[Finding], empty: str) -> str:
            if not items:
                return f"- {empty}"
            return "\n".join(f"- {f.text} {index.markers(f.sources)}".rstrip() for f in items)

        return (
            f"### Answer\n{lead}\n\n"
            f"### Key Findings\n{bullets(findings, 'No additional findings in the available evidence.')}\n\n"
            f"### Recommended Actions\n{bullets(actions, 'No specific actions identified in the available evidence.')}"
        )

    @staticmethod
    def _people_findings(tools: list) -> list[Finding]:
        out: list[Finding] = []
        for i, record in enumerate(tools):
            if record.success and record.tool_name == "search_employee_directory":
                for e in record.result["results"][1:4]:
                    out.append(Finding(text=f"{e['name']}, {e['title']} ({e['team']}), {e['email']}", sources=[f"tool:{i}"]))
        return out

    # --- node ------------------------------------------------------------------
    def __call__(self, state: CopilotState) -> dict[str, Any]:
        chunks = state.get("retrieved_documents", [])
        tools = state.get("tool_results", [])
        index = EvidenceIndex(chunks, tools)
        analysis = state.get("analysis")
        prompt = RESPONSE_USER.format(
            question=state["user_query"],
            intent=state.get("intent", Intent.GENERAL_QA).value,
            evidence=index.format_for_prompt(),
            analysis=analysis.model_dump_json(indent=1) if analysis else "",
        )
        errors: list[str] = []
        engine = "offline"
        body: str | None = None
        usage = TokenUsage()

        if index.is_empty:
            body = INSUFFICIENT_EVIDENCE
        elif self._llm is not None:
            try:
                result = self._llm.generate(RESPONSE_SYSTEM, prompt)
                body, usage, engine = result.text.strip(), result.usage, "Claude"
            except LLMError as exc:
                logger.warning("Response LLM failed, using offline composition: %s", exc)
                errors.append(f"response_agent: {exc} (fell back to offline composition)")

        if body is None:
            body = self._compose_offline(state, index)
            usage = TokenUsage(
                input_tokens=estimate_tokens(RESPONSE_SYSTEM + prompt), output_tokens=estimate_tokens(body), estimated=True
            )

        body = re.sub(r"\n#+\s*Sources\b.*", "", body, flags=re.DOTALL | re.IGNORECASE).strip()
        citations = index.citations_for(body)
        if citations:
            lines = []
            for c in citations:
                if c.source_type == "document":
                    lines.append(f"- **[{c.label}]** {c.filename} › {c.section} (`{c.chunk_id}`)")
                else:
                    lines.append(f"- **[{c.label}]** Enterprise tool `{c.snippet}`")
            body += "\n\n### Sources\n" + "\n".join(lines)

        return {
            "draft_answer": body,
            "citations": citations,
            "token_usage": usage,
            "errors": errors,
            "_detail": f"{engine} answer with {len(citations)} citations",
        }
