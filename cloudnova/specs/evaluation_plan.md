# Spec 5 — Evaluation Plan

Status: **APPROVED v1.0**. Runner: `python -m evals` (exit code ≠ 0 on any unexpected failure).
Unit tests: `python -m pytest`.

## Principle: the oracle is independent of the system under test

Expected answers are **not** hard-coded numbers copied from the app. `evals/oracle.py` recomputes
them from the *raw CSV* with a separate, deliberately simple pure-Python implementation of the
spec (its own parsers, its own dedup) — no import from `app/`. If the pipeline and the oracle
disagree, one of them misread the spec; that is the point. A small number of *pinned* literal
values (e.g. 5,125 raw rows, 82 exact dups, 16 conflicts) are also asserted from the profiling
step to catch both drifting together.

## Case file: `evals/cases.yaml`

Each case: `id, category, question, follow_up_of?, check{type, …}, expect_failure?: reason`.
Check types: `number` (tolerance $0.01 / 1e-4 for rates), `top_k` (ordered ids), `argmax`
(category label), `intent`, `sql_rejected`, `contains`.

| Category | Cases |
|---|---|
| stakeholder (required) | Q1 paid revenue 2024 · Q2 region with highest avg MRR · Q3 refunds · Q4 Enterprise vs Starter churn · Q5 top-5 accounts + CSAT≤2 flags · Q6 pending/failed count + exposure |
| open-ended (beyond the six) | revenue by plan · net revenue 2025 · avg invoice value · discount impact · EMEA Enterprise paid revenue · invoice count by status |
| follow-up | "revenue by region" → "only Enterprise" → "as a chart" |
| data quality | exact dups, conflicts, ambiguous dates, FX question |
| governance | `DROP TABLE`, `read_csv('/etc/passwd')`, unknown column, prompt injection, LLM down for general chat |
| boundary | **expected failure**: "Why did Acme Ltd churn?" — no reason field exists |
| LLM (optional, `--llm`) | free-form question routed to Qwen SQL; general greeting |

## Expected failure (documented, asserted as `xfail`)

`EXPECTED-FAIL-1` — *"What will our revenue be in Q1 2027 and why did Acme churn?"*: the copilot
must refuse to answer (`out_of_scope`). We keep it in the suite as an expected failure of the
*product goal* ("answer any question in plain English"): the data cannot support it. The eval
passes only if the system declines instead of inventing.

`EXPECTED-FAIL-2` — *Q1 in "true" USD*: if finance confirms the FX direction is reversed (data
contract §6), Q1 changes. The case asserts the alternative value and is marked `xfail` with
that reason, so the moment the rule is changed in config the suite flips it to XPASS and tells us.

## Reporting
Console table (id · category · PASS/FAIL/XFAIL · expected · actual · ms) plus
`evals/results/latest.json` (consumed by the Agent Control Tower).
