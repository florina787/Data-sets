# Implementation plan and phase status

Priority order (from the brief): data foundation → point-in-time integrity → evaluation infrastructure, ahead of agent count.
Status reflects **this session's executed evidence** (see EVALUATION_REPORT.md for outputs).

| Phase | Scope | Status | Evidence | Blocked by / next |
|---|---|---|---|---|
| 1 Foundation | audit, contracts, baseline tests, target architecture | ✅ done | 6 audit docs; `contracts.py`; 41 backend + 9 frontend tests | — |
| 2 Data intelligence | adapters, 1M+ pipeline, validation, PIT datasets, provenance | 🟡 engine done, **no real data** | 1,119,431-row versioned lake built in 6.4 s; quality score; as-of + survivorship tests | Market-data access (network blocked here); licensed provider keys |
| 3 News intelligence | 7 news agents, multilingual, knowledge graph | ⬜ not started | — | News-source licences/keys; Phase 2 real data to evaluate impact |
| 4 Quant research | Qlib, XGBoost/LightGBM, FinBERT, forecasting eval, regimes | 🟡 | LightGBM, ridge, 3 baselines; walk-forward + holdout; regime + crash-risk with precision/recall | Qlib/XGBoost/FinBERT integration; real data |
| 5 Multi-agent | bull, bear, skeptic, judge | ⬜ | UI states explicitly "not implemented" | Needs evidence store (Phase 3) to cite |
| 6 Adaptive trading | profiles, horizon modes, aggressive controls, cost simulation | 🟡 | profiles (horizon × appetite), hard caps, freshness gates, cost model | Intraday/tick data for swift & intraday engines |
| 7 Portfolio & risk | optimisation, crash-risk, contagion, options | 🟡 | pre-trade risk engine, crash-risk levels | Optimiser, VaR/CVaR, contagion graph, options data |
| 8 Continuous evaluation | prediction memory, outcomes, drift, champion–challenger, rollback | ✅ engine | immutable hash-chained ledger, outcome resolver, PSI, degradation rules, registry with approval + rollback | Scheduler for live forward predictions |
| 9 UX | dashboards, globe, rankings, scenarios, alerts | 🟡 | 12 dashboard views, rankings with methodology | News globe, what-if engine, alerts, paper-trading UI |
| 10 Validation & deploy | backtests, walk-forward, risk validation, paper, security, deploy docs | 🟡 | CI workflow, reproducible commands, security review | Real-data validation; hosting |

## Next increments (in order)

1. **Real EOD data** for a liquid universe (e.g. S&P 500 constituents *with historical membership*) via a licensed provider; rebuild the lake
   as `eod-v1`, re-run the experiment. Point-in-time index membership is mandatory to avoid survivorship bias.
2. **Scheduled forward predictions**: a daily job that records champion forecasts into Prediction Memory at the real clock and resolves due
   outcomes. This is the only way to get genuine out-of-sample evidence.
3. **Fundamentals with filing dates** (SEC EDGAR companyfacts; `available_at` = filing acceptance time) and FRED/ALFRED vintages.
4. XGBoost + Qlib Alpha158 features as challengers under the same splits and promotion criteria.
5. News ingestion (GDELT + licensed feeds) → entity linking → FinBERT sentiment as *features*, evaluated like any other.
6. Bull/Bear/Skeptic/Judge agents that may only cite evidence IDs from the lake/news store; Judge output feeds Prediction Memory, never the risk engine.
7. Paper-trading UI and alerts; portfolio optimiser with robust covariance and benchmark comparison.
