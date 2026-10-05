# I Built an AI Architecture Advisor Whose Most Important Feature Is Saying "Don't"

### Why the best enterprise AI recommendation is often "keep the rules engine," and how I encoded that judgment in code

---

Every few weeks, someone asks a version of the same question: *"Which LLM should we use for this?"* or *"Can we build an agent for that?"*

Those questions skip the one that matters most: **do we actually need AI for this business problem?**

I wanted a portfolio project that showed architectural judgment rather than prompt engineering. So I built **ArchAI**, an Enterprise AI Architecture Advisor. Its tagline is *"Modernize intelligently. Agentify selectively."* Its most valuable outputs are three sentences most AI demos never produce:

- **DO NOT USE AI**
- **AGENTIC AI NOT RECOMMENDED**
- **ROI DOES NOT JUSTIFY AI**

This article covers what it does, how it decides, and what I learned building it.

> *All companies, architectures and data in the project are fictional. The full source is on GitHub (link at the end).*

---

## The problem: we start from the wrong end

Many enterprise AI initiatives start at the technology and work backwards to the problem. An experienced architect reasons in the opposite direction:

```
Business problem → Current architecture → Data → Security / regulation
→ Operational constraints → AI suitability → Options → Risk → Cost → ROI
→ Target architecture → Migration roadmap
```

"Which model?" belongs near the end of that chain, if it shows up at all.

Here are the questions that tend to get skipped:

- **Is the workload deterministic?** If explicit rules already solve it, a rules engine is cheaper, faster and fully auditable.
- **Is it really a prediction problem?** Forecasting and classification usually call for classical ML, not an LLM.
- **Do answers need to be grounded in proprietary documents with citations?** That is when retrieval-augmented generation (RAG) earns its place.
- **Does the workflow actually vary across multiple systems?** If not, a workflow engine beats an agent.
- **What does the company already run?** Kubernetes, microservices, an API gateway and identity should be reused, not replaced.
- **What happens when the AI fails?**

ArchAI turns each of those questions into code.

---

## The core design decision: LLMs explain, they never decide

The most important architectural choice in ArchAI is that **the decision engine is plain, deterministic Python**. It uses explicit rules, weighted scoring and thresholds.

It computes eleven scores, each from 0 to 100:

- AI suitability
- ML suitability
- GenAI suitability
- RAG suitability
- Agentic AI readiness
- Infrastructure readiness
- Data readiness
- Security risk
- Operational risk
- Overall risk
- ROI / business value

Every score carries its factor breakdown and any gate or penalty that adjusted it. You can always see why a number is what it is.

An LLM can optionally rewrite the executive summary for a CIO audience. It never sets a score, a verdict, a cost or an autonomy level. If the LLM's text drops the decided architecture or verdict, ArchAI discards it and falls back to the deterministic template.

Why go to that length? Architecture decisions need to be **reproducible and auditable**. If you run the same assessment twice, you should get the same answer. That is a property an LLM-in-the-loop decision engine can't guarantee.

There is also a practical benefit. The public demo runs in **DEMO_MODE by default: zero LLM calls, no API key, $0 API cost**. That isn't just a promise in the documentation. The test suite runs every scenario with network sockets patched to fail and asserts that no paid model call ever happened.

---

## Why not every company needs agentic AI

Agents are the most hyped pattern right now, and also the easiest to over-apply. They add nondeterminism, hallucination risk, latency, operational complexity, governance burden and cost. ArchAI makes agents earn their place through an explicit **agentic need gate**.

The gate has four dimensions, each rated 0–5:

- multi-step reasoning
- workflow variability
- cross-system interaction
- tool requirements

At least three of the four must be rated 3 or higher before agents are even considered.

Even when a workload passes the gate, two hard rules still apply:

1. **Deterministic workloads get their agentic score multiplied by 0.4.**
2. **Deterministic-only actions cap agentic readiness at 20.** These are money movement, payment authorization, regulatory calculations, transaction validation, authentication, authorization and compliance rules. Those actions are always executed by existing, authoritative systems. AI may read or explain around them, but it never decides them.

### Scenario 1: "Replace our transaction rules with an autonomous agent"

A fictional bank, NorthStar Bank, runs its core platform on-premises:

- Kubernetes and microservices
- Oracle databases
- an API gateway

A business sponsor proposes replacing the deterministic transaction-threshold validation engine with an autonomous LLM agent.

ArchAI's answer:

> **KEEP EXISTING ARCHITECTURE — Keep Existing Transaction Rules Engine**
> **DO NOT USE AI**
> **AGENTIC AI NOT RECOMMENDED** — *No. This workload does not require agents.*

AI suitability scores 10 out of 100. The rules that fired are listed explicitly:

```
R-DET-01: deterministic, rules-governed workload → no AI component.
R-FORBID-01: deterministic-only actions (payment_authorization, transaction_validation)
             remain with existing deterministic systems.
R-REPL-01: request to replace 'Transaction Rules Engine' with AI rejected.
```

The rejection isn't dismissive. ArchAI also addresses the sponsor's real pain point, which is that rule changes are slow. It suggests rule versioning, golden test sets and a governed business-rule authoring UI. None of those require an LLM.

*[Image: docs/screenshots/01_banking_rules_not_recommended.png]*

### Scenario 2: same bank, different problem

Now the same bank, on the same platform, has a different use case. Operations engineers investigate production incidents by manually correlating logs, tickets, runbooks, dashboards and service APIs, and every investigation path is different.

This time the agentic gate passes clearly. The workflow is multi-step, variable, cross-system and tool-heavy. The answer changes:

> **Constrained Agents (LangGraph) around Existing APIs + RAG**
> **CONSTRAINED AGENTIC AI RECOMMENDED**
> **LEVEL 3: HUMAN APPROVAL REQUIRED**

The word that matters is **constrained**:

- The agent's tools are the bank's **existing APIs**, reached through the **existing API gateway**.
- Read-only investigation tools are enabled by default.
- Any remediation is *prepared* by the agent, *approved* by a named human, and *executed* by the existing system.
- Kubernetes stays. The microservices stay authoritative. Nothing gets replaced.

*[Image: docs/screenshots/02_incident_constrained_agentic.png]*

The contrast between these two scenarios is the whole point of the project. **Same company, same infrastructure, opposite answers, because the workloads are different.**

---

## AI should fit around the architecture you already have

A recurring failure mode in AI programs is the implicit rewrite: "the new AI platform" quietly becomes a parallel stack that duplicates identity, networking, observability and deployment.

ArchAI generates a **KEEP / ENHANCE / ADD / REPLACE** matrix with a few firm rules:

- Existing Kubernetes or OpenShift is **always KEEP**, and AI services deploy on it as ordinary workloads.
- Existing microservices are **KEEP and authoritative**. AI reaches them through their APIs, never directly through the databases of record.
- A vector store, a RAG service and a LangGraph orchestrator are only **ADDED** when the use case justifies them. Otherwise the matrix explicitly says **NOT ADDED**.
- **REPLACE** only appears for components the organization has *already* flagged as end-of-life, and even then the replacement is "a supported equivalent," not "AI."

ArchAI also draws the current-state and target-state architectures as Mermaid diagrams. In the target state, the AI capability layer sits *beside* the existing environment and connects to it only through the gateway and a human approval step.

*[Image: docs/screenshots/07_target_state_diagram.png]*

---

## "We have a vector database, so let's do RAG" is not a reason

One of my favourite test cases is a fictional retailer, MapleCart, that wants better store-level demand forecasting. It also happens to have a vector database left over from an earlier experiment.

ArchAI recommends **traditional machine learning** on the existing data warehouse. Forecasting is a prediction problem, and an interpretable classical model beats an LLM on cost and explainability. The existing vector database contributes **zero points** to the RAG score, and the scoring breakdown says so explicitly.

RAG does get recommended where it belongs. In another scenario, a fictional law firm needs lawyers to search thousands of case documents and prepare research summaries. The result is **Secure RAG + GenAI**, with:

- mandatory citations
- mandatory lawyer review of every output
- matter-level access control
- a model deployment strategy that refuses to default to a public API for privileged data

Even then, RAG has prerequisites. If document quality or the permissions model is weak, ArchAI defers RAG and recommends fixing the data first.

---

## When the business case says no

The ROI engine is deterministic too. It computes:

- current operating cost (manual effort, rework and existing technology)
- estimated benefit
- AI operating cost, taken from the cost engine
- implementation cost
- net annual benefit and payback period

**"ROI DOES NOT JUSTIFY AI" is a first-class outcome.**

In one scenario, a small fictional manufacturer's two-person HR team answers about 300 policy questions a month. A vendor pitched a custom GenAI chatbot. On need alone, a RAG chatbot *qualifies*. But the challenger step asks, *"Does the ROI justify the complexity?"* The answer is no, so the challenger sends the decision back to the engine with the AI patterns excluded.

The final recommendation: **keep the existing intranet FAQ.**

*[Image: docs/screenshots/06_cost_roi_not_justified.png]*

---

## How it's built

The assessment is orchestrated as a **LangGraph** workflow. LangGraph is a library for building workflows as graphs of steps. Every step in ArchAI's graph is deterministic Python:

```
Discovery → Current-State Architecture → Data Readiness → Use-Case Assessment
→ Decision Engine → {Traditional | ML | GenAI | RAG | Agentic} → Hybrid composition
→ Security & Governance → Resilience → Build-vs-Buy → Cost / ROI
→ Target Architecture → Challenger ─(FAIL, max 3 revisions)→ Decision Engine
→ Migration Roadmap → ADR → Final Report
```

A few details I'm proud of:

- **The challenger loop is bounded twice.** It uses the same iteration-budget guardrail ArchAI recommends for production agents (`AgentBudget`), plus LangGraph's own recursion limit. If an advisor tells you to cap your agents' iterations, it should cap its own.
- **Human-in-the-loop autonomy is capped by risk, never raised by it.** Levels run from 0 (no AI) to 5 (autonomous). Regulated industries, high-risk writes or high security risk all cap autonomy at level 3 (human approval). Level 5 is only reachable for low-risk, bounded, non-regulated workloads.
- **Resilience comes first.** The core principle is that *AI failure must not take down a deterministic business process.* Every recommendation includes a degradation chain that ends with *"existing system continues operating."*
- **Every assessment produces an Architecture Decision Record (ADR).** It covers alternatives considered, rejected options with reasons, security and cost implications, risks, the migration approach, evaluation criteria, and the conditions that would require reassessment.
- **FastAPI and Streamlit share one service layer**, so the API and the UI can never disagree.

There are 76 pytest tests. They cover every behaviour the design depends on, for example:

- Banking deterministic rules reject agents.
- Kubernetes is never replaced.
- RAG and agents are never recommended automatically.
- ROI can reject AI.
- Loops are bounded.
- Demo mode makes zero paid calls.
- No secrets are committed.

---

## What I learned

**1. Negative recommendations are harder to build than positive ones.** Recommending AI is easy, because you just pick the fanciest pattern. Saying "no" convincingly takes a reason, an alternative and a path forward. The deterministic rules engine didn't just get rejected. It came back with suggestions to fix the actual pain point.

**2. Explainability is a data-structure problem, not a prompt problem.** Every score carries its factors, gates and adjustments, and every decision lists the rules that fired. So the explanation *is* the computation, not a story told about it afterwards.

**3. The interesting work in agentic AI is constraint design.** Tool allow-lists, schema validation of tool parameters, approval gates, iteration and token budgets, and screening retrieved content for prompt injection decide whether an agent is safe to deploy. The model choice decides much less.

**4. Respect the existing architecture.** The most credible AI architecture in most enterprises is a thin, well-governed layer around systems that already work.

---

## Limitations, honestly

- ArchAI is only as good as its inputs. The 0–5 ratings come from people, not from automated discovery.
- The weights and thresholds are transparent, opinionated defaults. They are not calibrated against real-world outcome data.
- Model prices are illustrative sample values, and latency figures are indicative.
- It isn't legal or compliance advice. Regulatory considerations are prompts for your own risk teams.

---

## Try it

```bash
git clone https://github.com/florina787/Data-sets.git
cd Data-sets/archai-enterprise-advisor
pip install -r requirements.txt
streamlit run frontend/streamlit_app.py
```

You don't need an API key. Open `http://localhost:8501/?scenario=banking-transaction-rules` and watch it say no.

If you're working on enterprise AI, I'd love to hear where you think the decision rules are wrong. That debate is exactly the conversation this project is meant to start.

*Modernize intelligently. Agentify selectively.*

---

*Tags: Artificial Intelligence · Enterprise Architecture · Agentic AI · LangGraph · Software Architecture*
