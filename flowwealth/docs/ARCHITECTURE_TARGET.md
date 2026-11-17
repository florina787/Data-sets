# Architecture — target (v4) and what exists today

Legend: ✅ implemented and tested · 🟡 partial · ⬜ planned

```mermaid
flowchart TD
  SRC[Global data sources<br/>⬜ licensed feeds · 🟡 Stooq/AlphaVantage/FRED adapters · ✅ synthetic] --> ING
  ING[Ingestion & validation ✅<br/>cache · retries · rate limit · freshness · provenance · quality score] --> LAKE
  LAKE[Point-in-time lake ✅<br/>Parquet + DuckDB · versioned · available_at · delisted names kept] --> FEAT
  LAKE --> KG[Event knowledge graph ⬜]
  FEAT[Feature store ✅<br/>leakage-safe · cohort ranks · lineage registry] --> REG
  REG[Regime & crash-risk ✅ rules + evaluation] --> ROUTER
  FEAT --> ROUTER[Model router 🟡<br/>✅ baselines · ridge · LightGBM ⬜ Qlib · XGBoost · FinBERT · FinRL · vol models]
  ROUTER --> AGENTS[Bull · Bear · Skeptic · Judge ⬜]
  ROUTER --> PROF[Trader profile router ✅ horizon × appetite]
  AGENTS --> PROF
  PROF --> RISK[Independent risk engine ✅<br/>no AI override input · hard caps]
  RISK --> UI[Dashboard ✅ 12 views · ⬜ news globe · alerts · paper-trading UI]
  RISK --> PAPER[Paper trading ✅ engine · ⬜ UI]
  ROUTER --> MEM[Prediction Memory ✅ append-only, hash-chained]
  MEM --> OUT[Outcome evaluation ✅] --> DRIFT[Drift & degradation ✅ PSI · rules]
  DRIFT --> CC[Champion–challenger ✅ criteria · approval · rollback]
  CC -->|versioned, reversible| ROUTER
```

## Component boundaries

| Concern | Module | Storage | Runs as |
|---|---|---|---|
| Contracts (DataStatus, Horizon, PredictionIn) | `flowwealth/contracts.py` | — | library |
| Provider adapters | `data/providers/` | Parquet cache + JSON meta | job |
| Lake | `data/lake.py`, `data/pipeline.py` | `lake/bars/version=*/year=*/*.parquet`, manifests | job (CLI) |
| Quality | `data/quality.py` | manifest `quality` | job |
| Features / labels | `features/build.py` | in-memory → Parquet (planned feature store) | job |
| Splits | `validation/splits.py` | — | library |
| Models | `models/forecasters.py` | ⬜ model artefact store | job |
| Research / backtest / costs | `research/` | `reports/*.json` | job |
| Prediction Memory | `memory/store.py` | SQLite (→ PostgreSQL) | service + job |
| Evaluation / drift / registry | `evaluation/` | registry JSON (→ PostgreSQL) | job |
| Profiles / risk engine / regime | `profiles/`, `risk/` | — | library + API |
| API | `api/app.py` | reads lake, artefacts | FastAPI service |
| Dashboard | `flowwealth/frontend` | localStorage (watchlist only) | static SPA |

## Storage mapping to production

* Parquet + DuckDB stay for the analytical lake (cheap, local, columnar).
* Prediction Memory and the model registry move to PostgreSQL. The SQLite triggers become `REVOKE UPDATE, DELETE` for the app role plus
  `BEFORE UPDATE/DELETE` triggers; the hash chain stays as tamper evidence.
* pgvector only for news/filing retrieval when the news agents exist; not used today.
* Redis is not needed yet (no high-frequency fan-out).
