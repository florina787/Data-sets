# CloudNova Revenue Intelligence Copilot

**Track B — spec-driven cleaning & modeling pipeline + natural-language query agent.**
Ask CloudNova's finance questions in plain English and get an answer you can audit: the number, **the exact SQL
that produced it**, the metric definition, and the data-quality caveats that touch it. Runs fully local
(DuckDB + a local Qwen model); no API keys, no paid services.

> **3-minute summary for a CloudNova stakeholder**
> * Your export had **5,125 rows**; it describes **5,000 invoices**. The other 125 are duplicates or conflicting
>   copies from your three systems. Counting them naively would overstate paid revenue by **$2,121,660.87**.
>   Every removed row is kept in an audit table with its reason.
> * All six of your questions are answered and **checked against an independent re-computation** (below).
> * Two things need *your* decision, and the tool shows both answers until you decide: the **FX direction** in the
>   export (EUR/GBP amounts look already converted) and **what "customer" means** (3,815 account ids vs 200 names).
> * The AI never invents numbers: approved metrics are compiled to SQL deterministically; the local LLM only writes
>   SQL for questions outside the catalog, and that SQL is guarded, read-only and labelled "check this query".

---

## 1. Run it

**Prerequisites:** Python 3.11+ (tested on 3.13), ~2 GB disk for the model. Optional: a local Qwen server.

```bash
cd cloudnova
pip install -r requirements.txt
```

```bash
python -m app
```

That single command (tested end-to-end from a clean `env -i` shell, see §7) validates config, builds or reuses the
cleaned DuckDB, connects to local Qwen (or starts it via `LLM_START_CMD`), runs the six stakeholder questions as a
readiness check, starts the API + dashboard and prints:

```
READY in 2.0s
  Dashboard   http://127.0.0.1:8000/
  Ask (API)   POST http://127.0.0.1:8000/ask   {"question": "..."}
  Health      http://127.0.0.1:8000/health
  API docs    http://127.0.0.1:8000/docs
```

| Other commands | |
|---|---|
| `python -m app demo` | terminal only: the six questions with answers, SQL and caveats, then exit |
| `python -m app ask "revenue by region in 2025"` | one question (`--session ID` keeps follow-up context) |
| `python -m app chat` | multi-turn terminal chat ("only Enterprise", "as a chart", "explain the calculation") |
| `python -m pytest` | 114 unit tests, no LLM needed |
| `python -m evals` / `python -m evals --llm` | eval harness (deterministic / including local-Qwen cases) |
| `python -m evals.compare_modes` | hybrid vs Qwen-only measurement (needs Qwen) |

**Local Qwen (optional, needed only for general chat and free-form SQL).** Any OpenAI-compatible local server works.
Ollama: `ollama pull qwen2.5-coder:3b` then set nothing (defaults match). llama.cpp (what this was built and
measured with — Ollama's binary could not be downloaded in the build container):

```bash
pip install "llama-cpp-python[server]" huggingface_hub
```

```bash
python -c "from huggingface_hub import hf_hub_download as d; print(d('Qwen/Qwen2.5-Coder-3B-Instruct-GGUF','qwen2.5-coder-3b-instruct-q4_k_m.gguf',local_dir='models'))"
```

Then either start it yourself on port 11434, or put the start command in `.env` as `LLM_START_CMD=...` (see
`.env.example`) and `python -m app` will start it, health-check it, and stop it on shutdown. **If Qwen is not
available the app still starts** ("deterministic mode"): all approved-metric analytics, data quality, the dashboard
and the evals work; general chat and free-form SQL return a clear `llm_unavailable` error instead of a guess.

---

## 2. The spec (written first, drives code and tests)

| Spec | What it fixes |
|---|---|
| [`specs/cloudnova_data_contract.md`](specs/cloudnova_data_contract.md) | cleaned schema & types, dedup rule, category maps, **evidence-based date rule**, amount parsing, FX, account snapshot, audit tables, open questions |
| [`specs/financial_metrics.md`](specs/financial_metrics.md) | every metric as SQL; how each stakeholder question maps to a metric |
| [`specs/query_interface.md`](specs/query_interface.md) | `/ask` contract, two planners, SQL governance layers |
| [`specs/agent_contracts.md`](specs/agent_contracts.md) | the one agent's tools, permissions, budgets, refusal boundaries |
| [`specs/evaluation_plan.md`](specs/evaluation_plan.md) | independent oracle, case types, documented expected failures |

Key rules (all from `data/raw/BUSINESS_CONTEXT.md`, decisions marked ⚑):
* Status map exactly as briefed; **paid** = revenue, **refunded** = negative and nets, pending/failed/void excluded.
* MRR = `list_price[plan] × seats × (1 − discount/100)` in USD — never derived from the (annual) invoice amount.
* Annual invoices bill 10 months (used for the pricing check: 0 violations found).
* ⚑ Dates: `NN/NN/YYYY` = **MM/DD** (first part never > 12 in 1,320 rows), `NN-NN-YYYY` = **DD-MM** (first part > 12 in
  151 rows, second never). Remaining ambiguous rows are flagged, not guessed silently.
* ⚑ Dedup: exact duplicates → synonym duplicates → for real status conflicts, **refunded > paid > failed > void > pending**
  (evidence of money movement beats a stale state). Losers kept in `rejected_rows`.
* ⚑ "Revenue" alone = recognized revenue **net of refunds**; "paid invoices" = paid only (spec v1.1 change log).
* ⚑ Account attributes = the account's latest invoice (no `updated_at` exists). Unknown plan/status → quarantined,
  never defaulted. CSAT/industry/churn never imputed.

## 3. The six stakeholder questions — actual output, independently verified

Expected values are computed by [`evals/oracle.py`](evals/oracle.py): a separate stdlib-only re-implementation that
reads the **raw CSV** and does **not** import the app. All six match to the cent.

| # | Question | Answer (from `python -m app demo`) | Oracle | SQL (abridged) |
|---|---|---|---|---|
| 1 | Recognized revenue in USD for **paid** invoices in 2024 | **$32,686,371.16** (net of 2024 refunds: $30,755,088.36) | ✓ | `SUM(amount_usd) FILTER (WHERE status='paid') … WHERE invoice_year = 2024` |
| 2 | Region with highest average MRR per account | **APAC, $6,147.30** (NA 5,632.84 · EMEA 5,327.66 · LATAM 5,187.55; active accounts) | ✓ | `AVG(current_mrr_usd) FILTER (WHERE is_active) FROM accounts GROUP BY region` |
| 3 | How much given back in refunds | **$8,925,163.80** across 292 refunded invoices | ✓ | `SUM(amount_usd) FILTER (WHERE status='refunded')` |
| 4 | Churn rate, Enterprise vs Starter | **Enterprise 21.92%** (171/780) vs **Starter 18.81%** (354/1,882) | ✓ | `AVG(churned) … FROM accounts WHERE plan IN ('Enterprise','Starter') GROUP BY plan` |
| 5 | Top 5 accounts by revenue, flag CSAT ≤ 2 | Stark Inc ACC-7509 $1,210,592.75 · Tyrell Industries ACC-1420 $1,208,092.75 (CSAT blank → "unknown") · Initech LLC ACC-9946 · Pied Piper Partners ACC-1196 · Oscorp Industries ACC-5211 — **none has CSAT ≤ 2** | ✓ | `… FROM invoices i JOIN accounts a … GROUP BY i.account_id ORDER BY net_revenue DESC LIMIT 5` |
| 6 | Invoices stuck in pending/failed and $ exposed | **894 invoices, $28,983,255.91** (pending 498 / $15.83M · failed 396 / $13.16M) | ✓ | `COUNT(*), SUM(amount_usd) FILTER (WHERE status IN ('pending','failed'))` |

Each answer in the app also lists caveats that apply to *its* rows, e.g. Q1: "3 invoices came from conflicting
duplicates ($31,018.68 depends on that rule) · 24 ambiguous dates · under the inverse FX rule this would be
$29,595,624.38".

**Where we may be wrong (and say so):** Q1 depends on the FX open question (−$3.09M if the inverse rule is right).
Q5 changes completely if "account" means company name (expected-failure case below). Q2/Q4 depend on the
latest-invoice snapshot (980 of 3,815 accounts have conflicting attributes across invoices).

## 4. Evaluation

```text
python -m evals --llm      (2026-11-07, local qwen2.5-coder:3b on 4 CPU threads)
PASS=33  FAIL=0  XFAIL=3  XPASS=0  SKIP=0
```
* 6 stakeholder · 10 open-ended (beyond the six) · 4 multi-turn follow-ups · 2 data-quality · 8 governance ·
  1 boundary · 2 local-Qwen · **3 documented expected failures** (`evals/cases.yaml`):
  1. *"Top 5 customers by revenue"* — if "customer" = company name (200 names over 3,815 ids) the top 5 is different.
     Needs CloudNova's decision on account identity.
  2. *Q1 under the inverse FX rule* — flips to XPASS the moment `FX_DIRECTION=inverse` is confirmed.
  3. *Qwen text-to-SQL, "support tickets churned vs active"* — Qwen writes valid-but-wrong SQL (filters to active
     accounts, deleting the churned group). The guard checks safety, not meaning.
* Without Qwen (CI default): `PASS=31 FAIL=0 XFAIL=2 SKIP=3`. Unit tests: **114 passed**.
* CI: `.github/workflows/cloudnova-ci.yml` runs build → pytest → evals → demo on every push touching `cloudnova/`.

### Hybrid vs Qwen-only (measured, `evals/results/mode_comparison.md`)

| Mode | Correct on the six | Median latency | Max |
|---|---|---|---|
| **Hybrid** (approved metrics first, Qwen fallback) — default | **6/6** | 10 ms | 61 ms |
| **Qwen-only** (`QUERY_MODE=llm`, Qwen-2.5-Coder-3B writes all SQL) | **2/6** | 20.6 s | 42.9 s |

Qwen-only failures: Q2/Q4 ambiguous join columns (runtime error); **Q4 invented `status = 'churned'`** (a business-logic
error even if it ran); **Q5 ranked by paid-only revenue**, swapping two accounts (wrong answer, no error); Q6
referenced a non-existent column (caught by the SQL guard). This is the evidence behind the hybrid design: a
3B local model is a useful *fallback*, not a safe *source of record*.

## 5. Production instincts

* **Read-only by construction:** DuckDB opened `read_only`, `enable_external_access=false`, config locked; plus a
  sqlglot structural guard (single SELECT, allow-listed tables & columns, no table functions / COPY / ATTACH / PRAGMA).
  20 attack queries in `tests/test_governance.py`; the DB is also tested to refuse writes *if the guard were bypassed*.
* Query timeout (interrupt), row cap with `truncated` flag, PII (email) masked in results, prompt-injection text flagged
  and treated as data, write requests refused, out-of-scope questions ("why did X churn", forecasts) declined.
* Structured errors `{code, message, retryable}` (no stack traces), versioned API `/api/v1/*`, config via env /
  `.env.example`, no secrets, pinned dependencies, idempotent build keyed on the raw file's sha256.
* Observability: every request's trace (route, tools, ms, status) persisted to SQLite and shown in the Agent Control
  Tower with an execution graph; eval results surfaced there too.
* Integration seam: `app/sources/` adapters emit the raw contract; see [`docs/INTEGRATION_ARCHITECTURE.md`](docs/INTEGRATION_ARCHITECTURE.md).

## 6. Design decisions & trade-offs

| Decision | Why | Cost |
|---|---|---|
| Track B over RAG | aggregation questions need SQL, not retrieval | no semantic search over free text (there is none in the data) |
| Hand-rolled semantic layer (~300 lines) instead of LangChain/dbt metrics | auditable, testable, zero deps; measured 6/6 | phrasing outside the catalog falls back to Qwen |
| pandas for cleaning, DuckDB for serving | row-wise rule functions are easy to unit-test; DuckDB gives typed, read-only SQL | 5k rows — would move to SQL/dbt at scale |
| Conflict precedence instead of "drop both" | keeps revenue complete and shows $ at stake | a rule the billing owner must confirm |
| Static dashboard (vanilla JS + vendored Chart.js) | no Node toolchain for reviewers | less component reuse than the React apps |
| Copy-and-adapt from FloPilot/ConvoLens, not import | those packages depend on their own DB/auth/settings | small duplicated helpers, each with a source header |
| Isolation Forest **not** shipped | deterministic pricing check finds **0** violations on this synthetic data; a statistical model would mostly flag large Enterprise invoices — not explainable value | see roadmap |

Reuse details: [`docs/REUSE_MATRIX.md`](docs/REUSE_MATRIX.md). Requirement-by-requirement evidence:
[`docs/REQUIREMENTS_TRACEABILITY.md`](docs/REQUIREMENTS_TRACEABILITY.md).

## 7. Startup verification (single command, tested)

Run from a clean shell (`env -i PATH=… HOME=… bash -c 'cd cloudnova && python -m app'`), 2026-11-07:

| Scenario | Result |
|---|---|
| Fresh clone (no `data/processed`), Qwen already running | data built in 0.7 s · Q1–Q6 ✓ · Qwen generation check 511 ms · **READY in 2.0 s** · Ctrl+C → "stopped cleanly" |
| Data present, Qwen down, no `LLM_START_CMD` | data **reused** (sha256 unchanged) · warning + deterministic mode · **READY in 0.8 s** · `/ask` analytics ✓, chat → `llm_unavailable` · SIGTERM → clean exit |
| Qwen down, `LLM_START_CMD` set (llama.cpp) | Qwen started & healthy in 3.0 s · **READY in 4.5 s** · SIGTERM → API drained, **the Qwen process it started was stopped** |
| Port already in use | exits with code 2: "port 8000 … already in use" |

Qwen-backed answers take 5–30 s on 4 CPU threads; approved-metric answers take < 100 ms.

## 8. Known limitations & failure modes

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md). Headlines: FX direction unresolved; "account" identity ambiguous;
churn is a snapshot flag (no dates → no period churn rate, no "why"); 111 invoices are future-dated and included;
the semantic planner is keyword-based (unusual phrasing may route to Qwen or to "clarify"); Qwen-3B produces
plausible-but-wrong SQL and occasionally wrong general definitions (it described NRR as logo retention).

## 9. What I'd do with another day

1. Get the two decisions from CloudNova (FX direction, account identity) and flip the expected failures.
2. Replace keyword routing with Qwen *intent → QueryPlan JSON* (constrained to the catalog) — keeps numbers
   deterministic while understanding more phrasings; evaluate with the existing harness.
3. Add `support_tickets`, tenure and signup-cohort metrics to the catalog (the most common Qwen fallbacks).
4. Move cleaning to SQL/dbt models with the same tests, so finance can review transformations in SQL.
5. A larger local model (Qwen2.5-Coder-7B/14B) re-measured with `python -m evals.compare_modes`.

## 10. How AI was used

Claude Code built this from the specs, steered by [`CLAUDE.md`](CLAUDE.md); the session log with prompts, decisions
and the places I overrode or corrected the AI is in [`.claude/prompt-history.md`](.claude/prompt-history.md).
Demo walkthrough: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). Architecture: [`docs/architecture.md`](docs/architecture.md).

## Repository map

```
cloudnova/
  app/            pipeline/ (rules, clean, build) · semantic/ (catalog, planner) · agent/ (supervisor, tools, harness,
                  memory, render) · governance/ (sql_guard, guards) · llm/ (Qwen provider) · sources/ (adapters)
                  reconciliation.py · api.py · startup.py · __main__.py · web/static (dashboard)
  specs/          five specs (written before code)
  evals/          oracle.py · cases.yaml · __main__.py · compare_modes.py · results/
  tests/          114 unit tests
  docs/           architecture · traceability · reuse matrix · limitations · integration · demo script · assignment
  data/raw/       the CSV + BUSINESS_CONTEXT.md (inputs, unchanged)
  .claude/        prompt-history.md (AI development log) · CLAUDE.md at project root steers the agent
```
