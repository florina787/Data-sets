# Evaluation

All figures below come from runs in this repository. The machine-generated report with every table is [`docs/evaluation/EVALUATION_RESULTS.md`](docs/evaluation/EVALUATION_RESULTS.md) (raw JSON: `data/manifests/evaluation_results.json`), produced by `make evaluate` (`backend/scripts/evaluate.py`). Re-running it regenerates both files.

**Model status during evaluation: Gemini unavailable.** The development environment's injected Gemini credential was rejected by Google (`401 API_KEY_SERVICE_BLOCKED`), and no other key was available. Everything below therefore measures the **deterministic path** (rules intent parser, deterministic labeller and narrative). The Gemini path is implemented and tested against a scripted SDK (§6) but **has not been verified against the live API**.

## 1. Methodology

| Area | Method | Data |
|---|---|---|
| Analytical correctness | (a) Hand-built fixture with hand-computed answers (exact counts, ranks, denominators, windows, agent metrics, turning points); (b) an **independent oracle** that re-implements Q1 from the raw CSV with its own regexes and score table and is compared with the system's answer. | `tests/fixtures/build_fixture.py`; real dataset |
| Intent classification | Labelled question set (40) on which the parser was tuned, plus a **held-out** set of 20 paraphrases written afterwards and scored once. | `tests/evaluation/datasets/` |
| Labelling | Template coverage; agreement between the lexicon fallback and template labels on all 21,639 real customer messages; blind human review (in-app). | real dataset |
| Retrieval | 36 paraphrased queries that avoid template wording (e.g. "billed two times for Wallet"); relevance = same issue topic (and product where named); P@5, hit-rate@5, MRR@5, duplicates, latency; random baseline. | real dataset |
| End to end | 40 single questions + 3 multi-turn sessions (11 follow-ups) through the full graph: QA pass rate per check, refusal of unsupported questions, follow-up routing, latency. | real dataset |
| Failure handling | Scripted failures: Gemini timeout, 429 with Retry-After, invalid JSON, invalid enums, 401 (circuit), 503 mid-request; corrupt FAISS index; missing DB; empty question; partial Gemini label coverage; client disconnect; backend error in the UI. | tests |

## 2. Results

| Metric | Result |
|---|---|
| Q1 numbers vs independent oracle (Nov 2025) | **exact match** — 682 conversations, 239 negative, all top-5 counts |
| Intent accuracy, tuning set (40) | 100% (after fixing 2 errors this set exposed — optimistic) |
| Intent accuracy, **held-out** (20) | **50%** — 7 of the 10 misses fail safe as "unsupported"; 3 misrouted (2 trajectory questions → conversation detail, 1 → topic frequency) |
| End-to-end QA pass rate (51 requests) | 100% (all 11 checks at 100%) |
| Unsupported questions refused | 6/6 |
| Follow-up routing (11) | 100% |
| Retrieval topic precision@5 (MiniLM) | **61.7%** (LSA fallback 36.7%; random baseline 12.5%) |
| Retrieval exact (topic+product) P@5 / hit-rate@5 / MRR@5 | 58.3% / 80.6% / 0.718 (LSA: 32.8% / 50.0% / 0.374) |
| Retrieval duplicate rate | 0% |
| Retrieval latency p50 / p95 | 35.4 / 61.8 ms MiniLM (LSA 18.5 / 20.7 ms), FAISS, local CPU |
| Lexicon fallback vs template labels (21,639 messages) | accuracy 78.1%, Cohen's κ 0.669 |
| End-to-end latency p50 / p95 | 167 / 776 ms (deterministic mode, MiniLM retrieval, local) |
| Automated tests | backend 97 (65 unit, 32 integration) · frontend Vitest 8 · Playwright E2E 10 — all passing |

### Retrieval by topic

The index was first built with the LSA fallback (Hugging Face was blocked at the time), then rebuilt with `sentence-transformers/all-MiniLM-L6-v2` once network access allowed the download; both runs use the same 36 queries.

| Topic | LSA topic P@5 | MiniLM topic P@5 |
|---|---|---|
| account_locked | 0.00 | 1.00 |
| app_crash | 0.04 | 0.84 |
| coupon_not_applied | 0.12 | 0.60 |
| duplicate_charge | 1.00 | 1.00 |
| general_help | 0.40 | 0.24 |
| not_received | 0.00 | 0.60 |
| payment_not_reflected | 0.20 | 0.00 |
| service_malfunction | 0.88 | 0.96 |

MiniLM fixes the paraphrases with no shared vocabulary ("cannot sign in, my profile is blocked" → account locked), but two topics got worse: generic help questions and "payment went through but X was never activated", which now retrieves other issue types. Hybrid lexical + vector scoring is the next improvement. When the model cannot be loaded, `EMBEDDING_BACKEND=auto` still falls back to LSA and records why.

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
