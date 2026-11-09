<div align="center">

<img src="docs/assets/logo.svg" width="88" alt="Career_flo AI logo" />

# Career_flo AI

### Your Intelligent AI Career Partner

Fifteen specialised agents find real jobs, match them to **your verified resume**, tailor documents **without inventing facts**, and prepare you for interviews.
Everything runs on open-weight **Qwen** models.

<p>
<img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white">
<img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-15_agents-7357FF">
<img alt="MCP" src="https://img.shields.io/badge/MCP-7_servers-101828">
<img alt="Qwen" src="https://img.shields.io/badge/Qwen3-open--weight-38BDF8">
<img alt="React" src="https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=black">
<img alt="Supabase" src="https://img.shields.io/badge/Supabase-Postgres_+_RLS-3ECF8E?logo=supabase&logoColor=white">
<img alt="Stripe" src="https://img.shields.io/badge/Stripe-test_mode-635BFF?logo=stripe&logoColor=white">
<img alt="Tests" src="https://img.shields.io/badge/tests-95_passing-10B981">
</p>

<img src="docs/assets/screens/landing.png" alt="Career_flo AI landing page: an empty canvas with floating cards and AI agents shown as collaborative cursors" width="100%" />

</div>

---

## ✨ Why Career_flo

| 🧭 **Agents you can watch** | 🛡️ **Honest by construction** | 🎁 **Try everything, free** |
|---|---|---|
| A LangGraph supervisor routes your request to specialised agents. They appear as live cursors while they work. | Resumes and cover letters are fact-checked against your original resume. Anything unsupported is rejected. Salaries are shown only when the employer published them. | Every new account gets **2 free uses of all 16 premium features**, with no credit card. Trials never turn into a charge. |

<br/>

## 🎬 One request, the whole team

> *"Find Senior AI Engineer jobs in Toronto paying over CAD 150,000, analyze my resume, rank the best opportunities, and prepare me for interviews."*

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/assistant-results.png" alt="Assistant results: four Toronto jobs over CAD 150k with sources" /></td>
<td width="50%"><img src="docs/assets/screens/assistant-agents-working.png" alt="Agents working as cursors; resume analysis, interview plan and a streamed Qwen summary" /></td>
</tr>
<tr>
<td align="center"><sub><b>Job Discovery → Matching:</b> de-duplicated, salary-verified, every source shown</sub></td>
<td align="center"><sub><b>Resume + Interview agents</b> at work, then a grounded Qwen3-1.7B summary streamed at about 10–15 tok/s</sub></td>
</tr>
</table>

<details>
<summary><b>See the full conversation</b> (one long screenshot)</summary>
<br/>
<img src="docs/assets/screens/assistant-full.png" alt="Full assistant conversation" />
</details>

<br/>

## 🖼️ Feature tour

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/jobs.png" alt="Job discovery" /><br/><sub><b>Job Discovery</b>: category pills, verified salary filter, bookmark, posted-date strip and source attribution. Indeed and LinkedIn postings come only through the licensed aggregator.</sub></td>
<td width="50%"><img src="docs/assets/screens/resume-tailored.png" alt="Resume studio" /><br/><sub><b>Resume Studio</b>: your career progression, a tailored version with a Qwen-written summary that passed the fact check, and PDF/DOCX export.</sub></td>
</tr>
<tr>
<td><img src="docs/assets/screens/interview.png" alt="Interview intelligence" /><br/><sub><b>Interview Intelligence</b>: rubric scoring (coverage, depth, structure) plus written feedback from Qwen.</sub></td>
<td><img src="docs/assets/screens/learning.png" alt="Skills and learning" /><br/><sub><b>Skills & Learning</b>: four ways to grow (Ladder, Lattice, Wave, Portfolio), with real books and certifications matched to your skill gaps.</sub></td>
</tr>
<tr>
<td><img src="docs/assets/screens/analytics.png" alt="Career analytics" /><br/><sub><b>Career Analytics</b>: funnel, monthly timeline, match distribution, mock-interview progress and skill gaps.</sub></td>
<td><img src="docs/assets/screens/applications.png" alt="Application tracker" /><br/><sub><b>Application Tracker</b>: activity heatmap and board. Marking an application "submitted" requires your approval.</sub></td>
</tr>
<tr>
<td><img src="docs/assets/screens/mission-control.png" alt="Agent mission control" /><br/><sub><b>Agent Mission Control</b>: Qwen latency, tokens/s, MCP tool usage, CPU/RAM and every workflow run's step trace.</sub></td>
<td><img src="docs/assets/screens/mcp-registry.png" alt="MCP tool registry" /><br/><sub><b>MCP Tool Registry</b>: 7 versioned servers, per-agent allowlists and a redacted audit log of every call.</sub></td>
</tr>
<tr>
<td><img src="docs/assets/screens/governance.png" alt="Governance center" /><br/><sub><b>Governance Center</b>: approve or reject what agents propose, see the controls in force, read the audit log.</sub></td>
<td><img src="docs/assets/screens/pricing.png" alt="Pricing" /><br/><sub><b>Pricing</b>: Free, Pro (CAD 9.99) and Premium (CAD 19.99), with a monthly allowance table and clear renewal, refund and tax terms.</sub></td>
</tr>
<tr>
<td><img src="docs/assets/screens/dark-jobs.png" alt="Dark mode jobs" /><br/><sub><b>Dark mode</b>, everywhere.</sub></td>
<td><img src="docs/assets/screens/billing.png" alt="Billing" /><br/><sub><b>Billing</b>: plan status, per-feature free and monthly balances, payment history, Stripe portal.</sub></td>
</tr>
</table>

<details>
<summary><b>More screens</b>: empty-state assistant, career progression, dark learning, mobile</summary>
<br/>
<img src="docs/assets/screens/assistant-empty.png" alt="Assistant empty state" width="49%" />
<img src="docs/assets/screens/resume-progression.png" alt="Career progression" width="49%" />
<img src="docs/assets/screens/dark-learning.png" alt="Dark mode learning" width="49%" />
<img src="docs/assets/screens/mobile-landing.png" alt="Mobile landing" width="24%" />
</details>

<br/>

## 🎨 Design language

The direction is **near-empty screens, floating cards, and AI agents shown as collaborative cursors**. Career growth is drawn as a **ladder, a lattice, a wave and a portfolio**. All illustrations are original SVG drawn in code; no third-party artwork or stock photography is used. Details: [docs/DESIGN.md](docs/DESIGN.md).

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/hero-cards.png" alt="Floating cards with agent cursors" /></td>
<td width="50%"><img src="docs/assets/screens/growth-paths.png" alt="Ladder, Lattice, Wave and Portfolio illustrations" /></td>
</tr>
</table>

<br/>

## 🏗️ Architecture

```mermaid
flowchart LR
    U([User]) -->|HTTPS · SSE| FE[React + TypeScript<br/>Tailwind · Recharts · Framer Motion]
    FE -->|Supabase JWT| API[FastAPI]
    FE <-->|sign-up · verify · reset| SA[(Supabase Auth)]
    API --> MET{{Metering<br/>reserve → run → commit}}
    MET --> SUP[LangGraph Supervisor]
    SUP --> AG[14 specialised agents]
    AG --> GOV[Governance node]
    AG --> GW[MCP Gateway<br/>allowlists · identity injection<br/>rate limits · timeouts · audit]
    GW --> M1[Jobs] & M2[Resume] & M3[Applications] & M4[Portfolio] & M5[Company] & M6[Analytics] & M7[Governance]
    API --> Q[Qwen3 via Ollama / llama.cpp]
    API --> DB[(Supabase Postgres<br/>41 tables · RLS)]
    M1 --> P[JSearch · Adzuna · Greenhouse · Lever · Ashby]
    API <-->|Checkout · Portal · Webhooks| ST[Stripe]
```

<details>
<summary><b>How one paid action is metered</b> (sequence diagram)</summary>

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant M as Metering
    participant F as Feature (agents + MCP)
    C->>A: POST /api/resumes/tailor (Idempotency-Key)
    A->>M: reserve(user, feature, key)
    Note over M: UPDATE … WHERE used + reserved < limit<br/>+ unique reservation row
    alt allowance available
        M-->>A: reservation
        A->>F: run (nested features are included, not charged)
        alt success
            F-->>A: result
            A->>M: commit → used += 1, result cached for replays
            A-->>C: 200 + _usage (1 of 2 free uses remaining)
        else failure
            A->>M: release → nothing consumed
            A-->>C: error
        end
    else exhausted
        M-->>A: FeatureExhausted
        A-->>C: 402 "You've completed your two free trials… Upgrade to continue."
    end
```
</details>

<br/>

## 🎁 Two free uses of every feature

<img src="docs/assets/charts/trials.svg" alt="Sixteen premium features, each with two free uses" width="100%" />

- **Server-side:** the counters live on the server. Logging out or changing email never resets them.
- **Safe under load:** 12 parallel requests still get exactly 2 uses (tested on PostgreSQL).
- **No double charges:** a retry with the same `Idempotency-Key` replays the stored result and isn't charged again.
- **Fair:** a failed run never consumes a use, and a Free plan never auto-charges.
- **Paid plans unlock only from Stripe webhooks.** A checkout success redirect alone never grants access.

<br/>

## 🧠 Qwen on a plain CPU (measured)

<table>
<tr>
<td width="50%"><img src="docs/assets/charts/qwen-speed.svg" alt="Tokens per second by model" /></td>
<td width="50%"><img src="docs/assets/charts/qwen-ttft.svg" alt="Time to first token by model" /></td>
</tr>
<tr>
<td colspan="2"><img src="docs/assets/charts/qwen-accuracy.svg" alt="Task accuracy by model" /></td>
</tr>
</table>

**Default model: Qwen3-1.7B.** It is the smallest model that scored perfectly on structured output (4/4) and tool selection (8/8), at about 15 tok/s on 4 vCPUs. Routing, scoring and every safety control are deterministic code, so the model is never the security boundary. Method and caveats: [docs/BENCHMARK.md](docs/BENCHMARK.md).

<br/>

## ✅ Tested

<img src="docs/assets/charts/tests.svg" alt="45 backend tests on SQLite, 45 on PostgreSQL, 5 frontend tests" width="100%" />

The suite covers all six acceptance scenarios (job discovery, resume optimisation, mock interview, trial exhaustion, Stripe subscription, multi-user isolation). It also checks MCP discovery and allowlists, LangGraph workflows, SSE chat, Stripe webhook signature/replay/out-of-order handling, cross-user access, counter tampering, concurrent trials, malicious uploads, prompt injection and the coding sandbox.

<br/>

## 🚀 Run it locally

```bash
# Backend (Python 3.11+, uv) with Qwen through Ollama
cd backend && uv sync
uv run python -c "from app.main import init_db; init_db(); from app.db import SessionLocal; from app.seed import seed_demo; seed_demo(SessionLocal())"
ollama pull qwen3:1.7b
LLM_PROVIDER=ollama LLM_MODEL=qwen3:1.7b uv run uvicorn app.main:app --port 8000
```

```bash
# Frontend (Node 22): http://localhost:5173
cd frontend && npm install && npm run dev
```

Demo login: `demo@careerflo.example` / `DemoPassword123`. All demo data is synthetic and labelled.

```bash
# Tests
cd backend && uv run pytest
cd frontend && npm run typecheck && npm test && npm run build
```

Production (Supabase, Stripe, Ollama on one VM, Docker Compose): see the [deployment guide](docs/DEPLOYMENT.md).

<br/>

## 🗂️ Project map

| Area | Where |
|---|---|
| Feature registry, plans, trial limit | [`backend/app/features.py`](backend/app/features.py) |
| Metering: reserve / commit / release / idempotency | [`backend/app/billing/metering.py`](backend/app/billing/metering.py) |
| Stripe Checkout, Portal, webhooks | [`backend/app/billing/stripe_service.py`](backend/app/billing/stripe_service.py) |
| LangGraph supervisor and agents | [`backend/app/agents/`](backend/app/agents/) |
| MCP servers A–G and gateway | [`backend/app/mcp_servers/`](backend/app/mcp_servers/) · [`backend/app/mcp_gateway.py`](backend/app/mcp_gateway.py) |
| Qwen client and benchmark | [`backend/app/llm/qwen.py`](backend/app/llm/qwen.py) · [`backend/scripts/benchmark_qwen.py`](backend/scripts/benchmark_qwen.py) |
| Jobs, resume, ATS, interview, coding, salary, company, portfolio | [`backend/app/jobs/`](backend/app/jobs/) · [`backend/app/careers/`](backend/app/careers/) |
| Schema and row-level-security migrations | [`backend/migrations/versions/`](backend/migrations/versions/) |
| Frontend (22 sections, Skills & Learning, pricing, admin) | [`frontend/src/`](frontend/src/) |
| README visuals (regenerate) | [`scripts/readme_charts.py`](scripts/readme_charts.py) · [`scripts/readme_screenshots.cjs`](scripts/readme_screenshots.cjs) |

**Docs:** [Architecture](docs/ARCHITECTURE.md) · [MCP](docs/MCP.md) · [API (96 endpoints)](docs/API.md) · [Security](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Benchmark](docs/BENCHMARK.md) · [Limitations & costs](docs/LIMITATIONS_AND_COSTS.md) · [Design](docs/DESIGN.md) · [Dossier assessment](docs/DOSSIER_ASSESSMENT.md)

<br/>

## 📍 Status

Built and tested locally. **Not deployed yet.**
- Stripe is wired for **test mode**: live keys are refused unless `STRIPE_ALLOW_LIVE=true`.
- Live job search needs JSearch or Adzuna keys. Until they are set, the app uses clearly labelled synthetic jobs.
- See [Limitations & costs](docs/LIMITATIONS_AND_COSTS.md) for what is not yet verified end-to-end.

<br/>

## 💜 Thank you, Dossier

<table>
<tr>
<td>

**Career_flo AI owes a real debt of gratitude to [Dossier](https://github.com/AienTech/dossier) by [AienTech](https://github.com/AienTech).**

Dossier is a thoughtful, self-hosted job-search companion. Studying it shaped several of Career_flo's core principles:
- **"Never invent experience":** drafts use only facts from your profile, and whatever a posting asks for that you lack is shown as a *gap*, never made up.
- **Licensed job sources:** JSearch and Adzuna rather than scraping.
- **Nothing sent without you:** the agent prepares work, and you decide.
- **MCP as a first-class integration surface.**

Career_flo is a clean, multi-tenant Python implementation, and no Dossier source code is included. Dossier is licensed **AGPL-3.0**; if you build on Dossier itself, please honour that license. Our full assessment is in [docs/DOSSIER_ASSESSMENT.md](docs/DOSSIER_ASSESSMENT.md).

If you want a single-user, self-hosted job-search tool, go give Dossier a ⭐.

</td>
</tr>
</table>

### Also standing on the shoulders of

[Qwen](https://github.com/QwenLM/Qwen3) · [Ollama](https://github.com/ollama/ollama) · [llama.cpp](https://github.com/ggml-org/llama.cpp) · [LangGraph](https://github.com/langchain-ai/langgraph) · [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk) · [FastAPI](https://github.com/fastapi/fastapi) · [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) · [Supabase](https://github.com/supabase/supabase) · [Stripe](https://stripe.com) · [React](https://github.com/facebook/react) · [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) · [TanStack Query](https://github.com/TanStack/query) · [Recharts](https://github.com/recharts/recharts) · [Framer Motion](https://github.com/framer/motion) · [Lucide](https://github.com/lucide-icons/lucide)

Job data comes from the providers' own APIs: [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch), [Adzuna](https://developer.adzuna.com), [Greenhouse](https://developers.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api) and [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api). Company overviews come from [Wikipedia](https://www.wikipedia.org).

<div align="center">
<br/>
<sub>Made with care for everyone climbing, moving sideways, riding the wave, or building their portfolio.</sub>
</div>
