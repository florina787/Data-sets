# LinkedIn Demo Script (60–90 seconds)

> Recording tips: 1080p, browser at 125% zoom, sidebar visible. Pre-start Streamlit, reset the session and pick
> persona *Release Manager*. Every number below comes from the default seed (42).

---

**[0:00 — Opening, face or title card]**
> "I built an Agentic AI Copilot for the health-insurance software lifecycle — from a business requirement all the
> way to production claims intelligence."

**[0:06 — Copilot page]**
1. Type: *"Increase physiotherapy annual coverage from $750 to $1,000 and require authorization after 10 completed visits."*
2. Click **ANALYZE REQUIREMENT**. The Requirement Agent builds the user story, business rules and acceptance criteria,
   and **stops**: *"after 10 visits — visit 10 or visit 11?"*
   > "It doesn't invent business rules — it asks a human."

   Choose *visit 11 onward*, then **Apply clarification**.

**[0:20 — Policy Evidence]**
3. The cited sections appear: `§P-14.2` for the $750 maximum, `§P-14.3` for the threshold, and `§P-01.3`, which says
   cancelled visits don't count.

**[0:26 — Impact Analysis]**
4. Show the impact map.
5. Read the counts out loud: "**3 microservices, 2 APIs, 3 business rules, plus tests, monitoring and member comms**",
   then add "and it recommends *replacing* a hardcoded legacy constant — never the claims engine."

**[0:34 — QA & Tests → Claims Simulation]**
6. **GENERATE TESTS**: visit 10/11 boundaries and cancelled visits, with **19/19 passing**.
7. **RUN SIMULATION**.
8. Read out: "**10,000 synthetic claims**, 541 outcomes changed, **zero unexpected**, projected **$653K a year**,
   simulated."

**[0:44 — Release Center]**
9. Risk **MEDIUM → READY WITH APPROVAL**. Enter the approver name and click **Approve**.
   > "Deployment needs a human — no agent can call the deploy tool."

**[0:52 — ClaimIQ]**
10. Open ClaimIQ.
11. A red banner reads **ANOMALY DETECTED**: physiotherapy authorization denials **+76%** against what the approved
    spec predicts.
12. Click **INVESTIGATE**.

**[1:02 — Root Cause]**
13. Show the trace: **Anomaly → Release 2.4 → AUTH_RULE_184 → BR-391**.
14. Root cause, with **HIGH confidence**: *cancelled visits were incorrectly counted*. Every one of the 64 wrongly
    denied claims reaches 10 visits only when cancellations are added.
15. **GENERATE REGRESSION TEST**: real pytest code that fails on 2.4 and passes on the hotfix.
16. **CREATE DEFECT**: `CLAIMS-1042`, severity High, introduced in Release 2.4, source requirement BR-391.

**[1:15 — Traceability]**
17. **VIEW TRACEABILITY**: defect → incident → metric → release → test → rule → policy → requirement, and the
    feedback edge back to BR-391.

**[1:20 — Closing]**
> "The LLM does not adjudicate claims.
> Deterministic systems handle policy calculations.
> Agents handle reasoning, investigation and SDLC orchestration,
> with humans controlling consequential actions."

*Footer text:* Synthetic data only. Not a real insurer, not for real claim adjudication. Built with LangGraph,
FastAPI, Streamlit and Python. Runs for $0 in demo mode.

---

### Suggested post copy
> I built **ClaimForge Copilot**: agentic SDLC plus production intelligence for health insurance (100% synthetic data).
> One copilot drives a requirement through policy RAG, impact analysis, test generation, a 10,000-claim simulation,
> release risk and human approval. Then **ClaimIQ** catches a post-release denial anomaly, traces it to the exact
> rule and requirement, and turns it into a regression test and a defect.
> The design principle: **know when NOT to use an LLM.** Claims are adjudicated by deterministic rules, anomalies are
> detected with statistics, and humans approve consequential actions.
> #AgenticAI #LangGraph #HealthTech #InsurTech #RAG #SDLC
