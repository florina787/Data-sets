# Infrastructure and cost

## What runs where

| Part | Today | Free-tier option | Notes |
|---|---|---|---|
| Static dashboard | `npm run build` → `dist/` | GitHub Pages / Cloudflare Pages | Needs a reachable API URL; Pages cannot run the backend |
| API (FastAPI) | `uvicorn flowwealth.api.app:app` | Fly.io / Render free tiers (sleep on idle) | Holds lake frames in memory (~150 MB for 1.1M rows) |
| Lake build / experiments | CLI jobs, 6 s and 40 s at 1.1M rows | GitHub Actions (2,000 min/month private, unlimited public) | Keep lake in object storage (e.g. Cloudflare R2 free 10 GB) |
| Prediction Memory | SQLite file | Neon / Supabase free PostgreSQL | Needs durable storage; never on ephemeral disk |
| Scheduled forward predictions | not yet | GitHub Actions cron | Daily after US close |
| Local LLMs (future agents) | — | Ollama / llama.cpp on user hardware | No GPU here |

## Measured resource use (this container: 4 CPU, 15 GB RAM)

| Step | Time | Peak memory (approx.) |
|---|---|---|
| Generate + clean + write 1.12M rows | 6.4 s | < 1 GB |
| Features + 4-fold walk-forward + holdout, 5 models | 40 s | ~2–3 GB |
| Replay (fit + 800 forecasts) | ~20 s | ~2 GB |
| Full test suite | 8 s | < 1 GB |

Scaling to 5–10M rows is linear for the lake; feature building is pandas-groupby-bound (consider Polars or DuckDB SQL windows beyond ~10M).

## Paid costs that will appear

Licensed intraday/tick data, options data, and most news APIs are paid, and they dominate cost long before compute does.
Exchange display/redistribution fees apply if real-time prices are shown to other users.
