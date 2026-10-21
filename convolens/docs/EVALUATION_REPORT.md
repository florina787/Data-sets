# Evaluation report

Measured on 22 October 2026. Every number below comes from a command in this repository; where a judgment is
not human ground truth, it says so.

## 1. Retrieval quality on real data

Command:

```bash
EMBEDDING_PROVIDER=gemini uv run python -m app.evaluation.retrieval_eval --dataset <300-sample id>
```

- **Questions:** 17 paraphrased support questions (`app/evaluation/datasets/retrieval_real.jsonl`), written to avoid the
  exact keywords of the matching tweets, across 8 topics.
- **Dataset:** the 300-conversation sample of the real Kaggle data (all Gemini-labelled, all customer messages embedded).
- **Relevance:** a hit is relevant when its conversation's primary topic equals the question's target topic.
  These are **silver judgments from Gemini's labels, not human ground truth.**
- **Recall@5** uses every conversation with the target topic as the relevant set, so it is low by construction
  (5 hits against dozens of relevant conversations).

| Mode | Precision@5 | Recall@5 | MRR | nDCG@5 | Irrelevant evidence |
|---|---|---|---|---|---|
| Keyword (BM25) | 0.341 | 0.048 | 0.667 | 0.386 | 65.9% |
| Semantic (Gemini `gemini-embedding-001`, FAISS) | **0.671** | **0.117** | **0.897** | **0.698** | **32.9%** |
| Hybrid (reciprocal-rank fusion) | 0.600 | 0.092 | 0.676 | 0.596 | 40.0% |

**Findings.** Semantic search roughly doubles precision over keywords. Equal-weight fusion lets weak keyword matches
dilute the semantic ranking, so hybrid scores below semantic alone. Re-weighting the fusion should be tuned on a
separate question set, not on these 17, to avoid over-fitting.

On the full 3,000, semantic search is **not yet available** (5,641 customer texts still need embeddings), so Ask Flo
uses keyword retrieval there. In the acceptance run, 2 of 13 quotes were weakly relevant.

## 2. Label accuracy against human review

**Not measured yet: 0 human reviews.** The Human review page collects blind labels; the accuracy endpoint now reports,
per system and field: accuracy with a Wilson 95% interval, per-class precision/recall/F1, macro and weighted F1, and the
confusion matrix (`app/evaluation/metrics.py`, `app/analytics/review.py`). Target: ≥ 100 stratified reviews.

## 3. Agent and answer checks (synthetic reference set, deterministic)

From `python -m app.evaluation.run` on the synthetic fixtures (see [EVALUATION.md](EVALUATION.md)):
tool selection 8/8, numerical correctness 8/8, citation validity 72/72, unsupported-question refusals 6/6,
prompt-injection resistance 4/4. These are small synthetic sets, not real-data accuracy.

## 4. Live runs on the real 3,000 (Gemini)

See [ACCEPTANCE_TEST.md](ACCEPTANCE_TEST.md): 5 live runs, all claims validated, counts cross-checked with SQL,
latency 2.5–11.7 s, tokens as reported by the provider.

## 5. Not measured

Human-judged groundedness and citation relevance at scale, hallucination rate on real data, cost in currency
(free tier: no charge; paid pricing not configured), P95 latency over a larger run set.
