"""Configurable model provider adapter: Claude (Anthropic API or Amazon Bedrock) or Google Gemini. Credentials stay server-side.

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
    limiter = None
    if s.model_requests_per_minute:
        from langchain_core.rate_limiters import InMemoryRateLimiter
        limiter = InMemoryRateLimiter(requests_per_second=s.model_requests_per_minute / 60, check_every_n_seconds=0.2, max_bucket_size=1)
    if s.model_provider == "gemini":
        from langchain_openai import ChatOpenAI
        key = s.google_api_key.get_secret_value() if s.google_api_key else "injected-by-egress-proxy"
        # Thinking tokens count against max_tokens on Gemini, so allow more room than for Claude.
        return ChatOpenAI(model=s.gemini_model, base_url=s.gemini_base_url, api_key=key, max_tokens=max(mt, s.gemini_max_tokens),
                          reasoning_effort=s.gemini_reasoning_effort, timeout=max(s.model_timeout_s, 120),
                          max_retries=max(s.model_max_retries, 5), rate_limiter=limiter, stream_usage=True)
    if s.model_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=s.anthropic_model, api_key=s.anthropic_api_key.get_secret_value(), max_tokens=mt,
                             timeout=s.model_timeout_s, max_retries=s.model_max_retries)
    from langchain_aws import ChatBedrockConverse
    return ChatBedrockConverse(model=s.bedrock_model_id, region_name=s.aws_region, max_tokens=mt)


def _inline_schema(model_cls) -> dict:
    """Self-contained JSON schema (no $ref/$defs, no length keywords). Gemini's OpenAI-compatible endpoint rejects
    nested references in array items; Pydantic still validates the full constraints afterwards."""
    schema = model_cls.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(x):
        if isinstance(x, dict):
            if "$ref" in x:
                return walk(dict(defs[x["$ref"].split("/")[-1]]))
            out = {k: walk(v) for k, v in x.items() if k not in ("title", "maxItems", "maxLength", "default", "pattern")}
            if "properties" in out:  # smaller models skip optional fields (e.g. evidence); require every field
                out["required"] = list(out["properties"])
            return out
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x

    out = walk(schema)
    out["title"] = model_cls.__name__
    out.setdefault("description", (model_cls.__doc__ or model_cls.__name__).strip()[:300])
    return out


def structured_invoke(model, schema_cls, messages) -> dict:
    """Structured output for any provider. Returns {"parsed", "raw", "parsing_error"} like include_raw=True."""
    if get_settings().model_provider != "gemini" or _override is not None:
        return model.with_structured_output(schema_cls, include_raw=True).invoke(messages)
    out = model.with_structured_output(_inline_schema(schema_cls), include_raw=True).invoke(messages)
    if out.get("parsed") is None:
        return {"parsed": None, "raw": out.get("raw"), "parsing_error": out.get("parsing_error") or "empty response"}
    try:
        return {"parsed": schema_cls(**out["parsed"]), "raw": out.get("raw"), "parsing_error": None}
    except Exception as exc:  # pydantic validation error: reported as a failure, never coerced
        return {"parsed": None, "raw": out.get("raw"), "parsing_error": f"validation: {str(exc)[:300]}"}
