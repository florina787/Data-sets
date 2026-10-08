# I Built an Agentic AI Copilot for Health-Insurance Software — and the Most Important Design Decision Was Where *Not* to Use AI

*How ClaimForge Copilot takes a business requirement all the way to production claims intelligence, with LangGraph agents, deterministic rules engines, statistics and humans each doing the job they're best at.*

---

> **Disclaimer:** Everything in this project is synthetic. "NorthStar Health Benefits" is a fictional insurer. Every member, claim, policy and incident is generated. This is an engineering demonstration. It is not insurance advice, and it is not a real adjudication system.

---

## The one-sentence change that touches everything

Imagine a product manager at a health insurer writes this:

> *"Increase physiotherapy annual coverage from $750 to $1,000 and require prior authorization after 10 completed visits."*

It reads like a small change, but it touches a lot:

- **Policy wording.** Two policy sections have to be amended, and a 30-day member notice is required.
- **Three microservices:** Claims, Benefits and Authorization.
- **Two APIs, rule tables, an event schema,** regression tests, monitoring dashboards, member communications and analytics.
- **Money.** Every physiotherapy claim from now on pays differently.

It also contains a trap. Does "after 10 visits" mean authorization starts *on* visit 10, or from visit 11? In my experience the costliest defects come from requirements that reach a developer while still ambiguous, and they are rarely hard algorithms.

I wanted to see what an AI copilot for this lifecycle would look like if it were designed responsibly. The result is **ClaimForge Copilot**, with a production-intelligence module called **ClaimIQ**.

![Copilot asking for human clarification](screenshots/copilot_clarification.png)

---

## The core principle: don't use an LLM for everything

Most agentic-AI demos send everything through an LLM. In health insurance that is a liability. You never want to ask a language model whether someone's claim should be approved.

So ClaimForge splits the work by responsibility:

| Job | Who does it |
|---|---|
| Reasoning, orchestration, investigation, explanation | **Agents** (LangGraph) |
| Finding policy evidence, with citations | **RAG** (local BM25 retrieval) |
| Eligibility, coverage, limits, reimbursement, prior auth | **Deterministic Python rules engine** |
| Deciding "is this number anomalous?" | **Statistics** (relative change + z-score) |
| Approving releases, fixes and claim reprocessing | **Humans** |

The adjudication engine is a single pure function with versioned, immutable rulesets. The same function runs the single-claim API, the 10,000-claim simulator, simulated production and the generated tests. Every decision carries a reason code and a rule ID:

```json
{"status": "DENIED", "reason_code": "AUTH_REQUIRED", "rule_id": "AUTH_RULE_184",
 "counted_visits": 10, "engine": "DETERMINISTIC RULES ENGINE (no LLM)"}
```

The whole demo runs in **demo mode by default: no API key, zero LLM calls, $0**. If you add an Anthropic key, the LLM can only rephrase explanations. It never touches a decision.

---

## One copilot, twelve specialists

Users talk to one product. Behind it, a LangGraph supervisor routes the work through twelve specialised agents:

**Supervisor → Requirement → Policy → Impact → Architecture → Developer → QA → Security → Governance → Release**, then, after deployment, **Root-Cause → Remediation**.

The graph uses typed state and conditional edges, and every node is guarded by budgets:

- `MAX_WORKFLOW_STEPS` limits how many nodes one run may visit.
- `MAX_AGENT_ITERATIONS` caps how many times an agent loop may repeat.
- `MAX_TOOL_CALLS` and a timeout apply to each agent run.

Agents can only call tools on an explicit allowlist. The deploy tool is marked *consequential*. **No agent is on its allowlist**, and it refuses to run without a human approval token.

```
START → supervisor → requirement → policy → ambiguity_check ─(critical)→ human_review
      → impact → architecture → developer → qa → simulation → security → governance → release
      ─(BLOCKED)→ return_evidence
      → human_approval → simulated_release → ClaimIQ → anomaly? ─(no)→ healthy
      → root_cause → release_correlation → remediation → regression_test → defect → SDLC feedback
```

---

## Walking the lifecycle

### 1. The Requirement Agent refuses to guess

It parses the request into parameters, user stories, business rules and Given/When/Then acceptance criteria. Then it flags the threshold wording as a **CRITICAL ambiguity** and stops the workflow until a person chooses "visit 11 onward" or "starting on visit 10". The agent does not silently invent a business rule.

### 2. Policy evidence, with citations

The Policy Agent retrieves `§P-14.2` (the $750 maximum), `§P-14.3` (the 10-visit exemption) and `§P-01.3`. That last section says *cancelled visits do not count toward authorization thresholds*. This turns out to matter later. If nothing relevant exists, the agent returns **"INSUFFICIENT POLICY EVIDENCE"** and does not make up a clause.

### 3. Impact, architecture and a development plan

A data-driven impact map marks each component **KEEP / ENHANCE / ADD / REPLACE** with a reason. It finds 3 microservices, 2 APIs, 3 business rules and 3 tables, along with tests, monitoring, docs and member communications. The one REPLACE it recommends is a hardcoded legacy `750` constant. The deterministic claims engine is never replaced: a guardrail raises an error if anything ever tries.

### 4. Tests that actually run

The QA Agent generates boundary tests (visit 10 vs visit 11, $990 paid against a $1,000 cap, the policy effective date) and negative tests. It then **executes** them against the proposed ruleset: 19 of 19 pass.

### 5. Simulating 10,000 claims

The simulation lab runs the *same* seeded synthetic claims through the current and proposed rules:

- **541 outcomes changed, and 0 of those changes were unexpected.** Each change is classified as an expected consequence of the requirement or as a regression signal.
- **Projected annual impact: about $653K.** This is clearly labelled as a simulated estimate based on synthetic data.
- **Release risk: 48/100, MEDIUM, "READY WITH APPROVAL".**

### 6. A human approves

The Release Manager reviews the evidence and approves. Deployment is simulated.

![Release assessed](screenshots/copilot_release_assessed.png)

---

## Then production happens: ClaimIQ

To show the second half of the loop, the deployment injects a **controlled synthetic defect**. The release-2.4 build counts *completed plus cancelled* visits toward the authorization threshold. The specification was correct, and the implementation drifted from it, which is a common way for real defects to appear.

### Detecting the anomaly without asking an LLM

A naive monitor compares post-release denials with pre-release denials. That would raise an alarm even on a *correct* release, because the new authorization rule is *supposed* to deny some claims.

ClaimIQ uses a **release-aware baseline** instead. It shadow-replays the same post-release claims with the *approved specification* and tests the excess statistically:

> **ANOMALY DETECTED:** physiotherapy AUTH_REQUIRED denial rate **4.81% → 8.48% (+76%, z = 7.0)** versus the approved-spec projection.

When the defect isn't injected, no anomaly is raised. There's a test for that case too.

![ClaimIQ anomaly](screenshots/claimiq.png)

### An agent investigates, within a budget

The Root-Cause Agent runs a bounded loop over seven allow-listed deterministic tools:

1. Find the anomalous segment (physiotherapy).
2. Break down the denial-reason shift. AUTH_REQUIRED accounts for 100% of the excess.
3. Correlate with releases. The shift starts the week release 2.4 shipped, and `AUTH_RULE_184` changed in that release.
4. Trace the rule to its requirement (`BR-391`) and policy section (`P-14.3`).
5. Inspect affected claims. **64 of 64 wrongly denied claims reach the 10-visit threshold only when cancelled visits are added.**
6. Run the requirement's test suite against the deployed build. The two cancelled-visit tests fail.
7. Check operational health. There is no latency or rule-exception spike, so an outage is ruled out.

It tests five hypotheses: cancelled visits counted, an off-by-one error, a service outage, intended behaviour, and a change in member mix. One is supported and four are refuted. Confidence is calculated from **deterministic evidence weights** rather than an LLM's self-assessment, and it comes out **HIGH**.

```
CORRELATED RELEASE: 2.4    CHANGED RULE: AUTH_RULE_184    SOURCE REQUIREMENT: BR-391
LIKELY DEFECT: cancelled visits counted toward the completed-visit threshold (violates P-01.3)
```

If the agent runs out of iterations before finishing, it reports **INCONCLUSIVE** and generates no defect.

### Remediation is verified first and stays a proposal

The Remediation Agent proposes a forward fix ("count COMPLETED visits only") and **verifies it by replaying production claims**. The result is zero mismatches against the approved spec, with every test passing. Rollback is kept as a fallback. It notes that rolling back would also undo the member-friendly $1,000 increase.

It then produces:

- **A runnable pytest regression test** that fails on release 2.4 and passes on the 2.4.1 hotfix.
- **A Jira-style defect, `CLAIMS-1042`.** It is marked High severity, introduced in Release 2.4, and linked to source requirement BR-391. The tracker is mocked.
- **A reprocessing request for the 64 claims.** It needs human approval.

![Root cause and remediation](screenshots/root_cause.png)

---

## Closing the loop: traceability

All of this lives in a traceability graph:

**Requirement → Policy → Business Rule → Component → Implementation → Test → Release → Production Metric → Anomaly → Incident → Defect**

That includes a feedback edge from the defect back to the requirement. Starting from the production anomaly, you can trace back to the release, the rule, the requirement and the policy clause. Starting from the requirement, you can trace forward to the defect it eventually produced. The SDLC feedback step turns the incident into backlog items:

- a requirement revision
- a new regression test in the release gate
- a monitoring alert
- a fix to the test-data generator, which never produced cancelled visits in the first place

---

## What I learned

1. **The most valuable thing an AI copilot does here is stop.** Flagging the ambiguity, refusing to invent a policy clause, and saying "inconclusive" when the evidence runs out all build more trust than fluent output does.
2. **Agents earn their place in open-ended work.** That means routing, choosing the next investigation step, and weighing hypotheses. Arithmetic and policy rules belong in code you can test.
3. **The monitoring baseline needs to know what the release was meant to change.** Comparing against the approved specification, rather than last month, separates intended change from defects.
4. **Label everything honestly.** In the app every capability is tagged DETERMINISTIC, STATISTICAL, RETRIEVAL, SIMULATED, MOCKED or LLM-ASSISTED, and the use-case catalog marks 30 items implemented, 8 partial and 2 planned.

---

## Tech stack

Python 3.11, **LangGraph**, **FastAPI**, **Streamlit**, Pydantic, pandas/NumPy, Plotly, pytest (36 tests) and Docker. Policy retrieval is local BM25, so no paid embedding API is needed. An optional Anthropic Claude integration is used for narratives only.

**Code:** https://github.com/florina787/Data-sets/tree/claude/dreamy-hawking-6m7l6h/claimforge

Run it locally:
```bash
cd claimforge
pip install -r requirements.txt
streamlit run frontend/streamlit_app.py
```

---

*The LLM does not adjudicate claims. Deterministic systems handle the policy calculations. Agents handle reasoning, investigation and SDLC orchestration, and humans control the consequential actions.*

*Tags: Artificial Intelligence · Agentic AI · LangGraph · Health Insurance · Software Engineering*
