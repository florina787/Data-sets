# Reuse Matrix — what was taken from existing copilots

Audited 2026-11-07 by reading source (not READMEs). Projects found:

* **Conversational Intelligence Copilot = ConvoLens** — `convolens/` on `master` of this repo
  (FastAPI + LangGraph + React/Vite, Gemini/Claude via LangChain).
* **Excel Copilot = FloPilot** — `flopilot/` on branch `claude/keen-hopper-an50uq`
  (FastAPI + openpyxl + deterministic planner + tool harness, React/Vite UI). The brief called it
  "Jerome Excel Copilot"; the user pointed to FloPilot as that project mid-build.
* `enterprise-agentic-ai/`, `lexguard/` — also present; inspected at tree level only, not needed.

**Neither project contained a Qwen adapter** (ConvoLens: Gemini/Anthropic/Bedrock; FloPilot:
Anthropic/demo). There was no local Qwen runtime in the build container — see
`docs/ENVIRONMENT.md` for how one was stood up (llama.cpp server + Qwen2.5-Coder-3B GGUF).

Originals are untouched: CloudNova lives in its own folder `cloudnova/`; reused code was copied
and adapted (with a header naming the source file), not imported across projects, because both
sources depend on their own DB/auth/settings modules.

| Module | Source project | Existing path | Strategy | Adaptation | Tests |
|---|---|---|---|---|---|
| Tool harness: `ToolSpec`, registry, permissions, per-tool timeout, step budget, step trace | FloPilot | `backend/app/harness/runtime.py` | REUSE_WITH_ADAPTER | dropped workbook/version/auth/cost fields; trace kept in memory + SQLite; only `read` permission is model-invocable | `tests/test_harness.py` |
| `AppError` safe error type (`code`, safe `message`, `status`, `retryable`) | FloPilot | `backend/app/common.py` | REUSE_AS_IS | — | `tests/test_api.py` |
| `LLMProvider.complete()` protocol + `provider_status()` + "demo mode, no silent fallback" semantics | FloPilot (+ ConvoLens `llm/provider.py` "no fallback" rule) | `backend/app/llm/providers.py` | EXTEND | new `QwenProvider` (OpenAI-compatible `/v1/chat/completions`, works with Ollama, llama.cpp, vLLM, LM Studio) | `tests/test_llm.py` |
| Instruction-like text (prompt-injection) detector | FloPilot | `backend/app/workbook/security.py` `_INSTRUCTION_LIKE` | REUSE_AS_IS | applied to questions instead of cells | `tests/test_governance.py` |
| Deterministic planner first, LLM second | FloPilot | `backend/app/agent/planner.py`, `supervisor.py` | REUSE pattern | new metric/dimension planner for finance (workbook planner is cell/range-oriented) | `tests/test_planner.py` |
| Grounding check (narrative numbers must appear in tool output) | FloPilot | `backend/app/agent/grounding.py` | REUSE pattern | numeric token extraction over result rows | `tests/test_governance.py` |
| Conversation memory (session → turns) | ConvoLens / FloPilot | `app/agent/context.py` | REUSE pattern | SQLite table, stores last `QueryPlan` for follow-ups | `tests/test_planner.py` |
| Data cleaning (`cleaning.py`), profiling, quality | FloPilot | `backend/app/workbook/{cleaning,profile,quality}.py` | NOT_RELEVANT (logic) | openpyxl cell-level; CloudNova needs column-level finance rules → new `app/pipeline/` driven by the data contract | — |
| Formula engine, recalc, fidelity, change-sets | FloPilot | `backend/app/workbook/*` | NOT_RELEVANT | read-only analytics; no workbook edits | — |
| Embeddings / retrieval index | ConvoLens | `backend/app/retrieval/*` | NOT_RELEVANT | Track B is SQL, not RAG | — |
| Design tokens / chart card layout / KPI tiles | FloPilot `app.css`, ConvoLens `charts/ChartCard.tsx`, `components/ui.tsx` | | REUSE_WITH_ADAPTER (visual language) | rebuilt as a no-build static page (vanilla JS + vendored Chart.js) styled from the user's NOVA reference images, so reviewers don't need Node | manual + `tests/test_api.py` serves `/` |
| React apps (pages, routing, state) | both | `frontend/src/**` | NOT reused | coupled to their domain APIs; a Node build would add a second toolchain for a non-scored item (UI polish) | — |
| CI workflow shape | ConvoLens | `.github/workflows/convolens-ci.yml` | REUSE_WITH_ADAPTER | new `cloudnova-ci.yml` running pytest + evals | CI |
