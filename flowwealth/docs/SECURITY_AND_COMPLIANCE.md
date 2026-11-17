# Security, governance and compliance review

## Implemented

| Control | Where |
|---|---|
| No brokerage connectivity or order routing anywhere in the codebase | by design; paper trading is `mode="PAPER"` only |
| Independent pre-trade risk engine; no input for AI/agent opinions | `risk/engine.py`, signature test |
| Hard limits no profile, override or "aggressive" mode can exceed | `profiles/profile.py: HARD_LIMITS`, test |
| SYNTHETIC / stale data cannot pass the risk engine | horizon data requirements, tests |
| Immutable, tamper-evident forecast ledger | `memory/store.py` triggers + hash chain, tamper test |
| Model promotion needs evidence **and** a named human approver; rollback | `evaluation/registry.py`, tests |
| Input validation | pydantic models for API bodies; query regex/length limits on `range`, `q`; `limit ≤ 500` |
| Output validation | NaN/inf sanitised to `null`; no fabricated defaults |
| Secrets | API keys read only from environment (`ALPHAVANTAGE_API_KEY`, `FRED_API_KEY`); none committed |
| CORS | allow-list via `FLOWWEALTH_CORS` (default `http://localhost:5173`), GET/POST only |
| Disclaimers | footer on every page; `disclaimer` in health/status/rankings responses |
| Audit trail | registry log (register/refuse/promote/rollback with approver); ledger records |

## Not implemented yet (required before any multi-user or public deployment)

* **Authentication and role-based authorisation** — the API is unauthenticated and must stay on localhost/private network until added
  (ConvoLens' session layer is a candidate pattern).
* Rate limiting on the API; audit logging of API access; data-retention and user-consent controls (needed before behaviour analytics).
* Prompt-injection defences and structured-output validation for LLM agents (no LLM agents exist yet; ConvoLens/LexGuard have reusable guards).
* Secret scanning and dependency audit in CI.

## Regulatory position

FLOW WEALTH is framed as research and educational analytics. Personalised recommendations, portfolio advice to third parties, or any
execution integration may be regulated activity (e.g. investment-adviser registration in the US, FCA permissions in the UK, MiFID II in the EU).
A jurisdiction-specific legal review is required before enabling those features. Autonomous live trading is not available.
