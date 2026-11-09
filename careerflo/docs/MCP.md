# MCP servers and gateway

Seven servers are built with the official Python MCP SDK (`FastMCP`). They are reached through the SDK's **in-memory transport** (`create_connected_server_and_client_session`). These are real JSON-RPC MCP sessions (`initialize`, `tools/list`, `tools/call`) with no listening port, which is the lightest transport for services on the same VM. Each server can also be exposed over **stdio**:

```bash
cd backend && .venv/bin/python -m app.mcp_servers.run jobs
```

| Server | Version | Tools |
|---|---|---|
| A Job Discovery (`jobs`) | 1.0.0 | search_all_jobs, search_jsearch_jobs, search_adzuna_jobs, fetch_greenhouse_jobs, fetch_lever_jobs, fetch_ashby_jobs, search_indeed_origin_jobs, search_linkedin_origin_jobs, normalize_job, deduplicate_jobs, verify_job_url, save_job |
| B Resume Intelligence (`resume`) | 1.0.0 | parse_resume, extract_skills, analyze_resume, compare_resume_to_job, tailor_resume, validate_resume_claims, generate_pdf, generate_docx |
| C Application Tracking (`applications`) | 1.0.0 | create_application, update_application, list_applications, record_interview, schedule_followup, retrieve_application_history |
| D GitHub Portfolio (`portfolio`) | 1.0.0 | list_repositories, inspect_repository, analyze_technology_stack, match_project_to_job, generate_portfolio_summary |
| E Company Research (`company`) | 1.0.0 | retrieve_company_information, analyze_job_requirements, summarize_public_sources, compare_companies |
| F Career Analytics (`analytics`) | 1.0.0 | calculate_application_metrics, calculate_interview_conversion, analyze_salary_distribution, identify_skill_gaps, generate_dashboard_data, build_career_graph |
| G Governance (`governance`) | 1.0.0 | validate_tool_request, check_permissions, redact_sensitive_data, request_human_approval, record_audit_event |

## Gateway controls (`app/mcp_gateway.py`)
- **Discovery:** `tools/list` on every server. Schemas shown to agents and the UI have `user_id` and `requested_by` removed.
- **Allowlist:** `AGENT_ALLOWLIST[agent]` is a static set of `server.tool`. For example, the Interview agent cannot touch `applications.update_application`. The `user` principal (REST routes) cannot call governance tools that create approvals.
- **Identity:** any `user_id` an agent supplies is discarded; the authenticated user's id is injected. A test proves a forged `user_id` cannot read another user's application.
- **Validation:** the MCP server validates arguments against the tool's JSON schema (pydantic). The gateway caps argument size at 120 KB.
- **Limits:** 120 tool calls per user per minute, 45 s per call, 24 calls per workflow run.
- **Audit:** an `mcp_tool_calls` row (redacted arguments, status `ok|error|denied|timeout`, duration, tool version) is written for every attempt.
- **Untrusted data:** external text (job descriptions, Wikipedia extracts, GitHub descriptions) passes through `neutralize()`. Instruction-like phrases are removed and flagged before any model sees them.
- **Approvals:** `update_application(status="applied")` never acts. It creates a pending approval request that only the user can approve, through a REST endpoint no tool can reach.

`langchain-mcp-adapters` was not needed: agents call tools deterministically through the gateway rather than letting the model pick arbitrary tools.
