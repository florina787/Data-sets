# MuseFlow AI — Security Model (public demo)

The public build is a **simulation**. Its security goal is simple: a visitor can click anything
and nothing real happens, nothing costs money, and nothing they type leaks to anyone else.

## Guarantees and how they are enforced

| # | Requirement | Enforcement | Test |
|---|---|---|---|
| 1–4 | No Anthropic / OpenAI / Gemini keys, no paid LLM calls | No LLM SDK in `requirements.txt`; no code reads environment variables | `test_requirements_have_no_llm_clients`, `test_source_never_reads_api_keys_or_contains_secrets`, runtime import guard in `conftest.py` |
| 5–6 | No external credentials or production connectors | Only allowlisted, simulated tools exist (`services/tool_registry.py`) | `test_consequential_tools_refuse_without_approval` |
| 7–9 | No real email, calendar changes or browser transactions | Consequential tools only append to session lists; they refuse to run without a recorded approval | `test_approvals.py` |
| 10 | No shared persistent visitor memory | All mutable state lives in a per-session `SessionContext`; no `st.cache_*` on mutable data | `test_session_isolation.py` |
| 11–12 | No secrets in GitHub / frontend | No secrets exist; `.streamlit/secrets.toml` is git-ignored and absent | `test_source_never_reads_api_keys_or_contains_secrets` |
| 13 | No arbitrary Python execution | No `eval`/`exec`/`compile`/`__import__` calls | `test_source_has_no_dangerous_calls_or_imports` (AST) |
| 14 | No unsafe deserialisation | Fixtures are JSON only; no `pickle`/`marshal`/`yaml` | same AST test |
| 15 | No visitor-controlled shell | No `subprocess`/`os.system`; `shell.*` tools are not on the allowlist | AST test + `test_injected_non_allowlisted_action_is_denied` |
| 16 | No untrusted remote code | No HTTP clients; sockets are blocked in tests and every scenario still completes | `test_all_scenarios_run_with_network_and_llm_imports_blocked` |

## Input handling

* Every workflow parameter is validated against a per-scenario allowlist (`workflows/params.py`);
  unknown keys, unknown documents/topics/tasks, bad times and oversized text are rejected.
* Free text is NFKC-normalised, stripped of control characters and length-limited
  (`services/validation.py`). Memories, meeting titles and edited email bodies are also checked for
  sensitive data (email addresses, phone/card/ID numbers, credential words) and refused.
* Uploads (Document Wonderland) accept only UTF-8 `.txt`/`.md` up to 100 KB, are processed locally
  and are never written to disk.
* All dynamic values placed into custom HTML go through `html.escape` (`ui/components.e`).
  Interaction always uses native Streamlit widgets; no custom JavaScript is injected.

## Governance policies (Pearl 🛡️)

* `TOOL-001` the proposed tool must be on the allowlist, otherwise **deny** (the run ends at audit).
* `MAIL-001` simulated email recipients must be on the reserved `example.com` domain.
* `INPUT-001/002` argument size limit; no sensitive data in email bodies.
* `HITL-001` every consequential tool requires a human decision (LangGraph interrupt).

## Data retention

Session memory, runs, checkpoints, the audit log, simulated outbox/bookings and settings live in
process memory for the visitor's Streamlit session only. They disappear on refresh/session expiry or
server restart, and can be wiped from **Settings → Reset my demo session**.

## External requests

The only network request the page makes is the browser loading Google Fonts (DM Sans, Playfair
Display); system fonts are used if that fails. The Python process makes no outbound calls.

## Reporting

This is an educational demo. If you find a way to make it perform a real-world action or reach
another visitor's data, please open an issue in the repository.
