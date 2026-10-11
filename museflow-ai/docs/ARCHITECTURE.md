# MuseFlow AI — Architecture

## Layers

```text
┌──────────────────────────── Streamlit UI (ui/) ─────────────────────────────┐
│ app.py → sidebar → one page module per screen (lazy-imported)              │
│ components.py · themes.py · animations.py · charts.py · session.py         │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ SessionContext (one per browser session, in st.session_state)
┌───────────────────────────────▼─────────────────────────────────────────────┐
│ services/demo_engine.py — DemoEngine                                        │
│   start(scenario | request) · resume(run_id, decision) · runs registry      │
│   owns: SessionStores · AuditLogger · ToolRegistry · SessionCheckpointStore │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ graph.invoke(state, config, context=MuseContext)
┌───────────────────────────────▼─────────────────────────────────────────────┐
│ workflows/graph.py — LangGraph StateGraph(MuseState, context_schema)        │
│   intent_router → supervisor ⇄ agents … → respond → END                     │
│ workflows/state.py (typed state + reducers) · routing.py · params.py        │
│ workflows/checkpoints.py (per-session InMemorySaver)                        │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ agent_node() wrapper: timing, tool recording,
                                │ retries, error capture, trace events
┌───────────────────────────────▼─────────────────────────────────────────────┐
│ agents/*.py — deterministic agent-role functions                            │
│ services/tool_registry.py — allowlisted, simulated tools                   │
│ data/ — synthetic fixtures (JSON + Markdown documents)                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

`services/`, `workflows/` and `agents/` never import Streamlit, so the whole engine is unit-testable.

## The graph

```text
                 START
                   │
             intent_router        (Supervisor: validate, classify, build queue)
                   │
        ┌──────► supervisor ◄──────────────────────────────┐
        │          │ conditional edge = head of state.queue │
        │   ┌──────┼───────┬────────┬─────────┬──────────┐  │
        │ planning research memory  email  calendar  document browser analytics
        │   └──────┴───────┴────────┴─────────┴──────────┴──┘ (all return to supervisor)
        │          │
        │      governance ── deny ──► audit
        │          │ require_approval
        │      approval  ◄── LangGraph interrupt(): run pauses, checkpoint saved
        │       │      │
        │  approved  rejected / cancelled
        │       │      │
        │ simulate_action   │
        │       └──► audit ◄┘
        │              │
        └──────────────┘
                   │ queue empty
                respond → END
```

### How routing works

* `intent_router` resolves the scenario (explicitly chosen, or matched from chat text by keyword rules),
  validates parameters against an allowlist, and writes an initial `queue`, e.g.
  `["email", "governance", "audit"]`.
* After every node, control returns to `supervisor`. Its conditional edge sends the run to the
  head of the queue (or `respond` when the queue is empty).
* Agents can change the queue at run time — that is where the conditional behaviour lives:
  * **Planning** in the dream-team scenario inserts the specialists the visitor picked.
  * **Research** topics with a scoring matrix add **Analytics**.
  * **Governance** inserts **approval** when a consequential tool is proposed, or replaces the
    queue with `["audit"]` when a policy denies it.
  * **Approval** inserts **simulate_action** only on `approved`; otherwise it jumps to audit.
* The supervisor also enforces invariants on every hop (defence in depth): it drops
  `simulate_action` without an approval, inserts governance if an action appears without one,
  and inserts approval if governance demanded it.

### State

`MuseState` (TypedDict) — `outputs` merges by node name, `trace` and `errors` append via reducers.
Each node emits exactly one trace event `{seq, node, agent, kind, status, started_at, duration_ms,
message, input, output, tool_calls}`. Workflow Galaxy, chat activity lists, analytics and the
audit log are all derived from these events, so what you see is what ran.

### Human approval and checkpoints

`approval` calls `langgraph.types.interrupt()`. The graph stops, LangGraph stores a checkpoint
in the session's `InMemorySaver` under thread `"{session_id}:{run_id}"`, and the run is listed
as *Pending*. `DemoEngine.resume()` sends `Command(resume={"decision": …})`, which continues the
same thread from the checkpoint — earlier nodes are not re-executed (verified in
`tests/test_approvals.py::test_resume_comes_from_checkpoint_not_restart`, which even recompiles
the graph between pause and resume).

### Retry and error handling

* An agent may raise `TransientSimulatedError`; the wrapper records a `retrying` event, keeps the
  node at the head of the queue and the supervisor routes back to it (max 2 retries). The browser
  booking scenario uses this to simulate a page-load timeout.
* Any other exception produces a `failed` event, sets `status="error"`, and routes to `audit` so
  the failure is still recorded before `respond` explains it.

## Agent roles

| Node | Character | What the code actually does |
|---|---|---|
| intent_router / supervisor / respond | 🦄 Lumi | keyword intent rules, param validation, queue routing, template response |
| planning | 🦋 Nova | Kahn topological sort, capacity-based scheduling, time-block placement, team recruitment |
| research | 🧚 Aurora | reads curated fixture briefs; ranks fictional destinations with a scoring formula |
| memory | 🌸 Iris | session memory add/search; keyword-derived planning signals |
| email | 💌 Rosie | template + tone composition; proposes `email.simulate_send` |
| calendar | 🌙 Celeste | free-window search, conflict detection, next-free-slot suggestion |
| document | 📚 Athena | term-frequency extractive summary, `Label: value` fields, regex entities, diff redlines |
| browser | 🧭 Wren | reads fictional pages from fixtures, fills forms in memory, simulated retry |
| analytics | 🔮 Stella | weighted decision matrix, critical-path method, run metrics |
| governance | 🛡️ Pearl | allowlist, synthetic-recipient, sensitive-data and approval policies |
| approval / simulate_action | 💖 Cora | LangGraph interrupt; executes the approved tool in simulation |
| audit | ✨ Astra | SHA-256 hash-chained audit entries |

None of these are autonomous LLM agents; they are deterministic role simulations.

## Future extensibility (not implemented)

The seams for a future **private** deployment are deliberate:

* `ToolRegistry` — swap simulated handlers for real connectors (MCP servers, OAuth APIs) behind the same allowlist + approval gate.
* `MuseContext` — inject a model client into a separate private build; agent functions already receive dependencies rather than importing them.
* `SessionCheckpointStore` — replace `InMemorySaver` with a persistent saver for multi-device sessions.
* `MemoryStore` — back with a per-tenant database.

The public demo must stay free of all of these; `tests/test_security.py` fails if LLM SDKs or HTTP clients are introduced.
