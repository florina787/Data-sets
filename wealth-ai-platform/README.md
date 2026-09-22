# Wealth Intelligence & Advisor AI Platform

A reference implementation of an enterprise AI platform for a wealth division
(advisors, portfolio managers, operations, compliance). It is built one step
at a time. Each step is small, tested and runnable.

## Roadmap

| Step | What it adds | Status |
|------|--------------|--------|
| 1 | Foundation: identity (JWT), authorization *before* retrieval, audit log, tracing | ✅ done |
| 2 | Risk policy: use cases classified READ / REASON / DRAFT / RECOMMEND / ACT | next |
| 3 | Ingestion pipeline: parse, classify, PII detection, chunking, metadata | |
| 4 | Hybrid retrieval: query rewrite, metadata filter, BM25 + vectors, RRF, rerank | |
| 5 | LLM gateway: routing, retries, circuit breaker, fallback, cache, cost | |
| 6 | Guardrails and compliance checks | |
| 7 | Tools (MCP-style) and the meeting-prep agent | |
| 8 | Human-in-the-loop actions workflow | |
| 9 | FastAPI service | |
| 10 | Evaluation harness and CI gate | |

## Step 1: the foundation

| File | Purpose |
|------|---------|
| `wealth_ai/security/identity.py` | Validates the JWT (signature, expiry, issuer, audience) and turns it into a `Principal` |
| `wealth_ai/security/authz.py` | Computes an `AccessScope` (which clients and document classifications this person may see) from the entitlement store, **before** any data is fetched |
| `wealth_ai/audit/log.py` | Hash-chained audit log; editing any past record is detected |
| `wealth_ai/observability/tracing.py` | `trace_id` per request, a timed span per stage, P50/P95/P99 metrics |
| `wealth_ai/data/seed.py` | Fictional clients, portfolios, CRM notes and documents |

Key design choice: the token says *who* you are; it does not list your
clients. Entitlements are looked up on every request so a book transfer or
termination takes effect immediately.

## Run it on a Mac

```bash
cd wealth-ai-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
