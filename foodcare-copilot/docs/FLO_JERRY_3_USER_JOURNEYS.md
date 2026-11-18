# Flo & Jerry 3.0 user journeys

Each journey lists what the user does and what proves it works.

## 1. CTO morning check (2 minutes)

Overview → Enterprise Pulse: "Since your last visit", ranked priorities, health strip → click a
priority → investigation panel with evidence → "Record decision" (decision journal).
*Proof:* `test_pulse.py`, `e2e/enterprise.spec.ts`.

## 2. Ask, see, verify, export

Jerry AI → welcome cards → "Are we under attack?" → radar, exposure graph, heatmap → **Show how
Jerry knows** (X-Ray) → "Prepare a security and savings board report" → download PDF.
*Proof:* `e2e/command.spec.ts`, `test_defense.py`, `test_command.py`.

## 3. Continuous supplier investigation

"Which suppliers are creating the most exposure?" → "Why that one?" → "What if they stop
shipping for two weeks?" → "Animate it" → "Make this board-ready". Context (focus supplier) is
carried across turns.
*Proof:* `test_conversation.py::test_continuous_supplier_investigation`.

## 4. Containment under control

Defense Command → Containment → choose action + asset → Preview (dry run) → Propose → second
person approves with step-up → execute (dry run) within 15 minutes. Protected OT is refused at
preview.
*Proof:* `test_defense.py::test_containment_is_guarded_end_to_end`, `e2e/command.spec.ts`.

## 5. What is every team building?

Operations → Team & delivery portfolio → click Marketing → Gantt + dependency graph show the
blocked loyalty relaunch → "Brief me" → decisions awaiting approval.
*Proof:* `test_defense.py::test_department_questions`, `e2e/command.spec.ts`.

## 6. Connect the enterprise honestly

Technology → Connect your enterprise → see every connector's real state → read setup scope →
(with credentials on the server) Run read-only test.
*Proof:* `test_command.py::test_registry_is_honest_when_nothing_is_configured`.

## 7. Return visit and weekly review

Continuity: since-last-visit changes, open investigations, decision journal, Reports → Weekly CTO
review, Reports history ("time machine").
*Proof:* `test_pulse.py`.
