# API

Interactive OpenAPI docs: `http://localhost:8000/docs` (JSON at `/openapi.json`).

All routes are under `/api/v1`. Authenticate with `POST /auth/demo-login {"user_id": "usr-patient-demo"}` and send
`Authorization: Bearer <token>`. Errors always use:

```json
{"error": {"code": "FORBIDDEN", "message": "Missing permission: sdlc:read", "request_id": "…", "details": null}}
```

Every response carries `X-Request-ID` (and `X-Trace-ID` when tracing is on).

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/health` | — | liveness, DB, LLM/tracing status, config warnings |
| GET | `/config/public` | — | non-secret UI config (banner, services, radii, disclaimers) |
| POST | `/auth/demo-login` | — | demo JWT (disabled in staging/production) |
| POST | `/copilot/greet`, `/copilot/chat` | patient:chat | Christina conversation (`scenario` optional) |
| POST | `/search/facilities` | patient:search | directory + radius filter, no availability |
| POST | `/search/appointments`, `/workflows/start` | patient:search | run the patient LangGraph |
| GET | `/workflows/{id}`, `/workflows/{id}/events` | owner / agents:read | state, agent trace, audit events |
| GET | `/facilities?service&city&limit&offset`, `/facilities/{id}` | patient:search | paginated directory |
| GET | `/appointments/{slot_id}` | patient:search | freshly verified slot |
| POST | `/bookings/request` | patient:book | booking-handoff workflow (idempotency key, consent required) |
| GET | `/bookings`, `/bookings/{id}` | owner | booking handoffs |
| POST | `/bookings/{id}/patient-reported` | patient:self | self-reported (unverified) booking |
| GET | `/approvals`, `/approvals/{id}` | visible approvals | Human Approval Center |
| POST | `/approvals/{id}/decision` | depends on action | approve/reject; resumes the paused graph |
| GET/PUT | `/preferences`; POST/GET `/consents`; GET `/notifications` | user | patient settings |
| GET | `/searches/history[?saved=true]`; POST `/searches/{id}/save`; DELETE `/me/data` | user | history & deletion |
| GET | `/knowledge/search?q=`, `/knowledge/documents` | patient:chat / user | RAG with citations |
| GET | `/dashboard` | user | dashboard figures (qualified) |
| GET | `/agents`, `/agents/metrics`, `/graphs/patient` | agents:read / patient:search | registry, measured metrics, graph |
| GET | `/sdlc/requirements`; POST `/sdlc/requirements/analyze` | sdlc:read / sdlc:write | Requirements Agent |
| GET | `/sdlc/architecture` | sdlc:read | Mermaid diagrams |
| POST | `/sdlc/tests/run`; GET `/sdlc/tests/pytest-report` | sdlc:write / read | QA scenario suite, pytest JUnit import |
| POST | `/sdlc/security/scan`, `/sdlc/simulations`, `/sdlc/rca`, `/sdlc/anomalies/detect` | sdlc:write | agents on demand |
| GET | `/sdlc/anomalies`, `/sdlc/builds`, `/sdlc/releases`, `/sdlc/runs` | sdlc:read | monitoring & releases |
| POST | `/sdlc/releases/deploy` | approval:release (+ approved request for production) | simulated deploy |
| POST | `/sdlc/demo/start`; GET `/sdlc/demo/{id}`, `/traceability`, `/artifacts/{stage}` | sdlc | 90-Day MRI challenge |
| GET | `/telemetry`, `/telemetry/token-benchmark` | telemetry:read | dashboards |
| GET | `/metrics` | — (internal scrape) | Prometheus exposition |
| GET | `/governance/overview`, `/governance/audit`, `/governance/audit/verify` | governance:read | governance |
| POST | `/admin/demo/reset`, `/admin/retention/run`; GET `/admin/users` | admin:all | administration |

### Example

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/demo-login -H 'content-type: application/json' \
  -d '{"user_id":"usr-patient-demo"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s localhost:8000/api/v1/search/appointments -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"service":"MRI","location":"Toronto","radius_km":25,"existing_appointment_days":90,"requisition_status":"HAS_REQUISITION"}'
```
