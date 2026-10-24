"""Pick installed models for a request. Never assumes a model can see images:
vision is decided by the capabilities Ollama reports for the installed model."""

from __future__ import annotations

from .ollama import LLMUnavailable, ModelInfo


def _rank_text(m: ModelInfo) -> tuple:
    return ("qwen" in m.name.lower(), not m.vision, -abs(m.size_bytes - 2e9))


def resolve_text_model(preferred: str | None, installed: list[ModelInfo]) -> str:
    names = {m.name for m in installed}
    if preferred and preferred in names:
        return preferred
    if preferred and f"{preferred}:latest" in names:
        return f"{preferred}:latest"
    if not installed:
        raise LLMUnavailable("No local model is installed. Open Setup and download a recommended model, or run: ollama pull qwen2.5:3b")
    text_models = [m for m in installed if "embed" not in m.name.lower()]
    if not text_models:
        raise LLMUnavailable("Only embedding models are installed. Download a chat model in Setup.")
    return max(text_models, key=_rank_text).name


def resolve_vision_model(preferred: str | None, installed: list[ModelInfo]) -> str | None:
    vision = [m for m in installed if m.vision]
    for m in vision:
        if m.name == preferred or m.name == f"{preferred}:latest":
            return m.name
    if not vision:
        return None
    return min(vision, key=lambda m: m.size_bytes).name
