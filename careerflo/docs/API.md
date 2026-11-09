# API reference

Interactive OpenAPI docs are served by the backend at `/docs` (Swagger UI) and `/openapi.json`. All `/api/*` routes except auth, plans, features, health, learning catalogue and the Stripe webhook require `Authorization: Bearer <access token>` (Supabase Auth in production).

**Metered endpoints** accept an `Idempotency-Key` header. A retry with the same key returns the stored result and is never charged twice. A response from a metered endpoint includes `_usage` (remaining trial and plan balance). Possible errors: `402` when the allowance is exhausted, with `detail.message` and `detail.upgrade_url`; `409` while the same key is still in flight.

| Method | Path | Area |
|---|---|---|
| POST | `/api/account/delete-request` | account |
| GET | `/api/admin/metrics` | admin |
| GET | `/api/agents/catalog` | mission control & governance |
| GET | `/api/agents/metrics` | mission control & governance |
| GET | `/api/agents/runs` | mission control & governance |
| POST | `/api/agents/workflow` | mission control & governance |
| POST | `/api/analytics/report` | career intelligence |
| POST | `/api/analytics/roadmap` | career intelligence |
| GET | `/api/analytics/summary` | career intelligence |
| GET | `/api/applications` | crm & tracker |
| POST | `/api/applications` | crm & tracker |
| POST | `/api/applications/automate` | crm & tracker |
| PATCH | `/api/applications/{aid}` | crm & tracker |
| POST | `/api/applications/{aid}/followups` | crm & tracker |
| GET | `/api/applications/{aid}/history` | crm & tracker |
| POST | `/api/applications/{aid}/interviews` | crm & tracker |
| GET | `/api/approvals` | mission control & governance |
| POST | `/api/approvals/{rid}/decision` | mission control & governance |
| POST | `/api/ats/analyze` | career intelligence |
| GET | `/api/auth/config` | auth |
| POST | `/api/auth/login` | auth |
| GET | `/api/auth/me` | auth |
| POST | `/api/auth/register` | auth |
| POST | `/api/billing/cancel` | billing |
| POST | `/api/billing/change-plan` | billing |
| POST | `/api/billing/checkout` | billing |
| GET | `/api/billing/invoices` | billing |
| POST | `/api/billing/portal` | billing |
| POST | `/api/billing/resume` | billing |
| GET | `/api/billing/subscription` | billing |
| GET | `/api/chat/conversations` | assistant |
| POST | `/api/chat/conversations` | assistant |
| GET | `/api/chat/conversations/{cid}` | assistant |
| POST | `/api/chat/conversations/{cid}/messages` | assistant |
| GET | `/api/chat/meta` | assistant |
| GET | `/api/coding/exercises` | career intelligence |
| POST | `/api/coding/sessions` | career intelligence |
| POST | `/api/coding/sessions/{sid}/run` | career intelligence |
| POST | `/api/company/compare` | career intelligence |
| POST | `/api/company/research` | career intelligence |
| POST | `/api/career-graph` | career intelligence |
| POST | `/api/cover-letters` | career intelligence |
| GET | `/api/features` | account |
| GET | `/api/followups` | crm & tracker |
| GET | `/api/governance/audit` | mission control & governance |
| GET | `/api/governance/summary` | mission control & governance |
| GET | `/api/health` | mission control & governance |
| GET | `/api/interviews` | career intelligence |
| POST | `/api/interviews/mock` | career intelligence |
| GET | `/api/interviews/topics` | career intelligence |
| GET | `/api/interviews/{iid}` | career intelligence |
| POST | `/api/interviews/{iid}/answer` | career intelligence |
| POST | `/api/jobs/boards` | jobs |
| GET | `/api/jobs/radar` | jobs |
| GET | `/api/jobs/saved` | jobs |
| POST | `/api/jobs/search` | jobs |
| GET | `/api/jobs/sources` | jobs |
| GET | `/api/jobs/{job_id}` | jobs |
| POST | `/api/jobs/{job_id}/save` | jobs |
| DELETE | `/api/jobs/{job_id}/save` | jobs |
| POST | `/api/jobs/{job_id}/verify` | jobs |
| GET | `/api/learning/catalog` | career intelligence |
| POST | `/api/match` | career intelligence |
| GET | `/api/mcp/calls` | mission control & governance |
| GET | `/api/mcp/tools` | mission control & governance |
| GET | `/api/plans` | account |
| POST | `/api/portfolio/analyze` | career intelligence |
| GET | `/api/preferences` | account |
| PUT | `/api/preferences` | account |
| GET | `/api/profile` | account |
| PUT | `/api/profile` | account |
| POST | `/api/profile/skills` | account |
| DELETE | `/api/profile/skills/{skill_id}` | account |
| GET | `/api/recruiters` | crm & tracker |
| POST | `/api/recruiters` | crm & tracker |
| PUT | `/api/recruiters/{rid}` | crm & tracker |
| POST | `/api/recruiters/{rid}/email` | crm & tracker |
| GET | `/api/recruiters/{rid}/interactions` | crm & tracker |
| POST | `/api/recruiters/{rid}/interactions` | crm & tracker |
| POST | `/api/recruiters/{rid}/report` | crm & tracker |
| GET | `/api/resumes` | resumes |
| POST | `/api/resumes` | resumes |
| POST | `/api/resumes/tailor` | resumes |
| POST | `/api/resumes/validate` | resumes |
| GET | `/api/resumes/versions/{a}/compare/{b}` | resumes |
| GET | `/api/resumes/versions/{version_id}` | resumes |
| GET | `/api/resumes/versions/{version_id}/export.docx` | resumes |
| GET | `/api/resumes/versions/{version_id}/export.pdf` | resumes |
| GET | `/api/resumes/{resume_id}` | resumes |
| DELETE | `/api/resumes/{resume_id}` | resumes |
| POST | `/api/resumes/{resume_id}/primary` | resumes |
| GET | `/api/resumes/{resume_id}/versions` | resumes |
| POST | `/api/salary/report` | career intelligence |
| GET | `/api/system/llm` | mission control & governance |
| GET | `/api/usage` | account |
| GET | `/api/usage/history` | account |
| POST | `/api/webhooks/stripe` | billing |
