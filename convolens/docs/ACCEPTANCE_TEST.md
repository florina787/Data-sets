# Acceptance test (live)

Run on 22 October 2026 against the real 3,000-conversation dataset (`ds_d5b54d698d7f`), Connected mode,
model `gemini-3.5-flash-lite` (free tier), after the token-accounting fix. Nothing in this section is simulated.
Scenarios marked "scripted" in the last table are covered by deterministic tests instead.

## Main question

> *Why are customers experiencing unresolved billing and refund issues, and what evidence supports your findings?*

| Item | Result |
|---|---|
| Request | `req_864548c4798805a899ce` |
| Graph path | `interpret_request → resolve_context → plan_analysis → execute_tools → inspect_results → validate_claims → compose_response` |
| Scope | topic = Billing & refunds (taken from the question; noted in the answer) |
| Tools chosen by the model | `get_resolution_breakdown {}`; `search_conversations {"query": "refund unresolved", "k": 5}` |
| Validation | `numbers_match_validated_metrics` passed; `citations_resolve` passed |
| Tokens (provider-reported) | 1,773 in / 763 out (compose: 1,076 / 600, reporting mode `cumulative`) |
| Latency | 4.5 s |
| Errors | none |

### Counts, cross-checked with independent SQL

| Metric | Value | SQL recount |
|---|---|---|
| M1 Solution offered, outcome unconfirmed | 15 of 194 | 15 |
| M2 Explicitly unresolved | 2 of 194 | 2 |
| M3 Customer-confirmed resolved | 1 of 194 | 1 |
| M4 Unknown outcome | 176 of 194 | 176 |
| M5 Support asked to move to a private channel | 80 of 194 | 80 |
| M6 Customer confirmed the private-channel move | 7 of 194 | 7 |

### Evidence (13 quotes, each matched against the stored message)

Customer examples include `cv_6b131a3069248909/133767` (*"still waiting for a refund..."*),
`cv_15e55092c6eba4d2/87523` (partial refund), `cv_89871ddb7e1cd47f/64182` (*"Three days, and case still
unresolved"*) and `cv_011c54f37f6c49cf/115018` (*"I got charged, can I get a refund??"*).

**Relevance note.** Search on the 3,000 is keyword-only (semantic embeddings cover only the 300 sample). One support
quote, `cv_03f2f0a02a073948/123820` (*"request the channel be added"*), is about a TV channel, not billing: it is
attached as evidence for the private-channel metric, not as a billing example.

### What the answer can and cannot say

Under the active rule labels, 91% of billing outcomes are unknown, so Flo reports patterns (pending refunds, partial
refunds, private-channel handoffs) and says they are not verified causes. It does not invent a reason.

## Other live scenarios

| Scenario | Request | Result |
|---|---|---|
| Unsupported causal and financial question: *"Prove that slow refunds caused customers to churn and how much revenue we lost."* | `req_cfbbf6cc5b9db340f657` | Refused before any model call ("Not available from this data"); 0 tokens; no tools |
| Question, then follow-up *"What about delivery?"* in the same session | `req_f696bbbd4f907936c47d`, `req_7622bb0da922a5483f5d` | Follow-up scope narrowed to Orders & delivery (279 conversations); claims validated; 3.0 s and 2.5 s |
| Action request: *"Propose an action to reduce unresolved billing and refund issues."* | separate run, 22 Oct | Paused at `request_action_approval` with a drafted action; nothing saved; 1,295 / 493 tokens; 11.7 s |

## Scripted (deterministic tests, no live model)

| Scenario | Test |
|---|---|
| Provider failure / exception mid-stream | `tests/test_usage.py::test_provider_exception_during_stream_is_a_model_failure`, `test_interrupted_stream_fails_visibly_without_inflating_usage`, `tests/test_graph.py::test_failing_model_fails_without_demo_fallback` |
| Malformed tool arguments | `tests/test_graph.py` (invalid `args_json` → `invalid_tool_args`, step dropped) |
| Token-budget boundary | `tests/test_usage.py::test_token_budget_boundary` (24,000 passes, 24,001 stops) |
| Approval resume without duplicates | `tests/test_graph.py` approval tests |
| Zero results / too small a scope | `tests/test_graph.py::test_connected_insufficient_scope_is_reported` |
