# Existing capability audit (Phase 0)

Audited 2026-11-10 by checking out both branches and running their test suites. Both folders were imported into this integration branch **byte-identical** (verified with `git diff --quiet`), and the source branches were left untouched.

## Baseline test results

| Project | Branch | Command | Result |
|---|---|---|---|
| A. conversation-intelligence-copilot | `claude/happy-edison-gef7ay` | `uv run pytest` (also with `LLM_ENABLED=false`, as its CI does) | **163 passed, 2 failed** |
| B. archai-enterprise-advisor | `claude/gracious-pascal-83suux` | `pytest` | **76 passed** |

Project A's two failures reproduce with the LLM disabled, so they are real defects and not environment noise:

* `test_graph.py::test_general_question_gets_a_labelled_model_answer`: 2 model calls where 1 is expected.
* `test_graph.py::test_off_topic_question_is_gated_without_any_model`: an off-topic question is routed to "clarify" instead of being gated.

These were left unfixed: Project A is preserved as-is. Its README badge also claims 138 tests, but 165 are now collected.

## Feature matrix

| Capability | Project A | Project B | Reusable | Missing | Planned action |
|---|---|---|---|---|---|
| React frontend | Yes (React 18, Vite, Tailwind, React Flow) | No (Streamlit) | Stack choices | n/a | Florome uses the same stack |
| FastAPI backend | Yes | Yes | Patterns | n/a | New Florome API |
| LangGraph orchestration | Yes | Yes | n/a | n/a | Florome's RCA/actions are deterministic services; LangGraph not needed yet |
| Deterministic analytics | DuckDB registry | Decision engine | B's engine via adapter | n/a | **Done**: `/api/v1/architecture` |
| Evidence Challenger | Yes (conversation analytics) | Architecture challenger | Concept and causal-language rules | Ops/RCA version | **Done**: `florome/rca/challenger.py` |
| Root-cause analysis | Associational, conversation data | No | Statistical approach | Cross-platform operational RCA | **Done**: `florome/rca/engine.py` |
| PII / injection screening | Yes | Yes (guardrails) | Patterns merged | Credential redaction | **Done**: `florome/security/` |
| Autonomy / approval policy | No | Advisory model (autonomy levels) | Concepts | Enforced approvals | **Done**: `florome/governance/policy.py`, `actions/service.py` |
| Guardrails (budgets, allow-lists) | No | Yes | Concepts | Runtime enforcement | **Done**: action budgets, allow-lists |
| Decision replay / observability | Yes (replay store) | Tracing metrics | n/a | Audit chain | **Done**: hash-chained audit |
| MCP integration | **No** | **No** | n/a | Everything | **Done**: MCP gateway |
| REST/SDK connectors | No | No | n/a | Everything | **Partial**: sandbox plus GitHub (mock-tested) |
| Remediation execution | No | No | n/a | Everything | **Done** against the sandbox |
| Local Qwen | Yes (llama.cpp) | No | Client code | n/a | Not used: Florome's reasoning is deterministic. See readiness doc |
| Tests | 165 | 76 | n/a | n/a | Florome: 64 backend + 12 frontend |

## Security and technical debt observed

* Neither project has authentication. Florome adds demo-token auth only; live OIDC is not implemented, so live tenants fail closed.
* Project B's branch is based on an older `master` (its `convolens/` differs). That folder was not imported.
* Both projects pin different LangGraph versions. Florome does not depend on LangGraph, which avoids the conflict.
