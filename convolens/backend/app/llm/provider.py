"""Configurable Claude provider adapter (Anthropic API or Amazon Bedrock). Credentials stay server-side.

There is no fallback: if the configured provider is missing or fails, callers receive an error and the
run is reported as failed. Demonstration mode never calls this module.
"""
from __future__ import annotations

from app.config import get_settings


class ModelNotConfigured(RuntimeError):
    pass


class ModelCallFailed(RuntimeError):
    pass


_override = None


def set_model_override(model) -> None:
    """Test hook: inject a chat model (e.g. a failing or scripted fake)."""
    global _override
    _override = model


def provider_status() -> dict:
    s = get_settings()
    return {"provider": s.model_provider, "configured": s.model_configured or _override is not None,
            "model_id": (getattr(_override, "model_id", "test-override") if _override is not None else s.model_id)}


def get_chat_model(max_tokens: int | None = None):
    if _override is not None:
        return _override
    s = get_settings()
    if not s.model_configured:
        raise ModelNotConfigured(
            "No model provider is configured. Set MODEL_PROVIDER=anthropic with ANTHROPIC_API_KEY, or "
            "MODEL_PROVIDER=bedrock with BEDROCK_MODEL_ID and AWS_REGION (AWS credentials via the standard chain).")
    mt = max_tokens or s.model_max_tokens
    if s.model_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=s.anthropic_model, api_key=s.anthropic_api_key.get_secret_value(), max_tokens=mt,
                             timeout=s.model_timeout_s, max_retries=s.model_max_retries)
    from langchain_aws import ChatBedrockConverse
    return ChatBedrockConverse(model=s.bedrock_model_id, region_name=s.aws_region, max_tokens=mt)
