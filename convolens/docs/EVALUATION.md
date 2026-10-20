# Evaluation

```bash
cd convolens/backend
uv run python -m app.evaluation.run --system rules                       # demonstration rules system, synthetic references
uv run python -m app.evaluation.run --system llm --dataset <id>          # configured Claude model on an imported dataset
uv run python -m app.evaluation.run --system llm --dataset <id> --langsmith   # also upload the dataset + run a LangSmith experiment
uv run python -m app.evaluation.run --suite topic_classification,citation_validity
```

You can also run evaluations from the **Observability and evaluation** page. Results are stored in `eval_runs` and shown per suite **and per language** with sample sizes. Languages present in the data but without reference examples are listed as **unevaluated**.

## Suites

| Suite | Reference data | Check |
|---|---|---|
| `topic_classification` | `datasets/labelled_conversations.jsonl` (10 English) + 12 synthetic multilingual scenarios | Exact match with the reference topic |
| `resolution_extraction` | Same | Exact match with the reference resolution |
| `language_id` | Reviewed message languages in `data/demo/multilingual_reference.json` (including mixed and Romanized) | Exact match |
| `retrieval_relevance` | `datasets/retrieval.jsonl` (English) + multilingual reference questions | precision@5: a hit is relevant if its conversation's topic matches |
| `numerical_correctness` | `datasets/flo_questions.jsonl` | Every number in Flo's answer traces to a validated SQL metric, quote, limitation or the question |
| `citation_validity` | Flo answers to the questions | Each evidence ID resolves and its quote equals the stored redacted span (reported per language) |
| `unsupported_handling` | CSAT, NPS, revenue, churn, location and agent questions | Answer kind is `unsupported` and no tools ran |
| `tool_selection` | Expected tools per question | The expected tools are a subset of the tools executed; the scope is preserved |
| `prompt_injection` | `datasets/injection.jsonl` + the injected fixture tweet | No proposal, no forbidden text outside quotes, no record persisted |
| `reviewer_agreement` | Reviewer confirmations and corrections in the app | **Human judgment**: share of reviewed labels confirmed unchanged |

## Judgment types are kept separate

- `deterministic`: exact checks against references or recomputed values.
- `human`: reviewer confirmations and corrections.
- `llm_judge`: reserved for model-graded checks. It is always labelled "LLM-judge (not ground truth)" and never merged into deterministic scores. No LLM-judge suite has been run.

## Multilingual retrieval decision procedure

Both approaches are evaluated on the same `retrieval_questions` before either is chosen:

1. Set `EMBEDDING_MODEL` to a multilingual model, for example `paraphrase-multilingual-MiniLM-L12-v2`, and run `retrieval_relevance`.
2. Disable embeddings, translate the queries with the configured model, and pass them as `extra_queries` to `search()`. Then run the same suite.
3. Compare per-language precision@5.

This comparison is **not yet verified**. It needs the embedding model and a configured LLM, and neither is available in this environment.

## Latest results

See [TEST_RESULTS.md](TEST_RESULTS.md#deterministic-evaluations-demonstration-rules-system-executed).
