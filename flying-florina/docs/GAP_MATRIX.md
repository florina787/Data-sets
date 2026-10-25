# Gap matrix: what is real, simulated, optional, or not built

| Capability | Status | Notes |
|---|---|---|
| Synthetic dataset, KPIs, charts | **Working** | Single source of truth in SQLite; cross-screen consistency tested |
| Intent routing | **Working (rules)** | Regex/weighted patterns; not an LLM. Unusual phrasings fall back to a clarification prompt |
| Multi-agent workflows | **Working** | Explicit DAG engine; LangGraph not used |
| Diagnostics | **Working, limited** | Qualitative hypothesis ranking from synthetic evidence. Not a diagnosis, not predictive maintenance, no accuracy claims |
| Retrieval | **Working** | FTS5/BM25 + TF-IDF fallback. No embeddings/FAISS (optional, not installed) |
| Prompt-injection defense | **Working, pattern-based** | Catches the seeded patterns; not exhaustive. The real control is POL-011 (retrieved text can never trigger actions) |
| Policy engine | **Working** | 13 policies, deterministic, tested. No OPA |
| Approvals and writes | **Working, simulated target** | Approved writes go into the demo DB only; no external system is changed |
| Audit chain | **Working, tamper-evident** | Not tamper-proof against a host admin (no external anchoring) |
| Identity | **Demo only** | Persona login without passwords, HMAC tokens. Production needs an IdP + MFA |
| Legacy X-Ray | **Working** | Regex SQL parser covers common DDL; complex dialect features (partitions, PL/SQL) are ignored. Java analysis is regex metadata only; other languages listed as unsupported |
| Bridge generator | **Working** | One capability (`get_part_availability`) from vetted templates; backend is a synthetic snapshot |
| MCP | **Working locally** | Official SDK 2.3 over stdio; no remote MCP transports exposed |
| IFS Cloud / ERP integration | **Not connected** | Fixtures are fictional "IFS-like" projections. No undocumented endpoints are assumed |
| Simulation / ROI | **Working** | Deterministic, seeded; all money values are editable assumptions |
| Reports | **Working** | ReportLab PDF; no charts embedded in PDFs |
| Offline mode | **Working** | Process egress guard + test; host firewall still recommended |
| Optional local LLM | **Detection only** | `LLM_ENABLED` + loopback check (POL-008); no generation step is wired into answers |
| PostgreSQL, Alembic | **Not built** | SQLite only, idempotent DDL |
| SSE streaming | **Implemented, unused by UI** | `/api/workflows/{id}/stream`; UI uses polling |
| 3D visualization, plugin gallery | **Not built** | P2 |
| Docker images | **Files provided, not built in CI** | Compose for local use |
| Brand portrait | **Not available** | Placeholder mark; drop-in path documented |
| Accessibility | **Partial** | Labels, keyboard focus, skip link, chart data tables; no formal WCAG audit performed |
