# Privacy Shield

Enforcement is server-side, deterministic code (`backend/app/privacy.py`). It runs **before** data
reaches the browser, the local model, MCP clients, PDF exports, Motion Story GIFs, logs, traces or
conversation memory. It is never CSS, never frontend masking, and never the LLM.

## Classification

| Level | Who receives it |
|---|---|
| `public` | Everyone |
| `internal` | Signed-in users of the same tenant |
| `confidential` | Only roles granted that dataset (`CONFIDENTIAL_GRANTS`, e.g. suppliers → procurement), only for the `ui` purpose; everyone else gets a band or summary |
| `highly_restricted` | Nobody. Personal data, bank details and secrets never leave the server |

**The CTO is not a bypass.** Lenses (CTO, executive, factory, quality, supply, sales, admin) only
change what is shown first. Permissions always come from the account's server-side role, and
role changes apply on the next request.

## Purposes and minimisation

Purposes: `ui`, `llm`, `export`, `mcp`, `memory`, `log`. All except `ui` are *minimised*: they
never receive confidential values, even for a granted role.

## Layers

1. **Tenant isolation** — rows from another tenant are removed first.
2. **Column policy** — `apply(dataset, rows, principal, purpose)` keeps, bands or drops each field
   and returns a `PolicyReport` (counts only).
3. **Free-text scrubbing** — `scrub()` removes API keys, `password=`/`token=` values, Bearer tokens, emails,
   IBAN-like account numbers and phone numbers from questions, answers, tool arguments, traces and memory.
4. **Connector output** — `connectors.neutralise()` treats tool output as untrusted data.
5. **Audit** — each application writes counts, never values.

## What the user sees

Answers carry policy chips ("Policy applied", "Restricted fields excluded", "Aggregated data",
approved source count, data provenance). There is **no reveal control**: when a value is withheld,
Jerry says where it lives and which role can see it (e.g. exact supplier terms stay in the
procurement system).
Asking "Hide confidential details" or "Show me the bank details" never widens access.

## Proof: canary tests

The demo fixtures contain deliberately sensitive canary values (`CANARY-*`) including a row from
another tenant. `backend/tests/test_privacy.py` proves they never appear in any GET endpoint,
answer, trace, memory record, model prompt, MCP result or PDF (PDF streams are decoded:
ASCII85 + Flate). `test_defense.py` does the same for personnel ratings in the portfolio.
