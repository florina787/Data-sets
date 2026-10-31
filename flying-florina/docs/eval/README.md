# Four-question evaluation

Harness: `scripts/eval_four_questions.py` · data: `fixtures/eval/` · raw results: the JSON files in this folder.

## Data

| File | Role | Items |
|---|---|---|
| `four_questions_dev.json` | **Tuning** split. Also supplies the semantic router's labelled examples. | 109 + 3 follow-up conversations |
| `four_questions_test.json` | **Held-out v1.** Measured once before any fixes (results kept as-is below). | 70 + 3 follow-up conversations |
| `four_questions_test_v2.json` | **Fresh held-out v2.** Written after the v1 error analysis and *before* the fixed router was run on it. Never used for tuning. | 72 + 3 follow-up conversations |

Each split covers the four original questions (dev), at least 12 paraphrases per family (16 in dev; 28 per family across dev + v1), other existing
workflows, greetings, general aviation knowledge, unsupported requests, prompt-injection/exfiltration attempts, ambiguous questions,
multi-intent questions and follow-up conversations.

## Results (measured on the build machine, rules + semantic router; local Qwen NOT available there)

| Metric | Held-out v1 (router v1.0) | Fresh held-out v2 (router v1.1) |
|---|---|---|
| Routing accuracy | 94.3% | **95.8%** |
| Macro-F1 (all labels) | 0.923 | **0.958** |
| Four-family routing accuracy | 96.0% | 96.0% |
| Follow-up family accuracy | 100% (6/6 turns) | 83.3% (5/6 turns) |
| Specialist workflow correctness | 96.0% | 96.0% |
| Evidence accuracy (cited docs exist, revision matches, permitted) | 100% (200 citations) | 100% (200 citations) |
| Answer completeness (required sections per family) | 99.6% | 98.4% |
| Latency p50 / p95 per item (routing + workflow, no model) | 163 / 491 ms | 165 / 349 ms |
| Governance: injection + export attempts denied | 3/3 | 3/3 |
| Export tool executions during the run | 0 | 0 |
| Unsupported-claim rate (Evidence Challenger) | not measured: no Qwen | not measured: no Qwen |

Between v1 and v2 the router got four general fixes, each validated on the **dev** split only (dev: 109/109):
definition-style general-knowledge questions take precedence over weak workflow rules; an off-domain relevance gate in front of the
semantic matcher; multi-intent questions use the family asked about first; "driving" counts as an executive cue.

### Known misroutes on v2 (kept, not tuned away)
* "What is pulling down aircraft availability?" → general_knowledge (should be executive): the definition pattern still catches some "What is …" questions.
* "More please." with no context → unsupported (should be clarify).
* "What hurts readiness, and how would modernizing the legacy system help?" → modernization primary (gold: executive).
* Follow-up "Which inspection comes first?" was not recognised as a follow-up (no follow-up cue word).

These are exactly the ambiguous cases the **local Qwen classification stage** is for. On the build machine that stage could not run
(no Qwen there), so these numbers are the router *without* Qwen. Run the harness on your machine to measure it with Qwen:

```bash
backend/.venv/bin/python scripts/eval_four_questions.py --split test_v2          # uses your local Qwen if found
backend/.venv/bin/python scripts/eval_four_questions.py --split test_v2 --no-qwen
```

With Qwen available the run also reports the unsupported-claim rate, Qwen latency and the Qwen-routed share. No number in this
document was estimated; every figure comes from the JSON written by the harness.
