# Conversational AI architecture — how Jerry answers

Jerry is a conversation-first assistant over read-only tools. It runs locally: a deterministic
router and tool layer always produce the facts; the optional local model (Qwen behind an
OpenAI-compatible endpoint) only rewrites prose from those same cited facts. No cloud AI is used.

## Request path

```
question ─► router.parse()          intents, region, weeks, focus, follow-up detection
         ─► command handlers         export · animate · x-ray · containment · scenario · impact · compare ·
            (copilot/command*.py)    globe · plan · defense/team briefings · threats · downtime · alerts ·
                                     licenses · portfolio · architecture · losses · facilities
         ─► topic tools (engine)     sales · inventory · compliance · suppliers · pulse · tech health · …
         ─► Privacy Shield           privacy.apply()/scrub() before anything is returned or stored
         ─► visuals.validate()       typed visual contract 1.0; invalid visuals are dropped, never rendered
         ─► answer                   text + sources + visuals + ui_actions + policy + data_status + limitations
         ─► memory                   scrubbed question/answer, focus, last_agent_run_id
```

Files: `backend/app/copilot/router.py`, `engine.py`, `command.py`, `command_ops.py`,
`backend/app/visuals.py`, `backend/app/privacy.py`, `backend/app/memory/`.

## Intent routing

`router.COMMANDS` lists command intents in precedence order. A command wins when its keyword
score is at least the best topic score, so "Prepare a PDF of supplier risk" exports instead of only
listing suppliers. Explicit rules break known ambiguities: a question that names a batch, lot or
potato goes to inspection even if it also says "supplier". Greetings and thanks (`is_small_talk`)
get a short reply and the capability list instead of a refusal.

## Multi-turn context

Each conversation stores, after scrubbing:

* the last topic intents, region and period (so "What about Quebec?" reuses the sales question);
* `focus`: the entity the last answer was about (supplier, site, initiative, department);
* `last_agent_run_id`: so "Where did that come from?" opens the X-Ray of the previous answer.

Follow-ups say so in the answer ("Follow-up: used the topic of your previous question").

## What the model may and may not do

* The model never decides authorization. Permissions come from the server-side role
  (`auth.PERMISSIONS`); lenses only change emphasis.
* The model never emits SQL, kubectl, code or tool calls that are executed. Tools are a fixed
  allowlist with typed arguments.
* Tool output is treated as data: `connectors.neutralise()` strips instruction-like text.
* If the model is unavailable, the rules-based answer is returned unchanged ("Jerry · rules-based").

## Answer contract

| Field | Meaning |
|---|---|
| `text` | Plain-language answer, with numbered source references |
| `sources` | Each source with its provenance label (verified, operational record, modelled, synthetic) |
| `visual_schema` | `"1.0"` |
| `visuals` | Validated visuals (see `VISUAL_RESPONSE_SCHEMAS.md`) |
| `ui_actions` | Allowlisted actions: download, open_globe, open_xray, open_page, open_motion, open_containment |
| `policy` | Which policy was applied, approved source count, whether fields were withheld |
| `data_status` | e.g. synthetic, simulated, operational |
| `limitations` | What the data cannot answer |

## Tests

`backend/tests/test_conversation.py` (multi-turn journey, focus, follow-ups),
`test_command.py` (commands, exports, motion), `test_defense.py` (security and portfolio intents),
`e2e/command.spec.ts` and `e2e/memory.spec.ts` (browser).
