# Latency report: deterministic fast paths and the Explanation agent

Measured on 2026-10-27/28 on the development machine: 4 CPU cores, 15 GB RAM, no GPU, llama-cpp-python 0.3.36
(CPU-only build; `llama_supports_gpu_offload()` is false), Qwen2.5-1.5B-Instruct Q4_K_M, 4 threads, 8,192-token context.
Every number below comes from a file in `data/manifests/`; nothing is estimated.

## Summary

| | Before | After |
|---|---|---|
| Warm deterministic requests, server end to end, p95 | **92.3 s** (n=100) | **0.50 s** (n=140) |
| Warm deterministic requests, browser (Enter → painted answer), p95 | not measured | **0.62 s** (n=140) |
| Deterministic answers correct (checked against independent SQL) | 58 / 100 | **140 / 140** |
| Greeting ("Hi", "thanks!") | 8.6 s p50, model called, answered "Greeting Analysis" | **42 ms** p50, no agents or model |
| "Top 5 positive statements" | 32.7 s p50, wrong analysis (root cause / topic ranking) | **146 ms** p50, the 2 statements that exist, shortfall stated |
| Model explanation, "Why is duplicate charge so negative?" | 96–110 s, 4,933 prompt tokens | 27–33 s, 1,367 prompt tokens (when the budget allows it) |

The 1-second acceptance criterion for warm deterministic requests is met, end to end in the browser, with
every answer correct. **It is not met by model-written explanations, and on this CPU it cannot be:** the
local model needs 20–25 s just to read a ~1,400-token prompt and write a short answer. With the default
20-second budget, the copilot recognises this before calling the model and returns the evidence-backed
deterministic narrative (0.8 s, governance note attached). Sub-second general-purpose Qwen inference on CPU
is not claimed anywhere in this project.

## What changed

1. **Small-talk fast path** (`app/agents/fast_path.py`). Greetings, thanks, "how are you", "what can you do"
   and "who are you" are answered from templates after input validation (sanitising and the prompt-injection
   scan still run; a flagged message never takes the fast path). No agent, analysis, retrieval or model runs.
   The request is still recorded: node events, telemetry row, audit entry and a session-memory turn that
   follow-up resolution ignores. The replies do not claim feelings.
2. **Top-N statements** (`app/analytics/statements.py`, operation `top_statements`). Customer-authored
   messages with the requested sentiment, grouped on their PII-masked text and ranked by frequency (or by
   strength for "most positive/negative statement"), each with real example message and conversation IDs.
   When fewer distinct statements exist than requested, the actual number is returned and the shortfall is
   stated in the headline. New high-precision rules route these questions before the root-cause rule.
3. **Routing fixes found by the benchmark**: "What do customers complain about most?" (went to the model,
   13–28 s) now routes to the complaint ranking; "Show the sentiment distribution across conversations"
   (returned a conversation list) now routes to the sentiment distribution; "this month vs last month"
   (went to topic comparison) routes to the monthly trend, whose headline now compares the latest two months.
   The intent-routing evaluation on the train and validation splits is unchanged (69.0% / 67.1%, same as before).
4. **Evidence Challenger before and after generation**. `claim_constraints()` reviews the compact results
   first: which factors the analysis supports (may be named), which it tested and rejected (must not be
   named as drivers), and association-only wording. These go into the explanation prompt as
   `CLAIM_CONSTRAINTS`; the model only runs when the results are complete. After generation, the existing
   checks (numeric grounding, claim consistency, causal-language rewrite, excerpt fidelity) still run on the
   final text and still replace a model answer that breaks them.
5. **QA answer contracts** (critical checks): `intent_operation_agreement` (a statements question must be
   answered by the statements query alone; a complaints question by the complaint ranking),
   `answer_item_count` (returned = min(requested, available), shortfall stated), `answer_items_present`
   (every listed statement appears in the answer), `statement_provenance` (each example message is re-read
   from DuckDB: customer-authored, labelled with the claimed sentiment, text identical).
6. **Explanation budget** (`EXPLANATION_TIMEOUT_SECONDS`, default 20, only on the model path). Before
   calling the model, the client estimates prompt reading plus a ~120-token answer at this machine's measured
   speeds; a call that cannot finish is not started. A call that overruns is stopped between streamed tokens.
   Either way the deterministic narrative is used and a `latency_budget: deterministic_fallback` governance
   finding says so. Neither case retries or opens the circuit breaker.
7. **Warm start**: the API preloads the retrieval and intent indexes (5.8 s on the first request otherwise)
   and the local model in a background thread at startup.
8. **Frontend**: a ranked statements table with clickable example conversations, a light reply for small
   talk labelled "Fast path · no model", the route shown in the routing strip, and a live draft of a model
   explanation while it streams (marked as not yet checked).

Governance, the Evidence Challenger, numeric grounding and QA were not disabled or weakened for speed.

## Method

- **Server**: `backend/scripts/benchmark_latency.py`. 20 requests per category, fresh `POST /api/chat` each,
  no session (no follow-up context), several phrasings per category. There is no analytics result cache, so
  every deterministic request routes, queries DuckDB, runs QA and governance from scratch. The LLM response
  cache is emptied before every run. "Warm" means the server process was started and its indexes and model
  loaded before measuring (the old code has no preload, so it was warmed with one request of each kind).
- **Correctness**: each answer is checked against ground truth computed by the benchmark with its own SQL on a
  read-only DuckDB connection (statements and mention counts, topic volumes and negative counts, negative
  share, latest-month rate, empathy response rate, ranking order), plus the expected analysis and no model
  call for small talk.
- **Browser**: `frontend/e2e/latency-bench.mjs`, Playwright + Chromium against the production build
  (`vite build` + `vite preview`), fresh session per question, timed inside the page from the Enter keydown
  to the frame after the answer element appears. This includes SSE transport, routing, database, QA,
  governance, response assembly and React rendering.
- **Before**: the same scripts against the previous commit (`86926f6`) on a second port, same data, same
  machine, run separately. Categories where requests took minutes were capped at about 300 s of runs, so
  their n is below 20 (shown in the table).

## Results: server end to end (ms)

| Category | Before n | Before p50 | Before p95 | Before correct | After n | After p50 | After p95 | After correct |
|---|---|---|---|---|---|---|---|---|
| Greetings / small talk | 20 | 8,585 | 14,921 | 0 | 20 | 42 | 84 | 20 |
| Top-N positive statements | 8 | 32,744 | 95,720 | 0 | 20 | 146 | 188 | 20 |
| Top-N negative statements | 4 | 103,057 | 135,163 | 0 | 20 | 151 | 187 | 20 |
| Complaints | 8 | 45,423 | 91,906 | 8 | 20 | 183 | 194 | 20 |
| Sentiment percentages | 20 | 114 | 151 | 15 | 20 | 98 | 113 | 20 |
| Sentiment trend / month comparison | 20 | 118 | 187 | 15 | 20 | 91 | 97 | 20 |
| Rankings (leadership priorities, coaching) | 20 | 478 | 736 | 20 | 20 | 379 | 552 | 20 |
| **All deterministic** | 100 | 321 | **92,311** | 58 | 140 | 144 | **499** | **140** |

Before, small talk and statement questions went to the model (the greeting was "analysed" as a topic, and
statement questions were answered by a root-cause or topic ranking), so they were both slow and wrong. Half of
the complaint questions took the model path (~91 s each) although the right analysis then ran.

## Results: browser time to answer (ms, after)

| Category | n | p50 | p95 |
|---|---|---|---|
| Greetings / small talk | 20 | 81 | 106 |
| Top-N positive statements | 20 | 220 | 283 |
| Top-N negative statements | 20 | 216 | 266 |
| Complaints | 20 | 253 | 282 |
| Sentiment percentages | 20 | 150 | 177 |
| Sentiment trend / month comparison | 20 | 149 | 185 |
| Rankings | 20 | 568 | 638 |
| **All deterministic** | 140 | 208 | **615** |

The browser benchmark was not run against the old code: its statement and greeting requests take 8–135 s
on the server alone, so the browser figure would add nothing to the comparison.

## Results: complex reasoning on the model path

"Why …" questions in Hybrid AI mode (root-cause investigation, then a model-written explanation), 20 runs
over four questions, LLM cache emptied before each run.

| Configuration | n | p50 | p95 | Model text used | Fallbacks |
|---|---|---|---|---|---|
| Before (no budget) | 2 | 175.9 s | 214.7 s | – | – |
| After, 20 s budget (default) | 20 | 0.77 s | 0.92 s | 0 | 20 × predicted not to fit; deterministic narrative + governance note |
| After, 60 s budget | 20 | 30.5 s | 37.4 s | 15 | 5 × rejected by the Evidence Challenger (named unsupported factors) |

The root-cause analysis is correct in every run; only the wording source differs. If model-written
explanations are wanted on this hardware, set `EXPLANATION_TIMEOUT_SECONDS=45` (or more) and accept ~30 s
answers; on a GPU build the default budget is expected to be enough, but that has not been measured here.

### Explanation agent, phase by phase (same question, `scripts/benchmark_explanation.py`, n=3 each)

| | Prompt tokens | Generated | Explanation time | Model text accepted |
|---|---|---|---|---|
| Before | 4,933 (facts 4,421, cut at 12,000 chars into invalid JSON) | 235–351 | 96.4–109.7 s | 1 / 3 |
| Compact facts, 350-token cap | 1,169 | 140–184 | 25.7–30.7 s | 0 / 3 |
| + pre-generation claim constraints | 1,367 | 130–188 | 27.0–33.1 s | 2 / 3 |

Root cause of the original 117 s: prompt evaluation of 4,933 tokens at 67.5 tok/s (73 s), then 351 generated
tokens at 14.2 tok/s (25 s); about 3.3 of 4 cores busy; no retries; model load 1.3–3.5 s (done once).

## Demonstration (default configuration: local model available, 20 s budget, AUTO mode)

Real outputs from `data/manifests/demo_queries_after.json` (answers shortened).

| Question | Route | Time | Answer (headline) | QA |
|---|---|---|---|---|
| Hi, how are you? | fast path, 0 model calls | 110 ms | "I'm running normally and ready to help." (no feelings claimed) | pass |
| What are the top 5 positive statements from users? | analytics only, `top_statements` | 309 ms | "Only 2 distinct positive statements appear in customer messages": "Got it. I've retried, and it works now." (3,117), "Thanks, that helps." (3,068) | pass 15/15 |
| What are the top 5 negative statements from users? | analytics only, `top_statements` | 268 ms | "Still not fixed. Can you escalate?" (3,208), "Thoda jaldi please, flight in 2 hours." (3,114), … | pass* |
| What was the most positive statement? | analytics only, strength ranking, n=1 | 194 ms | "Got it. I've retried, and it works now." | pass 15/15 |
| What are the top 5 complaints? | analytics only, complaint ranking | 215 ms | General help request, Duplicate charge, Item or service not received, … | warn (small-group caveat) |
| What percentage of conversations are negative? | analytics only | 122 ms | 33.5% (1,004 of 3,000) | warn (small-group caveat) |
| Compare sentiment this month vs last month | analytics only, monthly trend | 95 ms | "35.2% in 2025-11, up from 33.6% in 2025-10" | pass 11/11 |
| Which recurring customer concerns should leadership review first? | analytics only | 342 ms | Item or service not received (priority 67.1), then Coupon not applying, Duplicate charge | pass 15/15 |
| Why is duplicate charge so negative? | hybrid, model skipped by budget | 810 ms | "…most strongly associated with: replies to negative turns rarely acknowledge frustration" (association, not cause) | pass 14/14 |
| What is LangGraph? | hybrid, general-knowledge answer | 11.8 s | Labelled "Model's own answer, not from the dataset" with a high hallucination-risk badge. **The answer is factually wrong** (it calls LangGraph a visualisation tool). | pass (label check) |

\* This run showed a sample-size warning because statement #5 occurs only 21 times; a statement's count is
the answer itself, not a rate's denominator, so statements were exempted from that check after this run.

The last row is the honest limit of a 1.5B model on general knowledge: the label and the risk badge work as
intended, but the content cannot be trusted. Questions outside the dataset should be read with that badge in
mind, or answered with a larger model.

## Cache keys

There is no cache for analytics results; deterministic answers are always recomputed. The only cache is the
LLM response cache (`app/llm/cache.py`), keyed by SHA-256 over the model name, prompt id and version, system
prompt, the full rendered user prompt and the output schema and generation config. The user prompt contains
the question, the scoped verified facts, the claim constraints, uncertainty notes and evidence excerpts, so a
different scope, dataset build, prompt version or model produces a different key: stale answers cannot be
replayed across data or prompt changes. The key is not normalised, so whitespace or case variants of a
question miss the cache (safe, only a lower hit rate). Benchmarks empty the cache file before each run.

## Notes for other hardware

- **GPU**: `LOCAL_N_GPU_LAYERS=-1` offloads all layers when llama-cpp-python is built with CUDA or Metal
  (for example `CMAKE_ARGS="-DGGML_CUDA=on" pip install --force-reinstall --no-cache-dir llama-cpp-python`);
  the CPU-only build ignores it. Not measured here (no GPU).
- **Budget**: `EXPLANATION_TIMEOUT_SECONDS` (0 disables it). The speed estimates start from conservative
  defaults (60 prompt tok/s, 12 generated tok/s) and become this machine's measured moving averages after
  the first call.
- **GitHub Copilot as a provider**: investigated, not implemented. A Copilot subscription does not provide a
  general inference API for third-party applications. GitHub Models offers an OpenAI-compatible inference
  endpoint authenticated with a personal access token, with rate limits for free use; its terms, limits and
  pricing should be checked before relying on it, and it would send conversation excerpts to a hosted
  service, which this project's local-first design avoids.

## Reproduce

```bash
cd backend
LLM_PROVIDER=local LLM_CACHE_PATH=/tmp/bench-cache.sqlite uv run uvicorn app.main:app --port 8000 &
uv run python -m scripts.benchmark_latency --label after --runs 20 --llm-cache-path /tmp/bench-cache.sqlite
cd ../frontend && npx vite build && (npx vite preview --port 4173 &) && APP_URL=http://127.0.0.1:4173 node e2e/latency-bench.mjs after 20
```
