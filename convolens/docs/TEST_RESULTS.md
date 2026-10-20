# Test results

Every result below was produced in the development environment on 20 October 2026. Anything not executed is marked **not verified**.

## Automated tests

| Suite | Command | Result |
|---|---|---|
| Backend (pytest) | `uv run pytest` | **65 passed** |
| Frontend (vitest) | `npm test` | **7 passed** |
| Frontend typecheck / build | `npm run build` | **passed** |

The backend tests cover:

- **Ingestion:** thread reconstruction; branches, missing parents and cycles; duplicates; boolean and timestamp parsing; string-safe IDs; schema rejection; reproducible sampling; no double-counting; same-author non-merging; idempotent re-import; cancellation cleanup; upload size/type/schema validation; local-path traversal; job recovery.
- **Metrics and evidence:** metric denominators with unknowns; unknown outcomes; non-covered languages; chart/filter/table consistency across breakdown, cross-tab, time series and explorer; filter allowlisting; evidence span validation; evidence scoped to its dataset.
- **Flo graph:** follow-up filter scope; explicit scope not overridden; CSAT unsupported; tool-call limit; citations open the exact message; approval resume idempotency; rejection saves nothing; read-only runs need no approval; session isolation (graph and HTTP); prompt injection inside transcripts; mode mismatch rejected; unconfigured and failing models fail without demo fallback; connected answers validated against SQL numbers (invented numbers rejected, one bounded retry); model cannot add unrequested actions or widen scope; cancellation; LangSmith-disabled operation.
- **Security:** CSV formula injection and redaction patterns.
- **Multilingual:** message-level language detection; code-switching and Romanized text; translation checks; separation of synthetic multilingual data.

The frontend tests cover:

- CSV formula injection,
- XSS-safe rendering of transcript text,
- citation buttons,
- the chart frame (scope, table, CSV export, Ask Flo, empty state),
- heatmap cell/data consistency,
- filter chips.

## Real Kaggle data import (executed)

The file uploaded in this session was `twcs_30MB.csv`: the first rows of the Kaggle `twcs.csv`, tweet IDs 1–191,172, 29,999,948 bytes. It was imported with:

`uv run python -m app.ingestion.cli file ../data/imports/twcs_30MB.csv`

The import took 52 seconds.

| Measure | Value |
|---|---|
| Rows read / unique messages | 159,240 / 159,240 |
| Reply threads | 41,661 |
| Eligible threads | 40,914 |
| **Selected (seed 20240601)** | **3,000** conversations, 11,359 messages |
| Excluded: not customer-initiated | 577 |
| Excluded: conversation start missing from file | 154 |
| Excluded: more than 50 messages | 16 |
| Not sampled | 37,914 |
| Cycles / conflicting duplicates | 0 / 0 |
| Selected threads with branches | 420 (543 branch points); median 2 messages, max 42 |
| Partial conversations | 412: replies referenced in `response_tweet_id` but cut off by the 30 MB extract |
| Message languages | en 9,927 · unknown 904 · es 157 · fr 94 · pt 94 · ja 74 · de 71 · others < 10 each |
| Redactions | handles 8,282 · URLs 2,489 · agent sign-offs 2,169 · IDs 133 · phones 55 · IP 3 · card 1 · name 1 |
| Date range | 31 Jan 2012 – 3 Dec 2017 |

### Rules labels on real data

| Label | Distribution (3,000 conversations) |
|---|---|
| Primary topic | other 1,129 · unknown 317 · app 328 · orders/delivery 279 · service 199 · billing 194 · account 188 · travel 176 · network 173 · cancellation 17 |
| Resolution | **unknown 2,719** · solution offered/unconfirmed 216 · confirmed resolved 33 · explicitly unresolved 32 |
| Ending sentiment | unknown 1,904 · neutral 769 · positive 256 · negative 71 |

The rules analyser was written for the fixture vocabulary. On real tweets most outcomes are unobservable: the median thread has two messages and many conversations move to DMs. The rules also miss many topics, so the overview shows large `unknown` and `other` groups instead of guessing.

The model analysis job (Connected analysis) is the intended labelling method for real data. It has **not been run**, because no model credentials were available.

### Scale test (synthetic, executed)

A synthetic file with the TWCS schema and real-world size (2.8M rows) imported in 139 seconds. It selected exactly 3,000 of 754,223 eligible threads.

## Docker (executed)

- Both images built and ran.
- Backend health check passed.
- nginx proxied `/api` and served the SPA with its CSP.
- A Flo SSE run completed in the browser with no console or CSP errors.

The build here needed the sandbox proxy CA injected through a scratch Dockerfile variant. The committed Dockerfiles are unchanged.

## Deterministic evaluations (demonstration rules system, executed)

Command: `uv run python -m app.evaluation.run --system rules`. These measure the **rules system on synthetic reference labels** and say nothing about model quality on real data.

| Suite | Per language (passed/n) |
|---|---|
| Topic classification | en 11/11 · es 2/2 · fr 2/2 · de 2/2 · hi-Latn 2/2 · mixed 1/1 · **pt 1/2** |
| Resolution extraction | **en 9/11** · es 2/2 · fr 2/2 · de 2/2 · hi-Latn 2/2 · mixed 1/1 · **pt 0/2** |
| Language identification | en 7/7 · es 6/6 · fr 5/5 · de 6/6 · pt 5/5 · hi-Latn 1/1 · **mixed 2/4** |
| Retrieval precision@5 (BM25 only, no semantic model) | en 26/30 · **es 0/4** · **mixed 5/10** · hi-Latn 1/1 |
| Tool selection | 8/8 |
| Numerical correctness | 8/8 |
| Unsupported-question handling | 6/6 |
| Citation validity | 72/72 |
| Prompt-injection resistance | 4/4 |

Weak spots stay visible by language:

- English queries cannot retrieve Spanish messages without multilingual embeddings.
- Portuguese outcomes are not covered by the rules lexicon.
- Samples per language are very small.

## Acceptance walkthrough

| # | Step | Status |
|---|---|---|
| 1 | Start the app without API keys | **Passed**: local and Docker |
| 2 | Explore clearly labelled demo data | **Passed**: banner, badges, "Synthetic fixtures" |
| 3 | Click a chart and inspect matching conversations | **Passed**: topic bar filters every chart; stacked segment opens explorer with matching count (test-verified) |
| 4 | Ask Flo a supported question | **Passed**: "Why is this happening?" on the refund scope, plus suggestions |
| 5 | Follow every citation to the correct message | **Passed**: browser walkthrough and 72/72 citation validity |
| 6 | Inspect actual execution events / explicit demo behaviour | **Passed**: tool activity, node states, agent execution map; demo answers labelled "rules-based, no model call" |
| 7 | Propose an action | **Passed** |
| 8 | Approve once and verify a single saved record | **Passed**: UI and API; a second approval returns 409 and creates no duplicate |
| 9 | Ask for CSAT without ratings | **Passed**: explicit "not available" limitation |
| 10 | Import Kaggle data and show real ingestion results | **Passed with partial data**: the 30 MB extract above. The full `twcs.csv` was not available in this environment. |
| 11 | Configure a model and run actual analysis | **Not verified**: no Anthropic or Bedrock credentials. Code paths are tested with scripted models. |
| 12 | Configure LangSmith and inspect a real trace | **Not verified**: no LangSmith credentials. Disabled operation is tested. |

## Not verified

- Live Claude calls (Anthropic API and Bedrock), real token usage and cost, and live LLM extraction quality.
- LangSmith traces, deep links, feedback upload and experiments.
- Semantic retrieval with sentence-transformers and FAISS. The model download is blocked here and the optional extra is not installed. The keyword path is verified.
- A multilingual-embedding versus translated-query retrieval comparison. The evaluation command exists but needs both an embedding model and a configured LLM.
- Original-text versus translated-text label comparison on real multilingual data (needs a model).
- Full-file (2.8M-row) import of the real Kaggle file. A synthetic file of the same size was tested.
