# Phase 1 — Dossier repository assessment

**Repository:** https://github.com/AienTech/dossier (cloned at `--depth 1`, version 1.11.0, inspected on 2026-11-01).

## What it is
A single-user, self-hosted job-search app: one password, one profile, tailored resume and cover letter per application, application board, optional daily job agent, MCP connector, Gmail/Calendar integration.

| Area | Finding (from the code, not the README) |
|---|---|
| Stack | Next.js 16 / React 19 / TypeScript, Prisma 7 with PostgreSQL, Playwright for PDF printing |
| Job discovery | JSearch, Adzuna and FreeHire search; YC and Hacker News "Who is hiring?" startup sources |
| Resume generation | Profile → tailored resume/cover letter with a "facts only, gaps shown" rule; twelve print themes |
| Database | ~30 Prisma models, all single-tenant (no user/tenant column on most tables) |
| Authentication | One hashed password from env + login throttle; no multi-user accounts |
| AI | Anthropic, OpenAI-compatible and Ollama clients |
| MCP | TypeScript MCP server (`@modelcontextprotocol/server`) with OAuth for Claude connectors |
| License | **AGPL-3.0-only** |

## Decision: clean implementation
Career_flo AI is a clean implementation. **No Dossier source code was copied.** The reasons:

1. **Tenancy.** Dossier's schema and auth assume one owner. Retrofitting per-user isolation, RLS, metering and billing would touch every model and query.
2. **Stack.** The brief requires FastAPI + LangGraph + the Python MCP SDK + React (Vite). Dossier is a Next.js monolith.
3. **Runtime AI policy.** Dossier integrates hosted LLM APIs (Anthropic, OpenAI). Career_flo must run Qwen open-weight models only.
4. **License.** Dossier is AGPL-3.0. Because no AGPL code is incorporated, AGPL source-offer and network-use obligations do not attach to Career_flo. If Dossier code is ever reused, Career_flo would have to be offered under AGPL-3.0 to network users, with Dossier's notices kept.

Ideas that informed the design (concepts, not code): drafts only use facts the user supplied and show gaps instead of inventing them; job providers are behind licensed aggregators; consequential actions are never sent automatically.

## Not done
Dossier's own test suite was **not run**. It needs Yarn 4, PostgreSQL 18 and Playwright browsers. Since no code was reused, its test results would not affect Career_flo.
