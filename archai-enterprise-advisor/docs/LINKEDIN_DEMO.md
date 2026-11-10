# ArchAI — LinkedIn Demo Script (45–60 seconds)

**Main message:**
> *"I built an AI architecture advisor that can tell an enterprise when NOT to use Agentic AI."*

The demo should show **architectural judgment**, not LLM generation. Everything on screen comes from the deterministic engine in DEMO mode: **$0 API cost and no API key**. All companies and data are fictional.

---

## Setup (before recording)

```bash
cd archai-enterprise-advisor
pip install -r requirements.txt
streamlit run frontend/streamlit_app.py
```

- Open `http://localhost:8501/?scenario=banking-transaction-rules`.
- Use a 1440×900 or larger browser window, with zoom at 90% so the dashboard cards and verdict boxes fit on one screen.
- Point out the green **DEMO MODE · $0 API cost** badge once.

## Shot list and voice-over

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:05 | Header: **ArchAI — "Modernize intelligently. Agentify selectively."** | "Everyone's asking which LLM or agent framework to use. The better first question is: do we need AI at all?" |
| 0:05–0:10 | **Step 1–2.** Tab *2 · Industry*: **Banking**. Tab *3 · Current Architecture*: **On-Prem, Kubernetes, Microservices, Oracle, API Gateway** | "Here's a fictional bank: on-prem Kubernetes, microservices, Oracle, an API gateway." |
| 0:10–0:14 | **Step 3.** Tab *6 · Business Use Case*: *Replace transaction threshold validation rules with an autonomous LLM agent* | "The sponsor wants to replace deterministic transaction validation with an autonomous agent." |
| 0:14–0:22 | **Step 4–5.** Dashboard: red **AGENTIC AI NOT RECOMMENDED** and **KEEP EXISTING — Transaction Rules Engine · DO NOT USE AI**. Briefly show tab *8*, where the matrix row reads *Transaction Rules Engine → KEEP* | "ArchAI says no. The workload is deterministic, transaction-critical and auditable. An agent would add nondeterminism, hallucination risk, latency and cost. Keep the rules engine." |
| 0:22–0:27 | **Step 6.** Sidebar → *Switch use case* → **Cross-system incident investigation** → *Apply use case* | "Same bank, same platform. Now the use case is engineers investigating incidents across logs, tickets, runbooks and service APIs." |
| 0:27–0:33 | **Step 7.** Dashboard: amber **CONSTRAINED AGENTIC AI RECOMMENDED** and **Constrained Agents (LangGraph) around Existing APIs + RAG** | "Now agents are justified, but only constrained ones. The workflow is variable, multi-step and cross-system." |
| 0:33–0:40 | **Step 8–10.** Tab *8*: matrix rows *Kubernetes KEEP · Microservices KEEP · LangGraph AI Orchestrator ADD*, then the target diagram with **Human Approval** | "Nothing gets replaced. The existing microservices stay authoritative. LangGraph is added around the existing APIs, and every remediation needs human approval." |
| 0:40–0:45 | **Step 11.** Tab *9*: autonomy **Level 3 — Human approval required**, per-action policy, guardrails (max iterations, tool allow-list) | "The security controls are concrete: tool allow-lists, iteration limits, permission-aware retrieval and audit." |
| 0:45–0:50 | **Step 12.** Tab *10*: cost per month, **ROI JUSTIFIES AI**, payback. Move one What-If slider | "Cost and ROI are calculated deterministically, and 'ROI does not justify AI' is a valid answer too." |
| 0:50–0:55 | **Step 13.** Tab *11*: Phases 0→5, autonomy ceilings | "There's a phased roadmap. Unrestricted autonomy is never on day one." |
| 0:55–0:60 | **Step 14.** Tab *12*: ADR, then click **Export ADR (Markdown)** | "Every assessment produces an Architecture Decision Record. Modernize intelligently, agentify selectively." |

## Suggested post text

> I built **ArchAI**, an Enterprise AI Architecture Advisor whose most important feature is saying **"don't."**
>
> 🏦 A bank wants to replace deterministic transaction validation with an autonomous LLM agent → **AGENTIC AI NOT RECOMMENDED. Keep the rules engine.**
> 🛠️ The same bank wants faster cross-system incident investigation → **Constrained agents around existing APIs, with human approval for every remediation.**
>
> How it works:
> • A deterministic decision engine with explicit rules, weights and thresholds. The LLM never decides.
> • Kubernetes and microservices are kept, and AI fits around existing APIs.
> • Security, resilience, build-vs-buy, cost/ROI, a phased roadmap and an ADR for every assessment.
> • LangGraph workflow, FastAPI and Streamlit. The public demo runs with **$0 API cost and no API key**.
>
> All companies and data are fictional. Code: <repo link>
>
> #EnterpriseArchitecture #AIArchitecture #AgenticAI #LangGraph #GenAI

## Backup talking points (for comments)

- **"Isn't this just rules?"** Yes, deliberately. Architecture decisions have to be reproducible and auditable. LLMs can narrate the decision in live mode, but they can't change it.
- **"When does it recommend agents?"** Only when at least 3 of 4 dimensions are rated ≥3: multi-step reasoning, workflow variability, cross-system interaction and tool use. Even then, regulated or write-capable workloads are constrained to human approval.
- **"What about RAG?"** A vector database being present scores zero. RAG needs proprietary-knowledge and citation needs plus data-readiness prerequisites.
