# Four-question intelligence engine

The same specialist-routing and evaluation method as the Conversation Intelligence Copilot, applied to aerospace.

| Family | Original question | Specialist graph |
|---|---|---|
| **Q1 Aircraft Diagnostics** | Why is aircraft AC-204 showing abnormal vibration, and what should engineering investigate? | `aircraft_diagnostics`: intake → precheck → [telemetry ‖ retrieval ‖ history] → diagnostics |
| **Q2 Aircraft Recovery** | Which recovery option could return AC-204 to service fastest, considering spare parts, maintenance scheduling, and engineering approval? | `aircraft_recovery`: … → [parts ‖ scheduling] → compliance → [scenario simulation ‖ draft plan] → approval gate |
| **Q3 Legacy Modernization** | How can we modernize our legacy aircraft maintenance system using APIs, MCP, and AI without replacing the existing platform? | `legacy_assessment`: metadata import → dependency graph → risks → integration options → target architecture → adapter preview → static contract tests → security review |
| **Q4 Executive Intelligence** | What is affecting fleet readiness, and which maintenance improvements could reduce downtime and cost? | `executive_readiness`: precheck → [fleet ‖ downtime trend ‖ parts] → causes → modeled levers |

Every answer then runs: **Qwen explanation → Evidence Challenger → Governance validation**.

```
question ─▶ hybrid router ─▶ specialist agents ─▶ deterministic data (SQL, statistics, simulation)
         ─▶ evidence assembly (workspace) ─▶ local Qwen explanation ─▶ Evidence Challenger ─▶ governance validation ─▶ response
```

## Hybrid router (`backend/app/workflows/router.py`)

1. **Policy**: instruction-override / privilege requests → refused (POL-011/POL-007); exports to external or personal destinations → governance graph (POL-004). Cannot be outscored.
2. **Greeting**: short social messages.
3. **Follow-up**: short questions with a reference cue ("it", "that", "what about AC-118?") reuse the session's family and entities; a clear new family switches family but keeps the aircraft.
4. **Rules**: weighted, high-precision patterns for the four families and the existing workflows; multi-intent questions use the family asked about first and offer the other as a follow-up.
5. **Semantic**: TF-IDF cosine to labelled tuning examples, accepted above a similarity threshold with a margin; an off-domain relevance gate rejects unrelated questions first.
6. **Local Qwen**: closed-set label classification (validated JSON) for what remains ambiguous.
7. **Fallback**: definition-style general aviation knowledge (Qwen only, no fleet claims), unsupported (off-domain), or a clarification with the four questions.

Entities always come from deterministic extractors. Similarities are ranking scores, never shown as confidence.

## Conversation

* Follow-ups keep context per session (`conversation_context` table).
* General knowledge answers come from Qwen and may not mention fleet identifiers (removed if they appear). Without Qwen the assistant says it won't make up an answer.
* Unsupported questions get a scope statement and the four question cards, never fabricated evidence.

## Evaluation

See [eval/README.md](eval/README.md). Measured on the build machine without Qwen: fresh held-out v2 **95.8% routing accuracy, macro-F1 0.958**, 96% four-family routing and workflow correctness, 100% evidence accuracy over 200 citations, 3/3 governance denials with 0 export-tool executions. The first held-out set (v1) measured 94.3% before four general fixes validated on dev only; both are reported.
