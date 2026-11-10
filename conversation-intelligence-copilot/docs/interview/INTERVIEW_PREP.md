# Interview preparation

## Why LangGraph?
Explicit state machine with conditional routing, real parallel branches (specialist ‖ retrieval), per-request checkpointing and a stream of node events the UI animates. A single prompt can't guarantee the numbers; a free-form agent loop is hard to bound and test. Every node is a plain, unit-testable function.

## Why Gemini, and for what?
Configurable Flash model via `google-genai`: cheap, fast, native JSON-schema output. Used for **interpretation** (intent), **language** (grounded explanation) and **classification** (batch labelling). Not used for counts, rates, ranks or chart data. Without a key, or when the circuit is open, the same graph runs deterministically and says so.

## Why DuckDB for the numbers?
In-process, columnar, exact SQL over 42k rows in milliseconds; read-only connection; every query is a registered, parameterised operation, so results are testable against fixtures and an independent oracle.

## How is hallucination controlled?
1. Closed-enum structured outputs, schema-validated, one repair attempt. 2. IDs from the model re-validated against the DB. 3. Explanations rejected if they contain any number not in the verified results. 4. QA agent checks denominators, ranks, chart-to-table equality and citations on every answer. 5. Memory stores references, not prose.

## How does retrieval work, and how good is it?
Conversation-aware chunks → embeddings → exact cosine search in FAISS with metadata pre-filtering → one passage per conversation → evidence with message IDs and CSV lines. Two indexes (MiniLM + LSA) fused by weighted reciprocal rank fusion: topic P@5 62.8% vs 12.5% random on paraphrased queries (MiniLM alone 62.2%, LSA alone 28.9%). The fusion weight was tuned on the same queries, and the gain over MiniLM is small; every method still misses payment-not-reflected paraphrases.

## How are model failures handled?
Retryable errors (408/429/5xx/timeouts) back off with jitter or Retry-After; permanent errors (401/403) open the circuit immediately; repeated failures open it after a threshold; the request falls back to deterministic intent and explanation; the UI shows "Deterministic mode" with the reason and a retry button.

## What did evaluation reveal?
Exact match with an independent oracle; 100% QA on 51 requests; 50% intent accuracy on held-out paraphrases for the rules fallback (mostly safe refusals); a personnel-decision question wrongly routed to coaching (fixed); retrieval topic P@5 rose from 37% (LSA) to 62% with MiniLM.

## What about the data itself?
It is synthetic and templated: 426 unique texts; customer follow-ups and agent closing actions are drawn independently of the issue; timestamps are shuffled within conversations; ~1 agent per conversation. The app reports these properties instead of manufacturing insight: significance tests, sample-size gates, misfit rates flagged as a generator property.

## Production changes
Managed Postgres/warehouse + vector DB (pgvector/managed), job queue for labelling, SSO/RBAC/tenant isolation, secret manager, centralised tracing (LangSmith/OpenTelemetry), CI/CD with evaluation gates, model and prompt A/B with human-labelled sets, data retention policies, horizontal API scaling (the graph is stateless per request apart from SQLite stores, which would move to a shared DB).

## Trade-offs to own
Rules parser brittle without the model; developer-defined sentiment mapping not independently validated; LSA fallback when the embedding model is unavailable; single-node storage; Docker images not built in the sandbox.
