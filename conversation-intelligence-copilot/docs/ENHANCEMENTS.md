# Six analytical enhancements

These extend the existing graph without replacing anything. The four assignment questions, the registered-operation contract (no model-written SQL) and the provider-neutral LLM client are unchanged. Facts come from DuckDB, evidence comes from FAISS, and a model is used only to interpret: for intent when rules are unsure, and for narrative.

The audit and plan behind this work: [ENHANCEMENTS_PLAN.md](ENHANCEMENTS_PLAN.md).

| # | Enhancement | Where to see it | Backend | Tests |
|---|---|---|---|---|
| 1 | Zero-LLM Intelligence Router | Mode switch above the composer; routing strip on every answer; System Metrics → Token accounting | `agents/router.py`, `agents/intent_router.py`, `observability/store.py` (`request_usage`, `token_accounting`) | `test_router.py`, `test_intent_router.py`, `test_graph.py`, e2e |
| 2 | Query-driven dynamic dashboards | "Dashboard" tab on an answer | `visualization/dashboard.py` | `test_enhancements.py`, e2e |
| 3 | Conversation X-Ray | Ask "X-ray conversation C0000479"; also attached to every trajectory answer | `analytics/xray.py` (registered operation `conversation_xray`) | `test_enhancements.py` (hand-counted fixture), e2e |
| 4 | Autonomous Root Cause Investigator | Ask "What is driving negative sentiment in duplicate charges?" | `analytics/root_cause.py` (operation `root_cause_investigation`, intent `root_cause`) | `test_enhancements.py`, e2e |
| 5 | AI Decision Replay | "AI decision replay" panel under each answer; `GET /api/replay/{request_id}` | `observability/replay.py` | `test_enhancements.py` (incl. sanitiser), e2e |
| 6 | Analytical Evidence Challenger | "Evidence review" section on each answer; QA badge | `agents/evidence_challenger.py` (runs in the QA node) | `test_enhancements.py`, e2e |

Screenshots: [18 dashboard](screenshots/18-dynamic-dashboard.png), [19 replay + evidence review](screenshots/19-decision-replay-and-evidence-review.png), [20 X-Ray](screenshots/20-conversation-xray.png), [21 root cause](screenshots/21-root-cause.png), [22 hybrid retrieval](screenshots/22-hybrid-retrieval.png).

## 1. Zero-LLM Intelligence Router

* **Modes** (chosen per request, remembered per browser):
  * **ANALYTICS ONLY** never calls a model.
  * **HYBRID AI** uses the model for intent when the deterministic stages are unsure, and for the explanation.
  * **AUTO** calls a model only when the question asks for interpretation ("why", "explain", "recommend", "root cause") or when no high-precision stage can route it. All four assignment questions route by rules with zero model calls.
* Each answer shows the route, the reason, how the intent was resolved, and tokens used.
* **Token honesty.**
  * Tokens show as `0 (no model call)` only when no model was called.
  * They show as *not reported* when a provider returned no usage metadata.
  * Streaming usage is taken as the cumulative maximum, not summed across chunks.
  * Dataset-preprocessing (labelling) tokens are reported separately from per-question tokens (`/api/telemetry/tokens`). With `LABEL_SOURCE=rules`, preprocessing used no LLM tokens.
* Intent routing accuracy is reported in [evaluation/INTENT_ROUTING.md](evaluation/INTENT_ROUTING.md): 95.9% on a held-out split, scored once.

## 2. Query-driven dynamic dashboards

* Every answer gets its own dashboard. It contains:
  * a KPI strip;
  * sections (Answer, Reliability, Context, Evidence, Drill-down), each chart with a one-line "why this chart";
  * active filter chips;
  * refinement buttons ("All dates", "Previous month", "Why \<top topic\>?", "Compare top two").
* Refinements **re-run** the analysis through session memory rather than filtering a client-side copy.
* Nothing appears that the analysis did not compute; a test asserts every placed chart exists in the answer.

## 3. Conversation X-Ray

* A message-level diagnosis of one conversation. It covers:
  * escalation signals (escalation requests, urgency);
  * repeated concerns (the same act or a verbatim repeat, and a problem resurfacing after "it works now");
  * communication gaps (negative turns answered without acknowledgement, repeated holds or verification, scripted repeats, a closing action that doesn't fit the issue);
  * the outcome;
  * mean sentiment by phase.
* Every finding cites message IDs.
* The UI keeps the **timeline strip, sentiment line, findings list and transcript in sync**: click any one and the linked messages highlight in the others.
* Signals come from deterministic labels, so they are pointers for review, not a verdict on the agent.

## 4. Root Cause Investigator

* For a topic (named, or the most negative topic in scope), it compares negative and non-negative conversations on observable factors.
* For each factor it reports:
  * negative rate with and without the factor (Wilson 95% CIs);
  * risk difference, relative risk and two-proportion p-value;
  * support on each side;
  * for agent behaviours, **temporal precedence**: does the behaviour occur before the customer's last negative message?
* **Customer reactions (escalation, urgency) are reported as symptoms, not drivers**, because they are expressions of negativity.
* **Alternative explanations are tested:** product mix (chi-square), agent concentration, and the topic's baseline against other topics.
* The language is associational throughout. It warns about multiple comparisons, and factors not observed in the topic are listed as untestable.
* Measured on the full dataset for Duplicate charge: low empathy in replies to negative turns is a strong association (43% vs 25% negative, p 0.001). Closing-action mismatch, scripted repeats and longer conversations are within noise.

## 5. AI Decision Replay

* A sanitised replay built only from what was recorded while the request ran; nothing is re-executed. It includes:
  * the key decisions (route, intent and how it was resolved, plan, explanation source, evidence verdict);
  * a step-through player over every graph node, with engine, duration and output summary;
  * each DuckDB operation with parameters, row count and timing;
  * each FAISS search (mode, methods, fusion, filters, k, latency);
  * each model call (prompt id@version, model, tokens or "not reported", cache hit, latency);
  * QA results.
* Secrets are redacted, secret-named fields and tracebacks are dropped, text is truncated, and prompt bodies are never included.

## 6. Analytical Evidence Challenger

* It runs inside QA after the explanation is written. It checks that:
  * every quoted excerpt is re-read from the database and matches word for word (critical);
  * each top-ranked claim has an example attached;
  * examples fit the claim (negative for negative claims);
  * small samples (n < 30) are disclosed, adding a caveat if missing;
  * counter-evidence is stated ("61% of Item-not-received conversations were not negative");
  * causal wording ("driven by", "causes", "leads to") is **rewritten as association**;
  * a root-cause explanation names only factors the tests support.
* If a model explanation names unsupported drivers, it is replaced by the deterministic narrative, and this is logged as a governance finding.
* Building it exposed two real bugs, both fixed:
  * QA had been reporting "0 evidence items resolved" because the explanation node overwrote the evidence report.
  * `repeated_agent_phrases` was always 0.

## Hybrid retrieval visibility

* Hybrid search (MiniLM + LSA, weighted Reciprocal Rank Fusion) is the default.
* The UI shows that both methods are used:
  * evidence cards and Explorer results show **MiniLM #n · LSA #n** and a "hybrid RRF" tag;
  * Explorer has a *Hybrid / MiniLM only / LSA only* switch;
  * System Metrics shows both backends (dimensions, build time) and the per-method benchmark.

## Known limitations

* **Small samples for root cause.** It needs at least 20 conversations in a topic and 8 on each side of a factor. Within the latest month alone, several factors are untestable.
* **Template-generated data.** X-Ray and root-cause signals come from template-level labels. With synthetic-looking data, associations may reflect how the data was generated rather than real agent behaviour.
* **Weak semantic routing.** The semantic routing stage is built but disabled by its own calibration: no threshold reached 95% precision on validation.
* **Local-model latency.** HYBRID AI with the local model is slow on CPU: about 1 s per warm routing call, 30–55 s for the first call after start-up, and tens of seconds for a model-written explanation.
* **The dashboard is not a saved artefact.** It is regenerated per question. Pinning and sharing dashboards is not implemented.
* **Replay depends on telemetry retention.** Replay reads the telemetry store; if telemetry is cleared, older answers can't be replayed.
