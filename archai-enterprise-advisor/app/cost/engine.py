"""Deterministic cost engine and what-if simulator.

Pure arithmetic over the inputs and the configurable sample pricing file: the
same inputs always produce the same outputs. Prices are illustrative.
"""

from __future__ import annotations

from typing import Any

from app.cost.pricing import load_pricing, model_price
from app.models.enums import ArchitectureOption
from app.models.inputs import CostInputs
from app.models.outputs import CostBreakdown

A = ArchitectureOption
_LLM_PATTERNS = {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI}


def _calls_per_request(inputs: CostInputs, patterns: list[ArchitectureOption], pricing: dict[str, Any]) -> float:
    llm = [p for p in patterns if p in _LLM_PATTERNS]
    if not llm:
        return 0.0
    if inputs.llm_calls_per_request is not None:
        return float(inputs.llm_calls_per_request)
    defaults = pricing["default_llm_calls_per_request"]
    return float(max(defaults[p.value] for p in llm))


def _per_call_cost(
    price: dict[str, Any], input_tokens: float, output_tokens: float, cache_hit_rate: float
) -> float:
    cached = input_tokens * cache_hit_rate
    uncached = input_tokens - cached
    return (
        uncached * price["input_per_mtok"] + cached * price["cached_input_per_mtok"] + output_tokens * price["output_per_mtok"]
    ) / 1_000_000


def _blended_cost(
    inputs: CostInputs,
    pricing: dict[str, Any],
    input_tokens: float,
    output_tokens: float,
    *,
    cache_hit_rate: float,
    routing: float,
    batch_pct: float,
) -> float:
    primary = model_price(pricing, inputs.primary_model)
    small = model_price(pricing, inputs.small_model)
    per_call = (1 - routing) * _per_call_cost(primary, input_tokens, output_tokens, cache_hit_rate) + routing * _per_call_cost(
        small, input_tokens, output_tokens, cache_hit_rate
    )
    discount = float(pricing.get("batch_discount", 0.0))
    return per_call * (1 - batch_pct * discount)


def calculate_cost(
    inputs: CostInputs,
    architecture: ArchitectureOption,
    ai_patterns: list[ArchitectureOption] | None = None,
    *,
    regulated: bool = False,
    review_mandatory: bool = False,
    pricing: dict[str, Any] | None = None,
    include_comparison: bool = True,
) -> CostBreakdown:
    """Monthly cost model for an architecture option."""
    pricing = pricing or load_pricing()
    patterns = list(ai_patterns) if ai_patterns is not None else ([architecture] if architecture in _LLM_PATTERNS | {A.TRADITIONAL_ML} else [])
    no_ai = not patterns
    uses_rag = A.RAG_GENAI in patterns or (A.AGENTIC_AI in patterns and inputs.rag_top_k > 0)
    calls = _calls_per_request(inputs, patterns, pricing)

    retrieval_tokens = inputs.rag_top_k * inputs.tokens_per_chunk if uses_rag else 0
    in_tokens = float(inputs.avg_input_tokens + retrieval_tokens)
    out_unlimited = float(inputs.avg_output_tokens)
    out_tokens = float(min(inputs.avg_output_tokens, inputs.max_output_tokens) if inputs.max_output_tokens else inputs.avg_output_tokens)

    optimized_call = _blended_cost(
        inputs, pricing, in_tokens, out_tokens,
        cache_hit_rate=inputs.cache_hit_rate, routing=inputs.small_model_routing_pct, batch_pct=inputs.batch_pct,
    )
    unoptimized_call = _blended_cost(inputs, pricing, in_tokens, out_unlimited, cache_hit_rate=0.0, routing=0.0, batch_pct=0.0)
    cost_per_request = optimized_call * calls
    unopt_per_request = unoptimized_call * calls
    model_month = cost_per_request * inputs.requests_per_month
    unopt_month = unopt_per_request * inputs.requests_per_month

    infra = 0.0 if no_ai else inputs.infrastructure_cost_month
    review = 0.0
    if not no_ai:
        review = inputs.requests_per_month * inputs.human_review_pct * inputs.human_review_minutes / 60 * inputs.reviewer_hourly_cost
    current = inputs.current_monthly_cost
    proposed = current + model_month + infra + review  # existing systems are retained, so their run-cost remains

    # ---------------------------------------------------------- latency (indicative)
    if calls:
        primary, small = model_price(pricing, inputs.primary_model), model_price(pricing, inputs.small_model)
        per_call_ms = (1 - inputs.small_model_routing_pct) * primary["latency_ms_per_call"] + inputs.small_model_routing_pct * small["latency_ms_per_call"]
        per_call_ms *= 1 - 0.3 * inputs.cache_hit_rate
        if inputs.max_output_tokens and inputs.max_output_tokens < inputs.avg_output_tokens:
            per_call_ms *= 0.85
        latency = per_call_ms * calls
        if uses_rag:
            r = pricing["retrieval_latency_ms"]
            latency += r["base"] + r["per_chunk"] * inputs.rag_top_k + (r["rerank"] if inputs.rag_top_k > 5 else 0)
        latency_note = f"Indicative end-to-end latency ≈ {latency / 1000:.1f}s ({calls:g} model call(s) per request)."
    elif patterns:
        latency = 50.0
        latency_note = "Classical ML inference: typically tens of milliseconds; no LLM in the path."
    else:
        latency = 0.0
        latency_note = "No AI in the request path — existing latency profile unchanged."

    # ---------------------------------------------------------- risk impact
    risk_notes: list[str] = []
    points = 0
    if calls:
        if inputs.small_model_routing_pct > 0.6:
            points += 1
            risk_notes.append("High small-model routing share: validate the router and monitor answer quality.")
        if uses_rag and inputs.rag_top_k > 10:
            points += 1
            risk_notes.append("Large top-k raises cost/latency and the indirect prompt-injection surface; use reranking.")
        if uses_rag and 0 < inputs.rag_top_k < 3:
            points += 1
            risk_notes.append("Very small top-k risks missing relevant evidence (recall).")
        if inputs.cache_hit_rate > 0.7:
            points += 1
            risk_notes.append("Very high cache reliance: ensure invalidation when source documents change.")
        if inputs.max_output_tokens is None:
            points += 1
            risk_notes.append("No response-length cap: runaway output cost possible.")
        if review_mandatory and inputs.human_review_pct < 1.0:
            points += 2
            risk_notes.append("Human review below 100% although review is mandatory for this workload.")
        elif regulated and inputs.human_review_pct < 0.1:
            points += 1
            risk_notes.append("Low human review share for a regulated workload.")
    risk_impact = "NO CHANGE (no AI)" if not patterns else ("LOWER" if points == 0 else "MODERATE INCREASE" if points <= 2 else "HIGHER")

    # ---------------------------------------------------------- optimizations
    applied: list[str] = []
    recs: list[str] = []
    if calls:
        if inputs.cache_hit_rate > 0:
            applied.append(f"Prompt caching at {inputs.cache_hit_rate:.0%} hit rate")
        else:
            recs.append("Enable prompt caching for stable system prompts and shared context.")
        if inputs.small_model_routing_pct > 0:
            applied.append(f"{inputs.small_model_routing_pct:.0%} of calls routed to {inputs.small_model}")
        else:
            recs.append("Route simple/classification calls to a smaller model.")
        if inputs.max_output_tokens:
            applied.append(f"Response limit {inputs.max_output_tokens} tokens")
        else:
            recs.append("Set a max-output-token limit per route.")
        if inputs.batch_pct > 0:
            applied.append(f"{inputs.batch_pct:.0%} batched (sample discount {pricing.get('batch_discount', 0):.0%})")
        else:
            recs.append("Batch non-interactive workloads (reports, back-office summaries).")
        if uses_rag and inputs.rag_top_k > 6:
            recs.append("Reduce top-k with a reranker: fewer, better chunks lower cost and latency.")
        if A.AGENTIC_AI in patterns:
            recs.append("Enforce per-request token budgets and maximum agent iterations.")
        if inputs.requests_per_month * calls > 5_000_000:
            recs.append("At this volume, evaluate self-hosted open-weight models for high-volume routes.")
    elif patterns:
        recs.append("Classical ML: cost is dominated by training/serving infrastructure, not tokens.")

    comparison: dict[str, float] = {}
    if include_comparison:
        for option in A:
            opt_patterns = [option] if option in _LLM_PATTERNS | {A.TRADITIONAL_ML} else ([] if option is not A.HYBRID else patterns)
            comparison[option.value] = round(
                calculate_cost(inputs, option, opt_patterns, pricing=pricing, include_comparison=False).proposed_cost_month, 2
            )

    return CostBreakdown(
        requests_per_month=inputs.requests_per_month,
        llm_calls_per_request=calls,
        effective_input_tokens=in_tokens if calls else 0.0,
        effective_output_tokens=out_tokens if calls else 0.0,
        cost_per_request=round(cost_per_request, 6),
        unoptimized_cost_per_request=round(unopt_per_request, 6),
        model_cost_month=round(model_month, 2),
        unoptimized_model_cost_month=round(unopt_month, 2),
        infrastructure_cost_month=round(infra, 2),
        human_review_cost_month=round(review, 2),
        current_cost_month=round(current, 2),
        proposed_cost_month=round(proposed, 2),
        expected_savings_month=round(current - proposed, 2),
        optimization_savings_month=round(unopt_month - model_month, 2),
        estimated_latency_ms=round(latency, 0),
        latency_note=latency_note,
        risk_impact=risk_impact,
        risk_notes=risk_notes,
        optimizations_applied=applied,
        recommendations=recs,
        comparison_by_architecture=comparison,
        pricing_disclaimer=pricing.get("_disclaimer", "Sample pricing."),
    )


def simulate(
    inputs: CostInputs,
    architecture: ArchitectureOption,
    ai_patterns: list[ArchitectureOption] | None = None,
    *,
    regulated: bool = False,
    review_mandatory: bool = False,
) -> CostBreakdown:
    """What-if simulator entry point (identical engine, separate name for the API/UI)."""
    return calculate_cost(inputs, architecture, ai_patterns, regulated=regulated, review_mandatory=review_mandatory)
