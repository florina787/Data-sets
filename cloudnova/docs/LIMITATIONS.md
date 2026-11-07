# Known limitations & failure modes

Ordered by how much they could change a number a stakeholder sees. Every item is either tested, measured, or
visible in the app — none is hypothetical.

## Decisions CloudNova must make (the tool shows both answers meanwhile)
| # | Issue | Evidence | Impact | Where it shows |
|---|---|---|---|---|
| 1 | **FX direction.** Every EUR/GBP `amount` equals the USD list amount × rate, so the documented `amount × 1.08/1.27` likely converts twice. | 100% of the 1,566 non-USD raw rows reconcile to `list × seats × months × (1−disc) × rate` | Q1 paid 2024: $32,686,371.16 (documented) vs $29,595,624.38 (inverse); all-time paid revenue −$11.1M | Q1 caveat · Data Quality "FX" table · `XFAIL-q1-inverse-fx` |
| 2 | **Account identity.** 3,815 `account_id`s but only 200 `account_name`s, each spread over ~25 ids; 976 ids carry >1 name. | profiling | Q5 top-5 by name shares only 3 of 5 companies with the top-5 by id, in a different order | `XFAIL-top5-by-company-name` |
| 3 | **Dedup precedence** for 16 real status conflicts (paid/pending 7, paid/void 5, paid/failed 2, paid/refunded 2). | `dedup_conflicts` | net revenue swing −$168,441.54 if every loser had won | Reconciliation view, per-answer caveat |

## Modelling limits
* **Account snapshot = latest invoice.** 980 of 3,815 accounts have attributes (plan/region/churned/CSAT) that differ
  across their invoices; there is no `updated_at`, so "latest invoice" is the only defensible current state. Q2 and
  Q4 depend on it.
* **Churn is a snapshot boolean** with no churn date: we report a share of accounts, not a period churn rate, and the
  agent declines "why did X churn" (no reason field exists).
* **Average MRR is over active accounts** (MRR is defined for active subscriptions). Over all accounts the region
  ranking changes (APAC still first; NA and EMEA swap) — documented here; the Q2 caveat states the active-only rule.
* **111 invoices are dated after the build date** (up to 2027). They are included as issued and flagged.
* **81 invoice dates are genuinely ambiguous** (DD-MM-YYYY with both parts ≤ 12). Parsed day-first by the evidence
  rule; a month-first reading would move them between months within the same year — flagged per answer.
* Revenue is recognized on **invoice date** (no service periods in the data), not ratably.

## Query-agent limits (measured)
* **Keyword semantic planner.** It is deterministic and auditable but literal: phrasings outside its patterns go to
  Qwen text-to-SQL or to a "clarify" response. A battery of 24 business-context questions found 8 gaps, fixed with
  generic rules (not per-question templates); more will exist.
* **Qwen2.5-Coder-3B text-to-SQL is unreliable for business logic**: 2/6 stakeholder questions correct when used
  alone; it invented `status = 'churned'`, ranked by paid instead of net revenue, and produced ambiguous joins.
  The guard blocks unsafe SQL but **cannot detect valid-but-wrong SQL** — which is why those answers are labelled
  "check the query" and why approved metrics never go through the LLM.
* **Qwen general knowledge can be wrong** (it described net revenue retention as customer-count retention). General
  answers are labelled "not computed from CloudNova data"; terms that exist in our catalog (MRR, recognized revenue)
  are answered from the catalog instead of the model.
* Qwen latency on CPU: 5–43 s per call. Narration of Qwen-SQL results is rejected if it contains numbers not in the
  result rows (tested with a scripted model), but a grounded narrative can still mis-describe the rows.
* Conversation memory is per session in local SQLite; no auth/multi-tenant isolation (local single-user tool).

## Environment notes
* No Qwen runtime existed in the build container and Ollama's binary could not be downloaded (GitHub release
  host blocked by the network policy); Qwen2.5-Coder-3B-Instruct Q4_K_M was run through `llama-cpp-python`'s
  OpenAI-compatible server instead. The adapter speaks the same API as Ollama/vLLM/LM Studio.
* "Jerome Excel Copilot" was not found under that name; the user identified it as FloPilot mid-build.
