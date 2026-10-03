"""Evidence index: assigns citation labels to retrieved chunks and tool results."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.models.domain import Citation, RetrievedChunk, ToolCallRecord

CITATION_RE = re.compile(r"\[([ST]\d+)\]")


def tool_key(index: int) -> str:
    return f"tool:{index}"


@dataclass
class EvidenceIndex:
    """Maps evidence keys (chunk IDs / ``tool:<n>``) to labels ``S1..Sn`` / ``T1..Tn``."""

    chunks: list[RetrievedChunk]
    tool_results: list[ToolCallRecord]
    _labels: dict[str, str] = field(default_factory=dict, init=False)
    _citations: dict[str, Citation] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for i, chunk in enumerate(self.chunks, start=1):
            label = f"S{i}"
            self._labels[chunk.chunk_id] = label
            self._citations[label] = Citation(
                label=label,
                source_type="document",
                document_id=chunk.document_id,
                filename=chunk.filename,
                chunk_id=chunk.chunk_id,
                section=chunk.section,
                snippet=_snippet(chunk.text),
                score=chunk.score,
            )
        successful = [(i, r) for i, r in enumerate(self.tool_results) if r.success]
        for n, (i, record) in enumerate(successful, start=1):
            label = f"T{n}"
            self._labels[tool_key(i)] = label
            args = ", ".join(f"{k}={v}" for k, v in record.arguments.items())
            self._citations[label] = Citation(
                label=label,
                source_type="tool",
                tool_name=record.tool_name,
                snippet=f"{record.tool_name}({args})",
            )

    @property
    def is_empty(self) -> bool:
        return not self._citations

    def label(self, key: str) -> str | None:
        return self._labels.get(key)

    def markers(self, keys: list[str]) -> str:
        labels = []
        for key in keys:
            label = self.label(key)
            if label and label not in labels:
                labels.append(label)
        return "".join(f"[{label}]" for label in labels)

    def citation(self, label: str) -> Citation | None:
        return self._citations.get(label)

    @property
    def labels(self) -> set[str]:
        return set(self._citations)

    def citations_for(self, text: str) -> list[Citation]:
        """Citations referenced in ``text``, in order of first appearance."""
        seen: list[str] = []
        for label in CITATION_RE.findall(text):
            if label not in seen and label in self._citations:
                seen.append(label)
        return [self._citations[label] for label in seen]

    def corpus(self) -> str:
        """All evidence text, used by the guardrail for grounding checks."""
        parts = [c.text for c in self.chunks]
        parts += [json.dumps(r.result, default=str) for r in self.tool_results if r.success]
        return "\n".join(parts)

    def format_for_prompt(self, max_chars_per_chunk: int = 1200) -> str:
        """Numbered evidence block for LLM prompts."""
        lines: list[str] = []
        for chunk in self.chunks:
            label = self._labels[chunk.chunk_id]
            lines.append(f"[{label}] ({chunk.filename} › {chunk.section})\n{chunk.text[:max_chars_per_chunk]}")
        for i, record in enumerate(self.tool_results):
            label = self._labels.get(tool_key(i))
            if label:
                payload = json.dumps(record.result, default=str)[:3000]
                lines.append(f"[{label}] tool {record.tool_name}({record.arguments}):\n{payload}")
        return "\n\n".join(lines) if lines else "(no evidence available)"


def _snippet(text: str, limit: int = 280) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"
