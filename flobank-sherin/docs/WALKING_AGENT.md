# Walking agent experience

## Pieces

| File | Role |
|---|---|
| `frontend/src/sherin/Character.tsx` + `character.css` | One SVG rig with jointed shoulders, elbows, hips and neck, a blinking face and expression variants. States: idle, walking left, walking right, turning, pointing, thinking, working, success, warning, waiting for approval, error |
| `frontend/src/sherin/director.ts` | Shared director with `walkTo`, `presentAt`, `point`, `say`, `sleep` and `transitionTo`. Every call is pausable, speed-scaled and abortable (skip, jump, replay), and reduced motion is honoured |
| `frontend/src/sherin/CharacterLayer.tsx` | Persistent layer in the app shell, so it survives navigation. Sherin walks along a reserved bottom lane (`pointer-events: none`); main content is padded so she never covers controls or final values. Each route has a stop and a greeting. Long jumps use a short fade transition |
| `frontend/src/sherin/machine.ts` | Pure mapping from harness events to gesture and destination, plus `canCelebrate()` (success only after a verified `TASK_COMPLETED` and an approved decision) |
| `frontend/src/pages/Journey.tsx` | Seven scenes, each with an entry, a walking path, a destination, a gesture, a graph reveal, an agent state and an exit. Includes the controls and a narration panel (all content as text) |
| `backend/app/agents/harness.py` | Emits typed events into the run trace as they happen; `AGENT_STARTED` and `TOOL_RUNNING` are persisted *before* the tool runs |
| `backend/app/main.py` | `GET /api/harness/runs/{id}/events` (polling) and `/stream` (server-sent events) |

The character only reflects recorded state. It never calculates money and never changes the agent workflow.

## Live vs synthetic

* **Live LangGraph run** (default): pressing Play starts a real run, `Evaluate trade TP-1003…`, requested by the demo
  identity `pm.ananya` so that a different person (the manager) can approve it. Sherin follows the SSE event stream.
  The run genuinely pauses at `approval_gate`, and scene 6 waits for the approval to be decided.
* **Synthetic demo events**: a scripted sequence labelled *synthetic* everywhere, for viewers without permission
  to start runs. Its approval buttons write nothing to the database.

The harness finishes its tool calls in milliseconds, so scene 3 replays the recorded events in order at a viewing
pace (each event has a minimum on-screen time). The order and content are exactly what the run recorded.

## Asset approval

The approved Ghibli portrait is not in the repository, so the full-body face is drawn to the brief rather than to the
portrait. The character sheet at the bottom of `/journey` shows every state for review. To swap in final artwork,
replace the rig with a Rive or Spine file exported from the approved design that uses the same pose names. Nothing
else needs to change.

## Tests

* `npm test`: unit tests for the event mapping, "never celebrate early", synthetic labelling, the rig states, and
  director pause, speed, abort and reduced motion.
* `node e2e/journey-e2e.mjs`: 12 browser checks.
  * Character on all 15 routes, never intercepting clicks; persistent layer.
  * Chat sends Sherin to point at the cost driver.
  * Walking and turning; pause freezes, resume continues.
  * Charts clickable mid-journey.
  * Live events drive scene 3; approval pauses scene 6; success only after `TASK_COMPLETED`.
  * Jump, replay and skip; mute and speed; reduced motion.
* `node e2e/record-journey.mjs`: records `docs/media/sherin-guided-journey.mp4` from a live run.
