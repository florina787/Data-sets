# Architecture — current state (audit, 2026-11-17)

## What the repository contained before this work

The audit covered `florina787/Data-sets` (branch `master` at `88a72f8`), the only repository reachable from this session.
**No FLOW WEALTH application existed in it**, and no other repository named FLOW WEALTH was attached or listed for the account.

| Path | What it is | Stack | Tests / CI | Touched? |
|---|---|---|---|---|
| `*.csv`, `*.zip`, `*.rar`, `*.ipynb` (root) | Teaching datasets and notebooks (cars, bank, airlines, OCR, Siamese nets…) | CSV / Jupyter | none | **No** |
| `convolens/` | ConvoLens AI: customer-conversation intelligence, "Flo" assistant | FastAPI + LangGraph + Gemini/Bedrock, React 19 + Vite + Tailwind | pytest + vitest, `.github/workflows/convolens-ci.yml` | **No** |
| `lexguard/` | LexGuard: legal-AI governance demo (matters, privilege, audit, control tower) | FastAPI, Next.js | pytest + vitest | **No** |
| `enterprise-agentic-ai/` | Agentic RAG copilot (supervisor, RAG, tool agents, guardrails) | FastAPI + LangGraph | pytest | **No** |

Findings that shaped the plan:

* There were no financial data adapters, market databases, trading models, risk logic, or prediction stores to preserve.
* Reusable *patterns* (not code) existed: FastAPI + pydantic contracts, React/Vite/Vitest frontend, uv-locked Python, path-filtered GitHub
  Actions CI, deterministic tests with no network/API keys, explicit data-status honesty in ConvoLens docs. FLOW WEALTH follows them.
* The existing LLM integrations (Gemini via the environment's proxy, LangGraph) are a natural base for the planned news and
  bull/bear agents; they were deliberately **not** wired in yet (see IMPLEMENTATION_PLAN.md, priority on evaluation infrastructure).

## Decision

FLOW WEALTH v4 was added as a new, self-contained top-level package `flowwealth/` (backend + frontend + docs + CI workflow).
Nothing outside `flowwealth/`, `.github/workflows/flowwealth-ci.yml` and one link line in the root README was modified, so all
existing applications and their CI are unaffected. If the real FLOW WEALTH codebase lives elsewhere, `flowwealth/backend/flowwealth`
is a plain Python package with no coupling to this repo and can be moved as-is.

## Environment constraints observed during the audit

| Check | Result |
|---|---|
| Yahoo Finance chart API | HTTP 429 (rate-limited) |
| Stooq CSV | HTTP 200 with empty body |
| FRED, GDELT | connection timeout |
| SEC EDGAR | HTTP 403 (requires declared User-Agent / not allowed by proxy) |
| PyPI, npm | reachable |
| Compute | 4 CPU, 15 GB RAM, no GPU |

Consequence: **no real market data could be ingested in this session.** All runs use the clearly-labelled SYNTHETIC generator.
