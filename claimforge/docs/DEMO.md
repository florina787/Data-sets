# End-to-End Demo Guide (V1 scenario)

> NorthStar Health Benefits is fictional; all data is synthetic. DEMO_MODE: zero LLM calls, no API key.

**Current policy:** physiotherapy is reimbursed at 80% with a $750 annual maximum, and no authorization is needed
for the first 10 completed visits (P-14.1 to P-14.3).
**Proposed requirement:** *"Increase physiotherapy annual coverage from $750 to $1,000 and require prior
authorization after 10 completed visits."*

## Start

```bash
cd claimforge
pip install -r requirements.txt
streamlit run frontend/streamlit_app.py     # http://localhost:8501
uvicorn app.api.main:app --port 8000        # http://localhost:8000/docs   (optional)
```

You can also run `python scripts/run_demo.py` for a terminal-only run.

## Walkthrough (25 steps → where to see them)

| # | Step | UI | API |
|---|---|---|---|
| 1–2 | Parse requirement, user stories, acceptance criteria | Copilot → **ANALYZE REQUIREMENT**, then Requirements | `POST /requirements/analyze` |
| 3 | Retrieve policy (P-14.2, P-14.3, P-01.3, P-40.1) | **VIEW POLICY**, then Policy Evidence | `POST /policy/search` |
| 4 | Threshold ambiguity → **human clarification** (choose "visit 11 onward") | Copilot / Requirements | `clarifications: {"AMB-AUTH-THRESHOLD": "FROM_VISIT_11"}` |
| 5 | Impacted components (3 services, 2 APIs, rules, tables, tests, monitoring) | **RUN IMPACT ANALYSIS**, then Impact Analysis | `POST /impact/analyze` |
| 6 | Implementation plan, patch, schema | Development Plan | `POST /workflow/run` (`stop_after: developer`) |
| 7 | Generate and execute tests (19/19 pass) | **GENERATE TESTS**, then QA & Tests | `POST /tests/generate` |
| 8–12 | Generate 10,000 claims; run V1 and V2; compare; financial impact | **RUN CLAIM SIMULATION**, then Claims Simulation | `POST /simulation/run` |
| 13–14 | Release risk, governance and security review | **ASSESS RELEASE**, then Release Center / Security & Governance | `POST /release/assess` |
| 15–16 | **Human approval** → simulated deployment, with the controlled defect injected | Release Center form | `POST /release/deploy-simulated` |
| 17–19 | Post-release claims; physio denial anomaly detected (z ≈ 7) | ClaimIQ | `GET /claimiq/metrics`, `POST /claimiq/detect-anomaly` |
| 20–21 | Correlate with release 2.4, identify the AUTH_RULE_184 defect | ClaimIQ → **INVESTIGATE**, then Root Cause | `POST /claimiq/investigate` |
| 22 | Remediation: count COMPLETED visits only (verified by replay) | Root Cause | ↑ |
| 23 | Regression test (fails on 2.4, passes on 2.4.1) | **GENERATE REGRESSION TEST** | ↑ |
| 24 | Jira-style defect CLAIMS-1042 (mocked tracker) | **CREATE DEFECT** | `POST /defects/generate` |
| 25 | Trace defect → incident → anomaly → metric → release → test → rule → policy → BR-391 | **VIEW TRACEABILITY** | `GET /traceability/CLAIMS-1042` |

## Things to try
- Change the persona in the sidebar. The Copilot summary re-orders its emphasis, but the facts stay the same.
- In the Claims Simulation Lab, pick `RULESET_V2_DEFECTIVE` as PROPOSED. It shows 145 **UNEXPECTED** changes.
- In QA & Tests, run the suite against `RULESET_V2_DEFECTIVE`. Two critical cancelled-visit tests fail.
- In ClaimIQ, switch the baseline to HISTORICAL. It also flags the intended authorization denials, which is why
  the release-aware projection is the default.
- Untick "Inject controlled synthetic defect" in the Release Center. ClaimIQ then reports HEALTHY.
- Upload a `.md` containing "ignore previous instructions". That line is quarantined.
- On the System Metrics page, check the node order and latency, the tool allowlist and the audit log. Paid LLM calls stay at 0.
