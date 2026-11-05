# The LLM Should Never Be Your Calculator: Building a Governed Agentic AI Platform for Wealth Management

### What I learned building FLO — 20 agents, deny-by-default security, and a test suite that kept proving me wrong

![FLO Executive Command Center](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/01-executive.png)

Every asset manager I talk to asks some version of the same question about generative AI: *"Can we let it near our numbers and our clients?"*

It's a fair worry. In wealth management a wrong figure is a reportable error, and leaked client data is a regulatory incident. A friendly chatbot that "hallucinates a little" is a liability, not a productivity gain.

So I set out to answer the question with working software rather than slides. The result is **FLO — Financial Leadership, Operations & Wealth Intelligence**: an open-source, end-to-end agentic AI platform for a fictional Canadian investment and wealth management firm. It includes:

* an executive command center
* investment and wealth-advisor workspaces
* a scenario simulator
* regulatory research tools
* an AI-operations console
* "Ask Flo", a copilot backed by **20 specialist agents** orchestrated with LangGraph

> **Disclaimer:** FLO is an independent architecture demonstration. It isn't affiliated with any firm, and every record is synthetic: clients, portfolios, funds and documents. All integrations are mock adapters. By default it makes **zero external LLM calls**, and securities trading is prohibited by policy.

This article covers the design principles that mattered, the architecture, and the part I find most valuable: **the bugs my own verification suite caught**, which I would have shipped otherwise.

---

## Principle 1: The LLM is never the calculator

The most important decision in FLO is also the simplest. **Every financial figure is computed by deterministic Python, never by a language model.**

Money is stored as integer cents and computed with `Decimal`. It is rounded once, half-to-even, at the end of a calculation. Every metric has one governed definition in a *semantic layer*, and every chart and agent references those definitions by id. Examples:

* AUM roll-forward
* net flows
* revenue yield
* time- and money-weighted returns
* Sharpe ratio
* drawdown
* concentration (HHI)
* allocation drift

Agents call these services as tools. The model's only job is to *phrase* the result. Then the harness enforces a rule I now consider essential:

> **Numeric grounding:** if a narrative contains any number that does not appear in the tool outputs, the answer is rejected.

That check sounds paranoid. It caught real defects four times during development, all of them in my own templates. Once it was a "12-month" label with no "12" in the facts. Another time it was a "p95" in a narrative. If a deterministic template can slip an ungrounded number past you, a real LLM certainly will.

## Principle 2: Make the data tell a story you have to *explain*

Demo data is usually random noise, so demos end up scripted. I wanted the headline executive question — *"Why did AUM increase while profitability declined?"* — to be answerable from the data alone.

So the synthetic generator (fixed seed, enforced referential integrity) encodes a realistic business story:

* markets rise, with a drawdown in spring 2025
* client money rotates from high-fee mutual funds into low-fee ETFs and an institutional mandate
* a 15 bp fee cut lands in November 2025
* technology spending steps up mid-year

![AUM up while revenue yield and operating margin fall](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/images/story-aum-yield-margin.png)

When the CEO asks the question, three agents run **in parallel**, each calling governed analytics tools:

* The **AUM agent** reports total AUM of CAD 50.81bn, up 3.08% over 12 months. ETFs led net flows and mutual funds saw redemptions. The roll-forward reconciles to the cent.
* The **financial-performance agent** reports that operating margin fell from 30.69% to 27.85%: expenses grew 9.19% while revenue grew 4.89%, led by technology.
* The **revenue agent** splits the revenue change exactly into volume, product-mix and fee-change effects. The mix shift toward low-fee vehicles cost CAD 36.9m and the fee cut CAD 3.3m.

![Revenue attribution waterfall](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/images/revenue-attribution.png)

That is a *real* answer: specific, decomposed, reconciled and traceable. Every chart in the product carries a lineage panel showing which metric definitions, mock source systems and dataset version produced it.

![Ask Flo answering the CEO question with a governance trace](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/02-ask-flo.png)

## Principle 3: Security decisions never live in a prompt

"You are a helpful assistant. Never reveal client data." That is not a control. FLO enforces access in trusted backend code, through four layers.

**1. A deny-by-default policy engine.** RBAC and ABAC rules are written as versioned YAML (policy-as-code). They cover:

* advisors see only their assigned clients
* external dealer advisors never see private-wealth records
* documents above your clearance are invisible
* model providers must run in an approved Canadian region for the data classification involved

Every decision carries the policy version and a content hash. The same rules are mirrored in **Open Policy Agent (Rego)**, and a parity test runs roughly 2,000 decisions through both engines. That test found a genuine divergence on its first run.

**2. A tool gateway.** It is the *only* path from an agent to data or side effects. On every call it checks, in order:

1. Is the tool known?
2. Is the action prohibited?
3. Is the tool on this agent's allowlist?
4. Do the arguments pass strict schema validation?
5. Does policy allow it for the *human* principal and this specific resource?
6. Is it approval-gated?
7. Is it within its rate limit?

**3. An append-only, hash-chained audit log**, kept in its own store, with PII redacted before anything is written.

**4. Prohibited actions** — trading, shell access, raw database queries — are denied for every role, even with approvals.

To test this honestly I wrote a **compromised model**. It's a scripted test double whose "plan" asks to export all client data, e-mail it externally and place a trade. The gateway blocked every one of those calls and audited each denial, and the agent still produced its legitimate answer. That is the property you want: **security that holds even when the model is wrong or manipulated.**

![Prompt injection flagged; no tool bypass](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/14-prompt-injection.png)

Prompt-injection detection exists too: it flags inputs, and documents containing high-severity injections are quarantined at ingestion. But it's treated as defence in depth, not as the control.

## Principle 4: Humans approve the *exact* payload

Consequential actions wait for a human. These are client communications, personalized recommendations, sensitive exports, board-report distribution, financial-record changes and portfolio modifications.

FLO implements this as a LangGraph workflow with a durable `interrupt()` and checkpointing:

1. An advisor asks for a portfolio-review letter. It is drafted **only from compliance-approved templates** in English, French, Spanish, Hindi, Tamil or Korean, filled with figures from deterministic tools.
2. A translation validator checks that every number, date and preserved term (FLO, ETF, RRSP…) survives translation.
3. The workflow pauses. A compliance officer reviews the *exact* payload and approves its **SHA-256 hash**.
4. On resume, the requester's authorization is checked again. If even one character of the payload has changed, the approval is **invalidated**.

The workflow also blocks self-approval, enforces expiry, and rejects replays because each approval executes at most once.

![Approval queue showing the exact payload and its hash](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/07-approvals.png)

## Principle 5: Privacy by construction

A privacy service detects names, e-mails, phone numbers, Canadian SINs (Luhn-validated), account numbers, dates of birth, addresses, secrets and amounts linked to identified people. It then:

* **masks** values for display
* **tokenizes** text for model context, e.g. *"Client [CLIENT_001] has account [ACCOUNT_001]"*
* keeps mappings in an **encrypted, access-controlled vault** that never reaches the browser or the model

Rehydrating a token back into a real value needs a policy decision about the underlying client and is audited. Mappings expire, and subject erasure overwrites ciphertext before deleting it.

One subtle lesson came from here. My synthetic directory, like real life, contains different clients who share a name. The first version linked a detected name to whichever client came last in a dictionary. That meant an advisor could have been shown a *different* client's identity. The fix: **ambiguous names are never linked to a client**, so only a privacy officer with a recorded purpose can rehydrate them.

## The architecture

![A live wealth-advisor workflow traced in the AI Operations console: supervisors → agents → tool calls](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/08b-agent-workflow-graph.png)

* **Experience:** React, TypeScript, Vite, Tailwind, ECharts, Recharts, MapLibre and TanStack. There are 13 role-aware workspaces. Each chart has a table view, PNG/CSV export, lineage and an "Explain with Flo" button.
* **API:** FastAPI with Pydantic v2, load shedding and security headers.
* **Orchestration:** LangGraph runs an enterprise supervisor, five domain supervisors and 20 specialists. Independent tasks fan out in parallel with `Send()`. The graph is a DAG with no agent-to-agent loops.
* **Agent harness:** role admission, budgets (iterations, tokens, cost, time), retries with backoff, circuit breakers, an idempotency cache, cancellation, output validation and telemetry.
* **Knowledge:** a permission-aware hybrid RAG pipeline. Uploads pass malware and file checks before parsing (PDF, DOCX, XLSX, CSV, Markdown). Retrieval combines BM25 with pgvector, applies an **authorization filter *before* scoring** so ranking scores can't leak documents you shouldn't see, and returns citations.
* **Data:** PostgreSQL with pgvector, plus Redis and Alembic migrations.
* **Ops:** Docker Compose with an OPA sidecar, Prometheus and Grafana, Kubernetes manifests, a Helm chart and provider-neutral Terraform modules.

![Investment workspace — portfolio analytics](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/03-portfolio-detail.png)

![Wealth Advisor 360](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/screenshots/05-client-360.png)

## The best part: what verification caught

I built FLO in vertical slices: implement, test, fix, document, repeat. The rule was to report measured results, never estimated ones. Here's an honest list of real defects the tests, evaluations, load tests and deployment checks surfaced:

1. **Policy-engine divergence.** The Python engine attached "approval required" obligations to *denied* decisions; Rego didn't. The parity test caught it.
2. **Audit deadlock.** Writing audit events in a separate transaction deadlocked SQLite while a business transaction held the lock. The fix gives the audit log its own store, which is also the better production design.
3. **Missed names.** The name detector's regex consumed "Review Amélie" and never saw "Amélie Park". Overlapping matches fixed it.
4. **A LangGraph gotcha.** Resuming an interrupted graph with an empty dict (`Command(resume={})`) is silently ignored. The approval workflow simply never resumed until I sent a non-empty value.
5. **Role and classification mismatches.** The AI administrator couldn't read redacted operational traces. The privacy officer was an approver but lacked permission to decide. External advisors couldn't use the product-research *agent* even though the REST endpoint worked.
6. **PostgreSQL vs SQLite.** A `VARCHAR(24)` column overflowed on PostgreSQL. SQLite silently ignores lengths, so the whole suite now runs on both.
7. **A translation false positive.** The number extractor captured "30," (with the comma) from a date, which blocked valid Hindi letters. It failed safe, but it was still wrong.
8. **Connection-pool exhaustion under load.** The first 500-user test produced HTTP 500s and 60-second timeouts. Admission control is now sized to the pool, and saturation returns `503 Retry-After` instead of crashing.
9. **An RBAC gap** — the CIO couldn't open fund research — found by the load test, of all things.
10. **Stale DNS in nginx.** After the API container was recreated, the UI returned 502s because nginx had cached the old IP.

None of these would have appeared in a slide deck. Most would have appeared in production.

![Verification summary](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/images/verification.png)

The final state:

* **128** backend tests passing on SQLite and on PostgreSQL + Redis. They cover financial correctness with hand-computed expectations, security and adversarial cases, and all eight required end-to-end journeys.
* **6/6** Playwright browser journeys and **10/10** evaluation cases.
* A **release gate** that blocks any release on a failing critical security or financial test, plus static analysis, dependency audit and secret scanning.
* A backup/restore drill that found the audit hash chain valid on the restored copy.

## Honest numbers: performance

Here's a chart I'm glad I didn't fabricate.

![Measured load tests](https://raw.githubusercontent.com/florina787/Data-sets/claude/zen-goldberg-t5e2x7/flo-enterprise/docs/images/load-tests.png)

On a single 4-vCPU container, which was also running the load generator:

* **At 50 users**, every request succeeded. Dashboard p95 was 50 ms and the agent workflow p95 was 195 ms with the in-process model.
* **The host saturates at about 55–60 requests per second.** At 500 or more virtual users, the latency targets are *not met* on one machine.

What I did achieve is graceful degradation: overload becomes fast `503`s with `Retry-After`, with no 500s and no crashes. Meeting the targets at that scale needs horizontal scaling, which I haven't measured, so I don't claim it.

## Limitations (because they matter)

* **The default "model" is deterministic templating.** The answers are accurate and grounded, but formulaic. There is a Bedrock adapter with residency enforcement and grounding fallback, but it hasn't been exercised against a real model.
* **Synthetic data and mock adapters only.** Nothing connects to a production system.
* **A mock identity provider stands in for the login.** Some resilience state is per-process. Regulatory references are illustrative, and the AI makes no legal or regulatory determinations.

## Takeaways for anyone building AI in financial services

1. **Separate calculation from narration**, and enforce it mechanically with numeric grounding.
2. **Put authorization in a gateway, not a prompt.** Test it with a deliberately compromised model.
3. **Bind human approvals to exact payloads**, and re-authorize at execution.
4. **Make your synthetic data tell a story**, so demos prove reasoning rather than scripts.
5. **Run everything on the database you'll deploy on.** SQLite will lie to you.
6. **Measure, then publish the measurements — including the unflattering ones.** Verification is where the real engineering happens.

The full source — code, tests, policies, infrastructure and documentation — is on GitHub. I'd love feedback, especially from people running AI governance in regulated industries.

👉 **Repository:** [github.com/florina787/Data-sets](https://github.com/florina787/Data-sets/tree/claude/zen-goldberg-t5e2x7/flo-enterprise)

---

*Tags: Artificial Intelligence · LangGraph · FinTech · AI Governance · Wealth Management*
