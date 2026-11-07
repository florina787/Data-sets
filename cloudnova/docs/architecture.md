# Architecture — CloudNova Revenue Intelligence Copilot (Track B)

Every box below is a real module; the path is in the label. Data flows top to bottom: raw input → processing →
store → query/answer.

```mermaid
flowchart TB
  subgraph SRC["1 · Source (read-only)"]
    CSV["cloudnova_invoices.csv<br/>5,125 rows · 19 string cols"]
    AD["Source adapter seam<br/>app/sources/base.py · CsvLedgerAdapter<br/>(raw contract + sha256 provenance)"]
    CSV --> AD
  end

  subgraph PIPE["2 · Spec-driven pipeline  (specs/cloudnova_data_contract.md, financial_metrics.md)"]
    RULES["Business rules<br/>app/pipeline/rules.py<br/>plan/status/cycle maps · dates · amounts · FX · MRR"]
    CLEAN["Clean + dedup + snapshot<br/>app/pipeline/clean.py<br/>exact → synonym → conflict precedence"]
    BUILD["Build typed DuckDB<br/>app/pipeline/build.py<br/>(skips if raw sha256 unchanged)"]
    AD --> CLEAN
    RULES --> CLEAN --> BUILD
  end

  subgraph STORE["3 · Store  data/processed/cloudnova.duckdb"]
    INV[("invoices<br/>5,000")]
    ACC[("accounts<br/>3,815 snapshot")]
    AUD[("rejected_rows 125 · dedup_conflicts 16<br/>dq_issues · monthly_revenue view")]
    BUILD --> INV & ACC & AUD
  end

  subgraph AGENT["4 · One query agent  (app/agent/supervisor.py on harness adapted from FloPilot)"]
    G1["Guards<br/>app/governance/guards.py<br/>length · injection flag · write-intent · out-of-scope"]
    R{"Router"}
    SEM["Semantic planner<br/>app/semantic/planner.py + catalog.py<br/>metric × dimension × filter → SQL"]
    LLMSQL["Qwen text-to-SQL (fallback)<br/>tools.run_llm_sql · 1 retry with error"]
    DQ["Data-quality / reconciliation<br/>tools.data_quality_report · app/reconciliation.py"]
    GEN["General chat<br/>tools.general_chat"]
    GUARD["SQL guard (sqlglot)<br/>app/governance/sql_guard.py<br/>single SELECT · allow-listed tables/cols"]
    EXEC["Read-only executor<br/>app/db.py · read_only · no external access<br/>timeout · row cap · PII mask"]
    GROUND["Grounding check<br/>numbers in Qwen narrative must be in rows"]
    MEM[("SQLite memory + traces<br/>app/agent/memory.py")]
    G1 --> R
    R -->|approved metric| SEM --> GUARD
    R -->|unmodeled measure| LLMSQL --> GUARD
    R -->|cleaning / dedup| DQ
    R -->|concept / greeting| GEN
    GUARD --> EXEC --> INV & ACC
    LLMSQL -.narrate.-> GROUND
    R <--> MEM
  end

  QWEN["Local Qwen2.5-Coder-3B<br/>OpenAI-compatible server (llama.cpp / Ollama)<br/>app/llm/provider.py · no API key"]
  LLMSQL <--> QWEN
  GEN <--> QWEN
  GROUND <--> QWEN

  subgraph OUT["5 · Interfaces"]
    CLI["python -m app (startup) · demo · ask · chat<br/>app/__main__.py · app/startup.py"]
    API["REST /api/v1/* (FastAPI)<br/>app/api.py"]
    UI["Dashboard (static, no build)<br/>app/web/static"]
    EV["Evals: python -m evals<br/>oracle.py recomputes from RAW CSV (no app imports)"]
  end
  R --> CLI & API
  API --> UI
  EV -.independent check.-> CSV
  EV -.asks.-> API
```

## Answer contract
Every analytics answer carries: natural-language answer (numbers formatted from result rows), the **exact SQL
executed**, metric definitions, filters, result rows, caveats (dedup conflicts, ambiguous dates, FX question in scope),
chart spec, and a step trace. See `specs/query_interface.md`.

## Why this shape
* **Deterministic first, LLM second.** Financial numbers come from approved SQL metrics; Qwen handles what the
  catalog cannot express and general conversation. Measured: hybrid 6/6 vs Qwen-only 2/6 on the stakeholder
  questions (`evals/results/mode_comparison.md`).
* **One store, read-only.** The chat path cannot write: DuckDB is opened `read_only` with external access disabled
  and the configuration locked, *and* every statement is parsed and allow-listed before it runs.
* **Audit tables, not deletes.** Every raw row is in `invoices` or `rejected_rows`; the reconciliation view is
  computed from them.

## Enhancement branch additions
`app/enhancements/leakage.py` and `simulator.py` read the same DuckDB tables through the same read-only connection;
`app/sources/legacy_billing.py` feeds the same `pipeline.clean()` in memory. Diagrams: `docs/enhancements/README.md`.
