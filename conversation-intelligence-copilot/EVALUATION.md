# Evaluation

All figures below come from runs in this repository. The machine-generated report with every table is [`docs/evaluation/EVALUATION_RESULTS.md`](docs/evaluation/EVALUATION_RESULTS.md) (raw JSON: `data/manifests/evaluation_results.json`), produced by `make evaluate` (`backend/scripts/evaluate.py`). Re-running it regenerates both files.

**Model status during evaluation: Gemini unavailable.** The development environment's injected Gemini credential was rejected by Google (`401 API_KEY_SERVICE_BLOCKED`), and no other key was available. Everything below therefore measures the **deterministic path** (rules intent parser, deterministic labeller and narrative). The Gemini path is implemented and tested against a scripted SDK (§6) but **has not been verified against the live API**.

## 1. Methodology

| Area | Method | Data |
|---|---|---|
| Analytical correctness | (a) Hand-built fixture with hand-computed answers (exact counts, ranks, denominators, windows, agent metrics, turning points); (b) an **independent oracle** that re-implements Q1 from the raw CSV with its own regexes and score table and is compared with the system's answer. | `tests/fixtures/build_fixture.py`; real dataset |
| Intent classification | Benchmark v2: 288 questions in 95 paraphrase families, split by family into train / validation / test; test frozen and scored once ([INTENT_ROUTING.md](docs/evaluation/INTENT_ROUTING.md)). Legacy 40 + 20 sets kept for reference. | `tests/evaluation/datasets/` |
| Labelling | Template coverage; agreement between the lexicon fallback and template labels on all 21,639 real customer messages; blind human review (in-app). | real dataset |
| Retrieval | 36 paraphrased queries that avoid template wording (e.g. "billed two times for Wallet"); relevance = same issue topic (and product where named); P@5, hit-rate@5, MRR@5, duplicates, latency; random baseline. | real dataset |
| End to end | 40 single questions + 3 multi-turn sessions (11 follow-ups) through the full graph: QA pass rate per check, refusal of unsupported questions, follow-up routing, latency. | real dataset |
| Failure handling | Scripted failures: Gemini timeout, 429 with Retry-After, invalid JSON, invalid enums, 401 (circuit), 503 mid-request; corrupt FAISS index; missing DB; empty question; partial Gemini label coverage; client disconnect; backend error in the UI. | tests |

## 2. Results

| Metric | Result |
|---|---|
| Q1 numbers vs independent oracle (Nov 2025) | **exact match**: 682 conversations, 240 negative, all top-5 counts (rank 5 is a disclosed tie at 24) |
| Intent accuracy, tuning set (40) | 100% (after fixing 2 errors this set exposed — optimistic) |
| Intent accuracy, legacy held-out (20) | 50% at the time (superseded; the set was read during the v2 work) |
| Intent routing, **benchmark v2 test** (73) | **95.9%** (macro F1 0.932) confidence router + local Qwen; 90.4% with no model; previous router 61.6% |
| End-to-end QA pass rate (51 requests) | 88% — every critical check passes; 6 answers carry non-critical Evidence Challenger warnings (evidence coverage 92%, sample-size disclosure 90%). Before the challenger existed this read 100%. |
| Unsupported questions refused | 6/6 |
| Follow-up routing (11) | 100% |
| Retrieval topic precision@5 (hybrid, default) | **62.8%** (MiniLM alone 62.2%, LSA alone 28.9%; random baseline 12.5%) |
| Retrieval exact (topic+product) P@5 / hit-rate@5 / MRR@5 | hybrid 58.3% / 86.1% / 0.708 · MiniLM 56.1% / 83.3% / 0.711 · LSA 28.9% / 41.7% / 0.333 |
| Retrieval duplicate rate | 0% |
| Retrieval latency p50 / p95 | hybrid 38.6 / 53.2 ms · MiniLM 25.0 / 56.9 ms · LSA 15.7 / 21.0 ms (FAISS, local CPU) |
| Lexicon fallback vs template labels (21,639 messages) | accuracy 78.1%, Cohen's κ 0.669 |
| End-to-end latency p50 / p95 | 125 / 540 ms (deterministic mode, hybrid retrieval, local) |
| Automated tests | backend 138 · frontend Vitest 8 · Playwright E2E 17 (10 core + 7 for the six enhancements), all passing |

### Retrieval: LSA vs MiniLM vs hybrid (36 paraphrase queries)

Both embeddings are built and used. Hybrid search ranks with each index separately, then fuses the rankings with weighted Reciprocal Rank Fusion (k=60). The index holds the 3,000 supplied conversations (18,639 chunks).

| Method | Topic P@5 | Exact P@5 | Hit@5 | MRR@5 |
|---|---|---|---|---|
| LSA (TF-IDF + SVD, 192 dims) | 28.9% | 28.9% | 41.7% | 0.333 |
| MiniLM (all-MiniLM-L6-v2, 384 dims) | 62.2% | 56.1% | 83.3% | 0.711 |
| Hybrid, equal weights (measured once, not shipped)* | 51.1% | 47.8% | 66.7% | 0.591 |
| **Hybrid, LSA weight 0.15 (default)** | **62.8%** | **58.3%** | **86.1%** | 0.708 |

\* Measured on the earlier index build, which also contained the 120 generated demo conversations (filtered out at query time). LSA's vocabulary depends on the documents indexed, which is why LSA-only scores moved slightly (32.2% → 28.9% topic P@5) when the default build stopped indexing the demo data; MiniLM is unchanged.

**Disclosure.** The LSA weight (0.15) was chosen on these same 36 queries, so the hybrid row is optimistic relative to MiniLM alone. The gain over MiniLM is small: +2.2 points exact P@5 and +2.8 points hit rate, with MRR about equal. The honest reading: hybrid matches MiniLM on precision and finds a relevant conversation slightly more often, at about 14 ms extra median latency.

| Topic | LSA topic P@5 | MiniLM topic P@5 | Hybrid topic P@5 |
|---|---|---|---|
| account_locked | 0.00 | 1.00 | 1.00 |
| app_crash | 0.00 | 0.84 | 0.80 |
| coupon_not_applied | 0.16 | 0.60 | 0.72 |
| duplicate_charge | 0.60 | 1.00 | 1.00 |
| general_help | 0.20 | 0.32 | 0.48 |
| not_received | 0.00 | 0.64 | 0.40 |
| payment_not_reflected | 0.20 | 0.00 | 0.00 |
| service_malfunction | 0.92 | 0.88 | 0.92 |

LSA contributes on lexical matches. Every method misses "payment went through but the service was never activated" phrasings. When MiniLM cannot be loaded, `EMBEDDING_BACKEND=auto` falls back to LSA only and records why in the index manifest.

## 3. Classification evaluation — what can and cannot be claimed

* The original data contains 426 unique cleaned texts; **100%** of messages match a template, so labels are a deterministic mapping of templates to sentiment/act/topic.
* Topic and product extraction from the opening template is unambiguous (pattern match). Sentiment, empathy and resolution-fit mappings are **developer judgements** (ASSUMPTIONS.md §B). A developer-annotated "gold set" would only measure agreement with the same developer, so no accuracy is claimed for them.
* What is measured: the fallback's robustness (78.1% agreement; it misses urgency phrased without negative words, e.g. the Hinglish "Thoda jaldi please, flight in 2 hours." — recall 0.65 for negative) and, once people submit labels in the Governance panel, human agreement (accuracy, per-class P/R/F1, confusion matrix, κ, inter-annotator κ). **No human labels have been submitted yet**, so no human-agreement figures exist.
* Gemini classification (`make label`) and Gemini-vs-rules agreement: **not run** (model unavailable).

## 4. Grounding and quality checks

Every response passes through the QA agent; results are attached to the response and shown in the UI ("QA n/m"):

registered operations · filters applied · denominators (group totals equal scope totals) · ranking consistency · proportions in [0, 1] · chart data equals source table · evidence IDs resolve to source messages in scope · every number in the answer appears in the verified facts · uncertainty disclosed · coaching sample-size gate.

Pass rate on the 51-request evaluation: 100% for every check. The checks also fail when they should: during development the grounding check caught "95% CI" and numbers quoted from uncertainty notes as untraced (fixed by adding notes to the verified facts), and the scripted-Gemini test confirms an explanation with invented numbers is rejected.

## 5. Defects found by testing and evaluation (and fixed)

| Found by | Defect | Fix |
|---|---|---|
| Fixture test | "Last month" skipped a month whose data stopped one day early | Partial month = stops early **and** < 50% of median volume |
| Integration test | "The first one" could not resolve after a turn with no ranking | Resolve against the most recent ranking in the session, and say so |
| Evaluation | "Which agents should be fired?" was answered as coaching | Personnel-decision questions are refused (tests added) |
| Synthetic mode | Coaching crashed when no resolution was assessable | Nullable float handling + regression test |
| Screenshots | A cancelled request was recorded as "failed" | Recorded as "cancelled" |

## 6. Gemini path (scripted, not live)

`tests/integration/test_gemini_adapter.py` and `test_graph.py` drive the real `GeminiClient` with a scripted SDK: structured output parsing, cache hits, one bounded repair on invalid JSON, rejection after a second invalid output, 429 retry honouring `retryDelay`, timeout retries then failure, permanent 401 opening the circuit, streamed usage aggregated as cumulative (145 tokens, not 275), Gemini intent + grounded explanation accepted, ungrounded explanation rejected, outage mid-request falling back to rules. Live behaviour (latency, real token counts, label agreement) is **unmeasured**.

## 7. Limitations of this evaluation

* The intent sets and paraphrase queries were written by the developer; the held-out score is the more honest estimate.
* One dataset, synthetic and highly templated; topic-level differences in negative rate are mostly not statistically significant, which the app reports.
* Latency is local, single-user, deterministic mode; no load testing.
* Visual testing is screenshot review plus Playwright assertions (layout, overflow, rendering), not pixel-diff regression.
