# API contract

The live OpenAPI schema is at `http://localhost:8000/docs`. Every request needs a session. In demo mode that is the
`X-Demo-User: <seeded user id>` header; in production mode it would come from SSO, which is unconfigured, so requests
return 401. Actor and tenant always come from the session, never from the body. Errors use one shape:

```json
{"error": {"category": "policy", "code": "release_gates_blocking", "message": "…", "details": {"blockers": ["G-REVIEWS: …"]}, "trace_id": "…"}}
```

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/health`, `/ready` | — | Liveness; readiness (database, seed, knowledge base) |
| GET | `/api/meta` | — | Banner, modes, personas (empty in production), roles, permissions, states, transitions |
| GET | `/api/me` | session | Effective permissions |
| GET/POST | `/api/changes` | change.read / change.create | Create runs the requirements agent |
| GET | `/api/changes/{id}` | change.read | Full detail: requirement versions, clarifications, evidence, impact, models, revisions, runs, reviews, approvals, binding, releases, alerts, messages, agent invocations, next steps, interrupt |
| POST | `/api/changes/{id}/clarifications` | clarification.answer | `{key, answer?, structured?, use_suggested?}`; `use_suggested` is demo-only |
| POST | `/api/changes/{id}/requirements/approve` | requirements.approve | Blocked while required clarifications are open |
| POST | `/api/changes/{id}/investigate` | investigate.run | Evidence + impact agents |
| POST | `/api/changes/{id}/impact/accept` | impact.accept | → DEVELOPMENT |
| POST | `/api/changes/{id}/candidates` | candidate.register | `{model_id}`; verifies digest; invalidates prior reviews and approvals |
| POST | `/api/changes/{id}/evaluations` | evaluation.run | 202 + run; executes as a background job |
| GET | `/api/evaluations/{run_id}` | change.read | Status, digests, full computed summary |
| POST | `/api/evaluations/{run_id}/cancel` | evaluation.cancel | Cooperative cancellation |
| GET | `/api/evaluations/{run_id}/predictions?cell=&limit=` | change.read | Sample-level fixture predictions |
| POST | `/api/changes/{id}/reviews` | review.{code,domain,privacy,qa} | `{kind, decision: APPROVE\|REJECT, comment}` |
| GET | `/api/changes/{id}/release-readiness` | change.read | Live release gates |
| POST | `/api/changes/{id}/release-approvals` | release.approve | `{decision: APPROVED\|REJECTED, comment}`; gates must pass; approver ≠ author |
| POST | `/api/changes/{id}/releases` | release.execute | **Requires `Idempotency-Key`**; revalidates the approval; consumes it; simulated canary |
| POST | `/api/releases/{id}/promote` | release.execute | Needs ≥ 1 window at the current stage and no open alert |
| POST | `/api/releases/{id}/monitoring/advance` | monitoring.advance | Simulates one window; evaluates the alert rule |
| GET | `/api/releases/{id}/monitoring` | monitoring.read | Windows, cumulative cohort cells, reference, alerts, rollbacks |
| POST | `/api/alerts/{id}/investigate` | alert.investigate | Monitoring agent; may set ROLLBACK_RECOMMENDED |
| POST | `/api/releases/{id}/rollback-requests` | rollback.request | **Requires `Idempotency-Key`**; `{reason, alert_id?}` |
| POST | `/api/rollbacks/{id}/decision` | rollback.approve | `{decision: APPROVE\|REJECT}`; approver ≠ requester; compatibility checked |
| POST | `/api/changes/{id}/workflow/resume` | investigate.run | `{thread_id}`: resume a failed agent thread |
| POST | `/api/changes/{id}/copilot` | change.read | Deterministic answers from persisted state |
| POST | `/api/changes/{id}/cancel` | change.cancel | |
| GET | `/api/changes/{id}/audit` | audit.read | Events + chain verification |
| GET | `/api/changes/{id}/traceability` | change.read | Requirement → … → rollback chain |
| GET | `/api/changes/{id}/report?format=md\|json` | change.read | Exportable report |
| GET | `/api/changes/{id}/telemetry` | change.read | Per-agent latency, invocations, tool calls, tokens, cost |
| GET | `/api/metrics/process` | session | Process metrics with definitions |
| GET | `/api/knowledge/documents`, `/api/knowledge/search?q=` | session | Authorization-filtered |
| GET | `/api/evidence/{source}/{version}/{section}` | session + document access | Exact excerpt |
| GET | `/api/agents/contracts`, `/api/connectors`, `/api/scenarios` | — | Contracts; connector status; backlog |
| POST/GET/DELETE | `/api/images` | image.upload | Sandbox only when `IMAGE_SANDBOX_ENABLED=true`; raw PNG/JPEG body; `purpose`, `consent`, `retention_days`, `training_consent` query params |
| POST | `/api/demo/reset` | demo.reset | Demo mode only |
