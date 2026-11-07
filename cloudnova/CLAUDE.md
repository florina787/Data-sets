# CLAUDE.md — how AI agents must work in this project

You are building **CloudNova Revenue Intelligence Copilot** (Track B: spec-driven pipeline +
natural-language query layer). Read this before touching code.

## Sources of truth (in priority order)
1. `docs/ASSIGNMENT.md` — the take-home brief. Wins on scope.
2. `data/raw/BUSINESS_CONTEXT.md` — business rules. Wins on numbers.
3. `specs/*.md` — our decisions on top of 1–2. **Code follows specs; if code needs to differ,
   change the spec first (with a change-log line), then the code, then the tests.**

## Hard rules
- **Numbers come from DuckDB, never from the LLM.** The LLM may route, write SQL, or phrase text.
  Any narrative number must exist in the result rows (`app/governance/grounding.py`).
- Business constants (list prices, FX, 10-month annual billing, status map) live only in
  `app/config.py` / `app/pipeline/rules.py`. Do not repeat them in other modules.
- `evals/oracle.py` must **not** import from `app/`. It is an independent re-implementation of
  the spec so that it can disagree with the pipeline.
- Never default an unknown plan/status to a known one. Quarantine it into `rejected_rows`.
- Never impute `csat_score`, `industry`, or `churned`.
- Every raw row ends up in exactly one of `invoices` or `rejected_rows` (test enforces it).
- SQL from the LLM: single SELECT, allow-listed tables/columns, read-only connection,
  external access disabled. Do not weaken `app/governance/sql_guard.py` to make a test pass.
- No paid APIs, no API keys. LLM = local Qwen through an OpenAI-compatible endpoint
  (`LLM_BASE_URL`). If it is down, analytics still work; general chat returns `llm_unavailable`.
- Don't commit `.env`, `data/processed/`, `data/runtime/`, model weights.

## Commands
```bash
pip install -r requirements.txt
python -m app                 # build data (if needed) + answer the six stakeholder questions
python -m app serve           # API + UI on :8000
python -m pytest -q           # unit tests (no LLM needed)
python -m evals               # eval harness (no LLM needed); add --llm to include Qwen cases
```

## Style
Python 3.11+, type hints, small modules, no framework where 50 lines will do. Errors raised as
`AppError(code, safe_message, status)` (pattern reused from FloPilot). Prefer editing an existing
function to adding a parallel one.
