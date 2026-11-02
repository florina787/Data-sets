<div align="center">

<img src="docs/assets/v2/banner_v3.svg" width="100%" alt="Flying Florina 3.0 — Global Aerospace Predictive Intelligence & Resilience Platform" />

<br/>

![Synthetic data](https://img.shields.io/badge/data-100%25%20synthetic-D7B46A?style=for-the-badge)
![Local Qwen](https://img.shields.io/badge/LLM-your%20local%20Qwen-14B8A6?style=for-the-badge)
![Offline](https://img.shields.io/badge/runtime-offline-050B18?style=for-the-badge)
![Paid APIs](https://img.shields.io/badge/paid%20APIs-%240-22D3EE?style=for-the-badge)
![Policy](https://img.shields.io/badge/policy-deny%20by%20default-10B981?style=for-the-badge)

![pytest](https://img.shields.io/badge/pytest-160%20passed-10B981)
![playwright](https://img.shields.io/badge/playwright-22%20passed-10B981)
![vitest](https://img.shields.io/badge/vitest-9%20passed-10B981)
![forecast](https://img.shields.io/badge/90--day%20demand%20MAE-2.86%20vs%204.03%20baseline-22D3EE)
![routing 2.0](https://img.shields.io/badge/2.0%20held--out%20routing-95.8%25-22D3EE)
![routing 3.0](https://img.shields.io/badge/3.0%20held--out%20routing-90.3%25-F59E0B)
![egress](https://img.shields.io/badge/offline%20egress%20attempts-0-050B18)
![license](https://img.shields.io/badge/license-GPL--3.0-14B8A6)

### Forecast. Map. Simulate. Explain. Govern.

**Flying Florina 3.0** is a global aerospace predictive-intelligence and resilience platform: component forecasting, a global
interactive map with a +90-day timeline, maintenance digital twins, supply-chain and resilience simulation, a civilian airspace-safety
lab, software change-impact analysis and persistent conversational memory, all driven by a **governed agent harness**. Models and
simulations produce every number; **your local Qwen** explains; deterministic policy decides; humans approve.

<sub><b>Independent concept demo | Not affiliated with or endorsed by IFS.</b> All operational data is synthetic and fictional. No live IFS connection,
no certification, no airworthiness determinations, no promised savings.</sub>

<br/><br/>

<img src="docs/screenshots/v3/02_global_map.png" width="100%" alt="Flying Florina 3.0 Global Intelligence map" />

<sub>Global Intelligence: MapLibre globe with inventory-forecast layer, predictive timeline, KPIs, region comparison and freshness. No tile service, no network.</sub>

</div>

---

<div align="center">

**[3.0 overview](#-flying-florina-30)** ·
**[3.0 screens](#-the-30-screens)** ·
**[Harness](#-the-governed-agent-harness)** ·
**[Measured](#-30-measured-results)** ·
**[Deploy](#-deployment-modes)** ·
**[2.0: four questions](#-the-four-signature-questions)** ·
**[Local Qwen](#-local-qwen-setup)** ·
**[Quick start](#-quick-start)** ·
**[1.0 deep dive](#-platform-foundations-from-10)** ·
**[Docs](#-documentation)**

</div>

---

## 🌍 Flying Florina 3.0

| # | Section | What it does | Route |
|---|---|---|---|
| 1 | **Global Intelligence** | Globe / 2D / lite map, 6 layers (facilities, component health, supply chain, inventory forecast, disruptions, recovery), TODAY→+90 d timeline, search, filters, region comparison, report export | `/global` |
| 2 | **Component Forecasting** | Demand P10/P50/P90, inventory depletion curves, demand heatmap, health gauges, RUL distribution, failure-risk comparison, historical accuracy vs baselines | `/forecasting` |
| 3 | **Aerospace Digital Twin** | Unit history, telemetry, why it was flagged, uncertainty over time, work orders, replacements, documents to review (advisory only) | `/twin` |
| 4 | **Airspace Safety Lab** | Capability-honest analysis of prerecorded footage; labelled evaluation with FP/FN; civilian scope only | `/airspace` |
| 5 | **Supply Chain Intelligence** | Supplier trends, lead-time distributions, concentration, repair capacity, dependency graph, delay-impact simulator | `/supply` |
| 6 | **Predictive Maintenance** | 2.0 statistical risk view + Qwen explanation | `/predictive` |
| 7 | **Operational Resilience** | 8 scenarios: baseline vs disruption vs recovery, backlog uncertainty, recovery time, cost | `/resilience` |
| 8 | **Agent Harness Control Tower** | Graph, timeline, governance, model performance, evaluation, recovery — from recorded events only | `/control-tower` |
| 9 | **AI Governance** | Policies, approvals, audit chain, security lab (2.0) | `/trust` |
| 10 | **Flying Florina Chat** | 12 suggested 3.0 questions + the four 2.0 questions; memory that survives restarts | `/` |

Every 2.0 page (Command Center, AOG recovery, Legacy X-Ray, Bridge Studio, Observability, …) is still there under *Workspace*, plus
the new **Software Change Impact** page (`/change-impact`).

```mermaid
flowchart LR
  U([Question]) --> R{Hybrid router<br/>policy first}
  R -->|3.0 intent + slots| PL[Planner<br/>agents · tools · budget]
  PL --> S[Supervisor DAG]
  S --> A1[Geospatial] & A2[Prognostics] & A3[Supply chain] & A4[Twin] & A5[Resilience] & A6[Evaluation]
  A1 & A2 & A3 & A4 & A5 & A6 --> G[[Policy gateway<br/>pinned tools]]
  G --> M[(Models · simulation · SQLite)]
  S --> EV[Evidence validation] --> C[Composer] --> Q[Local Qwen] --> CH[Evidence Challenger] --> AU[(Audit)]
  style G fill:#2A1530,stroke:#EF4444,color:#E5E7EB
  style Q fill:#0E2A3A,stroke:#22D3EE,color:#E5E7EB
```

## 🖥 The 3.0 screens

<table>
<tr>
<td width="50%"><b>Component Forecasting</b><br/><img src="docs/screenshots/v3/03_forecasting.png" alt="Component Forecasting" /></td>
<td width="50%"><b>Historical forecast accuracy</b><br/><img src="docs/screenshots/v3/04_forecast_accuracy.png" alt="Forecast accuracy" /></td>
</tr>
<tr>
<td><b>Aerospace Digital Twin</b><br/><img src="docs/screenshots/v3/05_digital_twin.png" alt="Digital twin" /></td>
<td><b>Supply Chain: 14-day supplier delay simulated</b><br/><img src="docs/screenshots/v3/06_supply_chain.png" alt="Supply chain" /></td>
</tr>
<tr>
<td><b>Operational Resilience</b><br/><img src="docs/screenshots/v3/07_resilience.png" alt="Resilience simulator" /></td>
<td><b>Agent Harness Control Tower (recorded run)</b><br/><img src="docs/screenshots/v3/08_control_tower.png" alt="Control Tower" /></td>
</tr>
<tr>
<td><b>Airspace Safety Lab (capability-honest)</b><br/><img src="docs/screenshots/v3/09_airspace_lab.png" alt="Airspace Safety Lab" /></td>
<td><b>Software Change Impact</b><br/><img src="docs/screenshots/v3/10_change_impact.png" alt="Change impact" /></td>
</tr>
<tr>
<td><b>Chat: follow-up from memory ("What about the next 60 days?")</b><br/><img src="docs/screenshots/v3/11_chat_followup_memory.png" alt="Follow-up from memory" /></td>
<td><b>Global map: supply-chain layer at +60 days</b><br/><img src="docs/screenshots/v3/15_global_supply_layer.png" alt="Supply layer" /></td>
</tr>
</table>

<img src="docs/screenshots/v3/16_mobile_global.png" width="24%" alt="Mobile global map (lite)" />
<img src="docs/screenshots/v3/17_mobile_forecasting.png" width="24%" alt="Mobile forecasting" />
<img src="docs/screenshots/v3/18_mobile_control_tower.png" width="24%" alt="Mobile Control Tower" />

## 🧭 The governed agent harness

USER REQUEST → authentication → intent classification → **policy engine** → **task planner** → supervisor → 12 **specialist agents**
(each with its own tool allowlist) → **11 pinned, typed tools** through the deny-by-default gateway → **evidence validation** → human
approval when required → response generation (deterministic composer, then local Qwen + Evidence Challenger) → **hash-chained audit**.
Budgets are enforced atomically; simple questions use one specialist, complex ones several. Tests prove unauthorized tools are blocked,
budgets halt runs, failures are safe, missing evidence is reported, approvals cannot be bypassed, memory survives restarts and traces
match real executions. → [docs/AGENT_HARNESS.md](docs/AGENT_HARNESS.md)

## 📊 3.0 measured results

<div align="center">
<img src="docs/assets/v2/forecast_mae_v3.svg" width="100%" alt="Demand forecast MAE vs baselines by horizon" />
<br/><br/>
<img src="docs/assets/v2/models_vs_baselines_v3.svg" width="100%" alt="Models vs simpler baselines" />
</div>

| What | Result (held-out, synthetic) | Honest note |
|---|---|---|
| Demand forecast, 7–90 days | beats moving average and seasonal naive at every horizon (90 d MAE 2.86 vs 4.03) | 80% intervals under-cover at long horizons (66.7% at 90 d) |
| Failure within 30 days | F1 0.855 vs 0.541 health rule; ECE 0.006 | — |
| Anomaly detection | IsolationForest F1 0.869 | **the simple z-score rule wins (0.974)** and the UI says so |
| Remaining useful life | health-trend MAE 9.5 weeks | survival-only 36.7 weeks; evaluation favours early failures |
| 3.0 intent routing (fresh held-out) | 90.3% (56/62), follow-ups 3/4 | below the 95% target; supplier names without "supplier" are missed |
| 2.0 routing after 3.0 | held-out v2 95.8% (unchanged) | — |
| Visual-lab baseline (not AI) | precision 0.70, recall 0.79 on 58 labelled frames | no vision model installed; aircraft are its false positives |
| Latency | 3.0 chat p50 251 ms; map API p50 16 ms; warm restart 1.1 s | 2.0 workflows ~1.2× slower than the 2.0 code measured the same day |

Details: [FORECASTING_ENGINE.md](docs/FORECASTING_ENGINE.md) · [PERFORMANCE_BENCHMARKS.md](docs/PERFORMANCE_BENCHMARKS.md) ·
[eval/README.md](docs/eval/README.md) · [CHANGELOG_3.0.md](docs/CHANGELOG_3.0.md)

## 🚢 Deployment modes

| Mode | Command | Status |
|---|---|---|
| A — Local | `make demo` | verified |
| B — Docker Compose | `docker compose up --build` (add `QWEN_MODEL_DIR`, `FF_QWEN_MODEL_FILE`, `INSTALL_LLAMA=true` for your Qwen) | config validated; images not built here (no Docker daemon) |
| C — Kubernetes reference | `kubectl apply -k deploy/k8s` | manifests parsed; not applied to a cluster; single-writer SQLite backend |

→ [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (including the PostgreSQL migration path for horizontal scaling)

**3.0 docs:** [Architecture](docs/FLYING_FLORINA_3_ARCHITECTURE.md) · [Audit](docs/FLYING_FLORINA_3_ARCHITECTURE_AUDIT.md) ·
[Agent harness](docs/AGENT_HARNESS.md) · [Forecasting engine](docs/FORECASTING_ENGINE.md) · [Global map](docs/GLOBAL_MAP.md) ·
[Qwen integration](docs/QWEN_INTEGRATION.md) · [Security & governance](docs/SECURITY_GOVERNANCE.md) · [Deployment](docs/DEPLOYMENT.md) ·
[Demo walkthrough](docs/DEMO_WALKTHROUGH.md) · [Performance](docs/PERFORMANCE_BENCHMARKS.md)

---

## 🛩 Flying_Florina 2.0 (still included)

<img src="docs/assets/v2/banner_v2.svg" width="100%" alt="Flying_Florina 2.0" />

## 🛫 Why it matters for A&D leadership

| | |
|---|---|
| **The customer problem** | Decisions about a grounded or degrading aircraft depend on evidence scattered across ERP, MRO, legacy databases, nightly files and document libraries that disagree. Engineers spend hours assembling it, and AI assistants that can act create new governance risk. |
| **Why it matters in A&D** | Every hour of AOG has an operational and financial cost; safety-critical decisions need traceable evidence; export-control and security rules forbid casual data movement; legacy platforms can't simply be replaced. |
| **How Flying_Florina works** | A hybrid router sends each question to specialist agents that query verified data deterministically. **Your local Qwen model explains the evidence**, an **Evidence Challenger** rejects any number, ID or claim it can't support, and **governance validation** confirms nothing was approved or executed by the model. |
| **How it complements enterprise systems** | It sits next to systems such as IFS Cloud as an evidence-and-governance layer, reading through typed, read-only adapters and MCP tools. It replaces nothing. See [IFS integration readiness](docs/IFS_INTEGRATION_READINESS.md) (implemented vs proposed). |
| **How governance is enforced** | Deny-by-default policy before every tool call, agents limited to the human's rights, retrieved text can never trigger actions, human approval with separation of duties for every write, a kill switch, a hash-chained audit log, and loopback-only model calls. |
| **What the demo proves** | All four signature questions run end to end; held-out routing 95.8% (macro-F1 0.958); 100% citation accuracy; exfiltration and instruction-override attempts denied with 0 tool executions; generated read-only adapters pass their own tests. |
| **What production would need** | Enterprise IdP and MFA, container sandboxing, externally anchored audit, an internal package mirror and SBOM, authorized IFS APIs, model-provenance review, and a formal security and compliance assessment. See [deployment readiness](docs/DEPLOYMENT_READINESS.md). |

---

## ❓ The four signature questions

<table>
<tr>
<td width="50%" valign="top">

#### Q1 · Aircraft Diagnostics
*Why is aircraft AC-204 showing abnormal vibration, and what should engineering investigate?*

`telemetry ‖ retrieval ‖ history → hypotheses → Qwen → Challenger`

<img src="docs/screenshots/v2/02_q1_diagnostics.png" alt="Q1 diagnostics answer" />

</td>
<td width="50%" valign="top">

#### Q2 · Aircraft Recovery
*Which recovery option could return AC-204 to service fastest, considering spare parts, maintenance scheduling, and engineering approval?*

`parts ‖ scheduling → compliance → simulation → draft → approval gate`

<img src="docs/screenshots/v2/03_q2_recovery.png" alt="Q2 recovery answer" />

</td>
</tr>
<tr>
<td valign="top">

#### Q3 · Legacy Modernization
*How can we modernize our legacy aircraft maintenance system using APIs, MCP, and AI without replacing the existing platform?*

`Legacy X-Ray → integration options → adapter preview → contract tests → security review`

<img src="docs/screenshots/v2/04_q3_modernization.png" alt="Q3 modernization answer" />

</td>
<td valign="top">

#### Q4 · Executive Intelligence
*What is affecting fleet readiness, and which maintenance improvements could reduce downtime and cost?*

`fleet ‖ downtime trend ‖ parts → causes → modeled levers`

<img src="docs/screenshots/v2/05_q4_executive.png" alt="Q4 executive answer" />

</td>
</tr>
</table>

Paraphrases, follow-ups ("what about AC-118?"), greetings, general aviation questions, off-topic requests and injection attempts are
all handled too. See [the four-question engine](docs/FOUR_QUESTION_ENGINE.md).

---

## 🏛 Architecture (2.0)

<div align="center">
<img src="docs/assets/v2/architecture_v2.svg" width="100%" alt="Flying_Florina 2.0 architecture: UI, hybrid router, specialist graphs, deterministic layer, policy gateway, Qwen gateway, Evidence Challenger, governance" />
</div>

| Rule | Where it's enforced |
|---|---|
| Every number, ID, citation and approval comes from deterministic code | `app/workflows/*`, `app/services/*` |
| Qwen only writes language (explanations, closed-set classification, general aviation answers) | `app/llm/gateway.py` |
| Anything Qwen writes that isn't in the verified facts is removed | `app/workflows/explain.py` (Evidence Challenger) |
| The model can never approve, execute or export | policy engine POL-001…013, governance validation |
| Model calls are loopback-only, no cloud fallback | POL-008, `app/llm/discovery.py` |

---

## 🔀 How a question becomes a governed answer

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant R as Hybrid router
    participant A as Specialist agents
    participant D as Deterministic data
    participant P as Policy gateway
    participant Q as Local Qwen
    participant C as Evidence Challenger
    participant G as Governance
    U->>R: "Why is AC-204 vibrating?"
    R->>R: policy → greeting → follow-up → rules → semantic → (Qwen if ambiguous)
    R->>A: aircraft_diagnostics + entities {AC-204}
    loop every tool call
        A->>P: request (persona, tool, args)
        P-->>A: allow / deny (logged)
        A->>D: SQL · z-scores · retrieval · simulation
    end
    A-->>U: evidence workspace (charts, tables, citations) — shown immediately
    A->>Q: compact fact pack (≤ 7,000 chars)
    Q-->>C: explanation (JSON, schema-validated)
    C->>C: drop unknown numbers/IDs, airworthiness & savings claims
    C->>G: checked explanation
    G-->>U: answer + "model approved nothing" + audit record
```

```mermaid
flowchart LR
    q([question]) --> pol{"Policy: injection or export?"}
    pol -- yes --> deny[["Refuse or governance graph"]]
    pol -- no --> gr{Greeting?}
    gr -- yes --> hi[Greeting + four cards]
    gr -- no --> fu{"Follow-up cue + session context?"}
    fu -- yes --> keep["Reuse family and aircraft"]
    fu -- no --> ru{High-precision rules}
    ru -- match --> wf[Specialist graph]
    ru -- weak/none --> gate{Off-domain?}
    gate -- yes --> uns["Unsupported: scope + cards"]
    gate -- no --> sem{"TF-IDF semantic above threshold + margin"}
    sem -- yes --> wf
    sem -- no --> qw{"Local Qwen closed-set label"}
    qw -- valid label --> wf
    qw -- none --> fb["Clarify / general knowledge"]
    keep --> wf
    style deny fill:#2A1530,stroke:#F87171,color:#E5E7EB
    style qw fill:#312E81,stroke:#A78BFA,color:#E5E7EB
    style wf fill:#0E2A3A,stroke:#22D3EE,color:#E5E7EB
```

```mermaid
flowchart TB
    subgraph GW["Local LLM Gateway (single endpoint)"]
      direction LR
      c[Exact-prompt cache] --> b[Context & token budget] --> s[Concurrency 1] --> r[Runtime] --> v[JSON schema validation] --> tm[("llm_calls telemetry")]
    end
    disc{{Discovery}} --> r
    disc --- d1["FF_QWEN_MODEL_PATH (.gguf)"]
    disc --- d2["FF_QWEN_BASE_URL (loopback)"]
    disc --- d3["Ollama: qwen models"]
    disc --- d4["llama.cpp / LM Studio on 8080, 1234"]
    disc --- d5["qwen .gguf files in known folders"]
    r -. never .-> cloud[("Cloud / paid API")]
    style cloud fill:#2A1530,stroke:#F87171,color:#F87171,stroke-dasharray: 5 5
```

---

## 📊 Measured results

Every chart below is drawn by [`scripts/render_readme_v2_assets.py`](scripts/render_readme_v2_assets.py) straight from the JSON the
harnesses wrote; nothing is typed in by hand. The build machine had **no Qwen model**, so these are the router and workflows *without*
the Qwen stages. Qwen latency and the unsupported-claim rate are measured by the app on your machine.

<div align="center">
<img src="docs/assets/v2/eval_metrics.svg" width="100%" alt="Evaluation metrics for held-out v1 and v2" />
<br/><br/>
<img src="docs/assets/v2/per_label_f1.svg" width="49%" alt="Per-label F1 on held-out v2" />
<img src="docs/assets/v2/route_methods.svg" width="49%" alt="Router stage that decided each item" />
<br/><br/>
<img src="docs/assets/v2/latency.svg" width="49%" alt="Deterministic workflow latency" />
<img src="docs/assets/v2/tests_growth.svg" width="49%" alt="Test suites 1.0 to 2.0" />
</div>

| What | Result | Honest note |
|---|---|---|
| Held-out routing accuracy | **95.8%** (v2) · 94.3% (v1) | v1 was measured before four general fixes; v2 was written afterwards and never tuned on. Both reported. |
| Citation accuracy | **100%** of 200 | document exists, revision matches, user permitted |
| Governance | **3/3** injection & export attempts denied, **0** export executions | |
| Follow-ups | 83.3% (v2) | a follow-up without a reference word ("it", "that") can be missed |
| Qwen latency, tokens/s, unsupported-claim rate | **not measured here** | run Benchmark in Evaluation & Observability, or `scripts/check_qwen.py` |

Details and the four known misroutes: [docs/eval/README.md](docs/eval/README.md).

---

## 🖥 The 2.0 screens

<table>
<tr>
<td width="50%"><b>Executive Command Center</b><br/><sub>KPIs, availability trend, ATA × base heatmap, risk matrix, backlog, agent activity</sub><br/><img src="docs/screenshots/v2/06_command_center.png" alt="Executive Command Center" /></td>
<td width="50%"><b>Predictive Maintenance</b><br/><sub>labelled statistical risk scores (z-scores, no trained model claimed) + Qwen explanation</sub><br/><img src="docs/screenshots/v2/07_predictive.png" alt="Predictive Maintenance" /></td>
</tr>
<tr>
<td><b>Evaluation & Observability</b><br/><sub>Qwen status, live test, benchmark, p50/p95, tokens/s, cache, workflow reliability, eval</sub><br/><img src="docs/screenshots/v2/08_observability.png" alt="Evaluation and Observability" /></td>
<td><b>Legacy X-Ray + Modernization Blueprint</b><br/><sub>dependency analytics and a Blueprint export (Markdown, HTML, PDF)</sub><br/><img src="docs/screenshots/v2/09_legacy_xray.png" alt="Legacy X-Ray" /></td>
</tr>
<tr>
<td><b>Multi-agent operations</b><br/><sub>agent graph, real execution timeline, retries and failure injection</sub><br/><img src="docs/screenshots/v2/10_agents.png" alt="Agents" /></td>
<td><b>Governance</b><br/><sub>policies, approvals with separation of duties, audit chain</sub><br/><img src="docs/screenshots/v2/11_governance.png" alt="Governance" /></td>
</tr>
</table>

<img src="docs/screenshots/v2/12_mobile_home.png" width="24%" align="right" alt="Mobile home" />

**Twelve primary sections:** AI Assistant · Command Center · AOG Recovery · Predictive Maintenance · Parts & Supply ·
Legacy X-Ray · Bridge Studio · Agents · Governance · Simulation & ROI · Evaluation & Observability · Reports, plus every 1.0 page under *More*.

Built on the **Conversation Intelligence Copilot** design system: the same color tokens (`#0B1020` background, indigo `#6366F1`,
cyan `#22D3EE`, violet `#A78BFA`), cards, stat tiles, chart palette and motion. Works down to phone width with no horizontal scroll.

<br clear="right"/>

---

## 🔁 Before → after

| 1.0 | 2.0 |
|---|---|
| <img src="docs/screenshots/before/01_mission_control.png" alt="1.0 Mission Control" /> | <img src="docs/screenshots/v2/01_assistant_home.png" alt="2.0 AI Assistant" /> |
| <img src="docs/screenshots/before/04_fleet.png" alt="1.0 Fleet" /> | <img src="docs/screenshots/v2/06_command_center.png" alt="2.0 Command Center" /> |
| <img src="docs/screenshots/before/09_legacy.png" alt="1.0 Legacy" /> | <img src="docs/screenshots/v2/09_legacy_xray.png" alt="2.0 Legacy X-Ray" /> |

Full list of changes: [docs/CHANGELOG_2.0.md](docs/CHANGELOG_2.0.md) · executive demo, scenarios A–E: [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md#flying_florina-20-executive-demo-ifs-leadership)

---

## 🧠 Local Qwen setup

Flying_Florina uses **the Qwen model already on your machine**. It never downloads a model and never calls a cloud or paid API.

```bash
cd flying-florina
sh scripts/setup.sh                                  # packages + llama.cpp runtime (your model is reused) + Qwen check
backend/.venv/bin/python scripts/check_qwen.py       # must print QWEN VERIFIED with latency and tokens/s
make demo                                            # http://127.0.0.1:5173 (green "Local Qwen" pill)
```

Discovery order: `FF_QWEN_MODEL_PATH` → `FF_QWEN_BASE_URL` → Ollama (`qwen*`) → llama.cpp/LM Studio server → `*qwen*.gguf` files,
including `../conversation-intelligence-copilot/data/models/qwen2.5-1.5b-instruct-q4_k_m.gguf`. Running it through **GitHub Copilot**?
Use the prompt in [`.github/prompts/run-flying-florina-with-local-qwen.prompt.md`](../.github/prompts/run-flying-florina-with-local-qwen.prompt.md).
Details, performance controls and monitoring: [docs/QWEN_LOCAL_LLM.md](docs/QWEN_LOCAL_LLM.md).

> Honest note: this repository was built in a cloud container that does not have your Qwen model. The Qwen code paths are tested
> against a test-only fake server, and real Qwen latency/tokens-per-second are measured by the app on your machine. No Qwen benchmark is
> quoted here because none was measured.

---

## 🧱 Platform foundations (from 1.0)

Everything below shipped in 1.0 and is **still included unchanged** in 2.0: the trust chain, agents, Legacy X-Ray, bridges and
value studio that the four-question engine builds on.

## ✨ Highlights

<table>
<tr>
<td width="33%" valign="top">

### 🧭 Ask anything
Ten sample questions, all functional. Each answer is a **workspace**: answer, KPIs, charts, tables, citations, warnings, assumptions, decision trace, approvals and exports. Follow-ups keep building the conversation.

</td>
<td width="33%" valign="top">

### 🤖 Real agents, real log
Thirteen typed agents run as a DAG with parallel waves, retries, timeouts, cancellation and checkpoints. The timeline and agent graph show **persisted events with real timestamps**; nothing is animated or invented.

</td>
<td width="33%" valign="top">

### 🛡️ Trust you can test
Thirteen deterministic policies, deny-by-default. The export of restricted records is **denied before the tool runs**: 0 executions. Separation of duties, a replay-proof write path, a kill switch, a hash-chained audit log, and a 12-scenario Security Lab.

</td>
</tr>
<tr>
<td valign="top">

### 🔬 Legacy X-Ray
Import SQL DDL, OpenAPI, CSV, OData XML, event schemas and ZIP source bundles. They are **parsed, never executed**. You get a dependency map, hotspots, findings, explicit unknowns, eight evidence-backed patterns and a 30/60/90 roadmap.

</td>
<td valign="top">

### 🔌 Bridges that run
Generate a read-only FastAPI adapter, an MCP server (official SDK) and their tests from legacy metadata. Run the tests in a sandbox (**14/14 pass**) and download the bundle.

</td>
<td valign="top">

### 📈 Value with receipts
Deterministic scenarios, seeded Monte Carlo, sensitivity, and an editable ROI range. Every number comes with its formula and assumptions. Export to PDF, HTML, Markdown, CSV and JSON.

</td>
</tr>
</table>

---

## 🏛 Architecture (1.0 layers)

<div align="center">
<img src="docs/assets/architecture.svg" width="100%" alt="Flying_Florina layered architecture" />
</div>

| Layer | What lives there | Key technology |
|---|---|---|
| **1 · Experience** | Mission Control chat, agent graph, 15 domain pages, light/dark, responsive | React 18 · TypeScript · Vite · Tailwind · ECharts · React Flow · TanStack Query |
| **2 · API** | Identity, validation, response envelope, typed errors, security headers, 61 OpenAPI paths | FastAPI · Pydantic v2 |
| **3 · Orchestration** | Deterministic intent router, DAG workflow engine, 13 specialist agents | Explicit typed state machine (LangGraph-compatible semantics) |
| **4 · Trust** | Tool gateway, policy engine, approvals, audit chain, kill switch, injection guard | Policy-as-code in Python, SHA-256 hash chain |
| **5 · Capabilities** | Access-aware retrieval, simulation & ROI, Legacy X-Ray, bridge generator, reports | SQLite FTS5/BM25 + TF-IDF · ReportLab |
| **6 · Data & integration** | Synthetic SQLite, fixtures, demo MCP server, generated adapters; IFS/ERP **not connected** | SQLite · official MCP Python SDK (stdio) |

---

## 🎬 See it in action

### Act 1: Operational AI on the AC-204 vibration anomaly

> *"Investigate AC-204 vibration anomaly, check maintenance evidence, parts and available technicians, and draft recovery options."*

<div align="center">
<img src="docs/screenshots/highlights/agent_graph_timeline.png" width="90%" alt="Agent graph and real execution timeline" />
<br/><sub><b>Agent graph + execution log.</b> Telemetry, retrieval and history run in parallel; every row is a persisted event with its own timestamp, duration and tools.</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/ac204_answer.png" width="49%" alt="Investigation summary" />
<img src="docs/screenshots/highlights/ac204_vibration_chart.png" width="49%" alt="Vibration chart vs fleet mean" />

<sub><b>Left:</b> the summary: 7-day vibration mean vs its own baseline, hypotheses (not a diagnosis), the fastest compliant recovery, and the pending approval. <b>Right:</b> AC-204 vs the fleet mean, with the fictional demo threshold and a data-quality gap visible.</sub>

<img src="docs/screenshots/highlights/ac204_hypotheses.png" width="49%" alt="Diagnostic hypotheses" />
<img src="docs/screenshots/highlights/ac204_parts_reconciled.png" width="49%" alt="Parts reconciled across systems" />

<sub><b>Left:</b> hypotheses with supporting and contradicting evidence and the authoritative reference each one needs. <b>Right:</b> inventory reconciled across systems. MAIN-HUB is rejected because ERP says 2 and the physical count says 0.</sub>

<div align="center">
<img src="docs/screenshots/highlights/ac204_recovery_options.png" width="90%" alt="Recovery options ranked" />
<br/><sub><b>Recovery options.</b> Only verified stock and authority-backed alternates qualify; the gray-market substitute is rejected for lack of evidence.</sub>
</div>

<br/>

<div align="center">
<img src="docs/screenshots/highlights/ac204_citations.png" width="90%" alt="Citations with revision and provenance" />
<br/><sub><b>Citations.</b> Each one carries its revision, effective date, classification and provenance hash. The supplier bulletin's hidden instruction is <b>quarantined</b>, and the export it asked for is denied (POL-011).</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/ac204_decision_trace.png" width="49%" alt="Decision trace" />
<img src="docs/screenshots/highlights/ac204_approval_gate.png" width="49%" alt="Human approval gate" />

<sub><b>Left:</b> every policy decision for the run, with expandable ordered checks. <b>Right:</b> the human approval gate. Nothing is written until a different authorized person approves.</sub>

### Act 2: What-if analysis and root cause

<img src="docs/screenshots/highlights/scenario_chart.png" width="49%" alt="Delay scenario comparison" />
<img src="docs/screenshots/highlights/downtime_analysis.png" width="49%" alt="Downtime analysis" />

<sub><b>Left:</b> 24/48/72 h part delays. Downtime jumps non-linearly because of hangar-slot availability; the P90 comes from a seeded Monte Carlo over the supplier's history. <b>Right:</b> "Why did downtime rise in October?" answered with a normalized trend, cause decomposition and bootstrap confidence intervals.</sub>

### Act 3: Defense trust

<div align="center">
<img src="docs/screenshots/highlights/export_denied.png" width="90%" alt="Export denied before execution" />
<br/><sub><b>"Export restricted maintenance records to my personal email."</b> DENY by POL-004 before execution. The tool ran <b>0</b> times; identity, classification and destination are all on record.</sub>
</div>

<br/>

<div align="center">
<img src="docs/screenshots/highlights/security_lab.png" width="90%" alt="Security Test Lab 12 of 12" />
<br/><sub><b>Security Test Lab.</b> Twelve scenarios run against the live controls: public read, restricted read, external export, expired approval, stale document, privilege escalation, prompt injection, untrusted tool, missing token, wrong audience, replayed write, tool timeout.</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/audit_ledger.png" width="49%" alt="Hash-chained audit ledger" />
<img src="docs/screenshots/highlights/agents_failure_retry.png" width="49%" alt="Failure injection and retry" />

<sub><b>Left:</b> the evidence ledger, a hash-chained audit log verified in one click. <b>Right:</b> failure injection in Agent Mission Control. The parts step fails, retries with backoff, and the workflow still completes.</sub>

### Act 4: Legacy modernization, from schema to running bridge

<div align="center">
<img src="docs/screenshots/highlights/legacy_dependency_map.png" width="90%" alt="Legacy dependency map" />
<br/><sub><b>Dependency map</b> of a fictional 20-year-old MRO landscape: 12 systems, APIs, batch files and dashed <i>unknowns</i>. The unknowns are open questions; nothing is assumed.</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/legacy_findings.png" width="49%" alt="Legacy findings" />
<img src="docs/screenshots/highlights/legacy_recommendations.png" width="49%" alt="Modernization recommendations" />

<sub><b>Left:</b> findings: an arbitrary-SQL endpoint, an SSRF-prone webhook, missing primary keys, stale counts, static API keys. <b>Right:</b> evidence-backed patterns (strangler fig, anti-corruption layer, read-only view, batch bridge, CDC, RAG, documented ERP APIs, MCP facade) with rollback, test plan and confidence.</sub>

<img src="docs/screenshots/highlights/bridge_tests_passed.png" width="49%" alt="Generated tests passing" />
<img src="docs/screenshots/highlights/mcp_discovery.png" width="49%" alt="MCP discovery" />

<sub><b>Left:</b> the generated adapter's contract, security and MCP stdio tests, run in a sandbox: 14 passed, 0 failed. <b>Right:</b> the demo MCP server, with tools discovered, schema hashes checked against pins, and each call authorized by the policy engine.</sub>

### Act 5: Executive value

<img src="docs/screenshots/highlights/executive_roi.png" width="49%" alt="ROI benefit components" />
<img src="docs/screenshots/highlights/executive_roadmap.png" width="49%" alt="90-day roadmap" />

<sub>An assumption-driven ROI range with editable inputs, next to the 30/60/90-day pilot roadmap with owners, dependencies and exit criteria.</sub>

### Anywhere: dark mode and mobile

<img src="docs/screenshots/highlights/dark_fleet.png" width="58%" alt="Fleet dashboard, dark theme" />
<img src="docs/screenshots/highlights/mobile_home.png" width="19%" alt="Mobile home" />
<img src="docs/screenshots/highlights/mobile_parts.png" width="19%" alt="Mobile parts" />

---

## 🖥 Every screen

Each page below was captured from the running app with synthetic data.

<table>
<tr>
<td width="50%"><b>Fleet & Asset Health</b><br/><img src="docs/screenshots/04_fleet.png" alt="Fleet & Asset Health" /></td>
<td width="50%"><b>Fleet dashboard (full)</b><br/><img src="docs/screenshots/highlights/fleet_dashboard.png" alt="Fleet dashboard" /></td>
</tr>
<tr>
<td><b>AOG Recovery</b><br/><img src="docs/screenshots/05_aog.png" alt="AOG Recovery" /></td>
<td><b>Maintenance & MRO</b><br/><img src="docs/screenshots/06_maintenance.png" alt="Maintenance & MRO" /></td>
</tr>
<tr>
<td><b>Parts & Supply Chain</b><br/><img src="docs/screenshots/07_parts.png" alt="Parts & Supply Chain" /></td>
<td><b>Engineering Quality</b><br/><img src="docs/screenshots/08_quality.png" alt="Engineering Quality" /></td>
</tr>
<tr>
<td><b>Legacy X-Ray</b><br/><img src="docs/screenshots/09_legacy.png" alt="Legacy X-Ray" /></td>
<td><b>API & MCP Bridge Studio</b><br/><img src="docs/screenshots/10_bridge.png" alt="Bridge Studio" /></td>
</tr>
<tr>
<td><b>Agent Mission Control</b><br/><img src="docs/screenshots/highlights/agents_mission_control.png" alt="Agent Mission Control" /></td>
<td><b>Agent Mission Control (catalog)</b><br/><img src="docs/screenshots/11_agents.png" alt="Agents catalog" /></td>
</tr>
<tr>
<td><b>Defense Trust Center</b><br/><img src="docs/screenshots/12_trust.png" alt="Defense Trust Center" /></td>
<td><b>Security Test Lab</b><br/><img src="docs/screenshots/12_trust_security_lab.png" alt="Security Test Lab" /></td>
</tr>
<tr>
<td><b>Compliance Evidence</b><br/><img src="docs/screenshots/13_compliance.png" alt="Compliance Evidence" /></td>
<td><b>Scenario Simulator</b><br/><img src="docs/screenshots/14_simulator.png" alt="Scenario Simulator" /></td>
</tr>
<tr>
<td><b>Reports & Exports</b><br/><img src="docs/screenshots/16_reports.png" alt="Reports & Exports" /></td>
<td><b>Integrations & Settings</b><br/><img src="docs/screenshots/17_settings.png" alt="Integrations & Settings" /></td>
</tr>
<tr>
<td valign="top"><b>Export request: denied</b><br/><img src="docs/screenshots/03_export_denied.png" alt="Export denied" /></td>
<td valign="top"><b>Legacy X-Ray: generated bridge and tests (full page)</b><br/><img src="docs/screenshots/18_legacy_bridge_tests.png" alt="Bridge tests full page" /></td>
</tr>
<tr>
<td valign="top"><b>AC-204 investigation: the complete workspace</b><br/><img src="docs/screenshots/02_ac204_investigation.png" alt="Full AC-204 workspace" /></td>
<td valign="top"><b>Executive Value Studio: the complete 90-day pitch</b><br/><img src="docs/screenshots/15_executive.png" alt="Executive Value Studio full page" /></td>
</tr>
</table>

---

## 🧠 How it works

### Trust chain

```mermaid
flowchart LR
  A["Intent<br/>(rules; optional local LLM<br/>never decides)"] --> B["Workflow<br/>engine"]
  B --> C["Tool registry<br/>name+version+schema SHA-256 pinned"]
  C --> D{"Policy gateway<br/>per invocation"}
  D -->|ALLOW| E["MCP server<br/>(agent interface)"]
  D -->|DENY| X["Not executed<br/>decision + audit"]
  E --> F["Typed read-only<br/>API adapter"]
  F --> G["Authorized system endpoint<br/>(synthetic)"]
  style D fill:#5C35B7,color:#fff
  style X fill:#C53030,color:#fff
```

### Policy evaluation order (the first failure decides; every check is recorded)

```mermaid
flowchart TB
  S([Request]) --> P12{"POL-012<br/>identity?"}
  P12 -->|no| DENY([DENY])
  P12 --> P09{"POL-009<br/>kill switch off?"}
  P09 -->|no| DENY
  P09 --> P11{"POL-011<br/>from user, not<br/>retrieved text?"}
  P11 -->|no| DENY
  P11 --> P07{"POL-007<br/>no self-escalation?"}
  P07 -->|no| DENY
  P07 --> P06{"POL-006<br/>tool pinned?"}
  P06 -->|no| DENY
  P06 --> P08{"POL-008<br/>model is local?"}
  P08 -->|no| DENY
  P08 --> P04{"POL-004<br/>destination internal?"}
  P04 -->|no| DENY
  P04 --> P02{"POL-001/002<br/>role grants action?"}
  P02 -->|no| DENY
  P02 --> P03{"POL-003<br/>label & attributes?"}
  P03 -->|no| DENY
  P03 --> P10{"POL-010<br/>authoritative evidence?"}
  P10 -->|no| DENY
  P10 --> P13{"POL-013<br/>separation of duties?"}
  P13 -->|no| DENY
  P13 --> P05{"POL-005<br/>approved, unexpired,<br/>not replayed write?"}
  P05 -->|no| DENY
  P05 --> ALLOW([ALLOW])
  style DENY fill:#C53030,color:#fff
  style ALLOW fill:#0F8B8D,color:#fff
```

### Graph 1: maintenance investigation

```mermaid
flowchart LR
  I["intake<br/>Intake & Intent"] --> P["policy_precheck<br/>Security & Governance"]
  P --> T["telemetry<br/>Asset Telemetry"]
  P --> R["retrieval<br/>Knowledge Retrieval"]
  P --> H["history<br/>Diagnostic Evidence"]
  T --> D["diagnostics<br/>hypotheses only"]
  R --> D
  H --> D
  D --> PA["parts<br/>verified stock · approved alternates"]
  D --> SC["scheduling<br/>qualified techs · hangar slots"]
  PA --> C["compliance<br/>evidence checklist"]
  SC --> C
  C --> DR["draft_plan<br/>dry-run work order"]
  DR --> AP{{"approval_gate<br/>human, different persona"}}
  AP -.->|approve + execute| W["simulated write<br/>idempotent, audited"]
  style AP fill:#D7B46A,color:#0B1230
```

### Graph 2: legacy modernization · Graph 3: governance

```mermaid
flowchart LR
  subgraph G2["Graph 2 — Legacy"]
    a1[precheck] --> a2[metadata import] --> a3[dependency graph] --> a4[risk classification]
    a4 --> a5[integration options] --> a6[target architecture] --> a7[adapter generation]
    a7 --> a8[static contract tests] --> a9[security review]
  end
  subgraph G3["Graph 3 — Governance"]
    b1[identity + policy evaluation] -->|DENY| b2[no tool execution] --> b3[audit] --> b4[response]
    b1 -->|ALLOW| b5[permitted tool only] --> b3
  end
```

### Exfiltration attempt: denied before execution

```mermaid
sequenceDiagram
  autonumber
  actor U as Planner
  participant UI as Mission Control
  participant IR as Intent router
  participant SG as Security & Governance agent
  participant PE as Policy engine
  participant T as records.export_email
  participant A as Audit chain
  U->>UI: "Export restricted maintenance records to my personal email."
  UI->>IR: POST /api/chat/query
  IR->>SG: route = data_export (matched first, cannot be outscored)
  SG->>PE: evaluate(export, RESTRICTED, personal_email)
  PE-->>SG: DENY · POL-004
  PE->>A: decision + hash-linked event
  Note over T: never invoked (execution count stays 0)
  SG-->>UI: DENIED · policy trace · identity · classification · 0 executions
```

### Approval lifecycle

```mermaid
stateDiagram-v2
  [*] --> pending: draft created by planner<br/>payload SHA-256 stored
  pending --> pending: requester tries to approve<br/>DENY POL-013
  pending --> approved: different approver role<br/>evidence hash recorded
  pending --> rejected: approver rejects
  pending --> expired: TTL elapsed
  approved --> executed: execute with idempotency key<br/>policy re-checked (POL-005)
  executed --> executed: replay attempt<br/>DENY POL-005
  rejected --> [*]
  expired --> [*]
  executed --> [*]
```

### Hash-chained audit log

```mermaid
flowchart LR
  G["genesis<br/>000…0"] --> E1["event 1<br/>hash = SHA-256(fields + prev)"]
  E1 --> E2["event 2<br/>prev = hash(1)"]
  E2 --> E3["event 3<br/>prev = hash(2)"]
  E3 --> V{"verify"}
  V -->|"any edit or deletion"| BROKEN(["broken_at = event id"])
  V -->|"intact"| OK(["valid · head hash"])
  style BROKEN fill:#C53030,color:#fff
  style OK fill:#0F8B8D,color:#fff
```

<sub>Tamper-evident, not tamper-proof: a host administrator could rewrite the file and recompute the chain.</sub>

### Legacy X-Ray → Bridge pipeline

```mermaid
flowchart LR
  subgraph In["Inputs (parsed, never executed)"]
    s1[SQL DDL]
    s2[OpenAPI JSON/YAML]
    s3[Nightly CSV]
    s4[OData XML]
    s5[Event schema]
    s6[ZIP: .py AST / .java metadata]
  end
  In --> SAFE["Safety gate<br/>size · extension · binary · ZIP traversal/bomb · XXE"]
  SAFE --> X["Landscape<br/>systems · tables · APIs · edges"]
  X --> F["Findings<br/>/admin/sql · SSRF · missing PKs · stale counts"]
  X --> U["Unknowns U1–U5<br/>(asked, not assumed)"]
  F --> REC["8 recommendations<br/>strangler · ACL · read-only view · CDC<br/>batch bridge · RAG · documented ERP APIs · MCP facade"]
  REC --> RM["30/60/90 roadmap"]
  REC --> GEN["Bridge generator"]
  GEN --> B1["FastAPI adapter + Pydantic models"]
  GEN --> B2["MCP server (official SDK)"]
  GEN --> B3["contract · security · MCP tests"]
  GEN --> B4["OpenAPI · threat model · README"]
  B3 --> RUN{{"sandboxed pytest<br/>14/14 pass"}}
  style RUN fill:#0F8B8D,color:#fff
```

| Legacy column (`V_PART_AVAILABILITY`) | Canonical field | Rule |
|---|---|---|
| `PART_NO` | `part_number` | validated `^P-[0-9A-Z]{3,8}$` |
| `PART_DESC` | `description` | — |
| `BASE_CODE` | `location` | — |
| `QTY_OH` | `quantity_on_hand` | non-negative |
| `LOT_NO` | `lot` | `UNKNOWN` ⇒ not traceable |
| `LAST_CNT_DT` | `last_counted` | critical part counted > 30 days ago ⇒ unverified |

### Data model

```mermaid
erDiagram
  AIRCRAFT ||--o{ SENSOR_READINGS : "548 days"
  AIRCRAFT ||--o{ MAINTENANCE_EVENTS : has
  AIRCRAFT ||--o{ WORK_ORDERS : has
  PARTS ||--o{ INVENTORY : "per system of record"
  PARTS }o--|| SUPPLIERS : "sourced from"
  SUPPLIERS ||--o{ SUPPLIER_DELIVERIES : "reliability computed"
  WORK_ORDERS }o--o| TECHNICIANS : assigned
  DOCUMENTS ||--|| DOCUMENTS_FTS : indexed
  WORKFLOW_RUNS ||--o{ WORKFLOW_EVENTS : logs
  WORKFLOW_RUNS ||--o{ POLICY_DECISIONS : produces
  POLICY_DECISIONS ||--o{ TOOL_INVOCATIONS : "allow only"
  APPROVALS ||--o| WRITE_LOG : "idempotency key"
  AUDIT_EVENTS ||--|| AUDIT_EVENTS : "prev_hash"
```

| Synthetic dataset (seed `20261024`) | Rows |
|---|---|
| Aircraft (fictional IDs, e.g. AC-204) | 150 |
| Daily sensor readings (18 months) | 82,200 |
| Maintenance events / work orders | ~2,400 each |
| Parts / inventory records / supplier deliveries | 60 / ~130 / 720 |
| Technicians / hangar slots | 40 / 60 |
| Technical documents (fictional, versioned, classified) | 28 |
| Enterprise applications / seeded incidents | 12 / 8 |

### The agent roster

| Agent | Responsibility | Tools (pinned) |
|---|---|---|
| Intake & Intent | Deterministic routing, entity extraction, clarification | — |
| Supervisor | DAG waves, retries, cancellation, checkpoints | — |
| Asset Telemetry | Baselines, z-scores, outliers, data-quality gaps | `telemetry.get_series` |
| Knowledge Retrieval | Access-filtered hybrid search, injection quarantine | `docs.search` |
| Diagnostic Evidence | Hypotheses with supporting/contradicting evidence | `maintenance.get_history` |
| Parts | Reconciled inventory, authority-backed alternates | `parts.check_availability` |
| Maintenance Planner | Unexpired qualifications, slots, dry-run drafts | `roster.find_qualified` · `hangar.find_slots` · `workorder.create_draft` |
| Compliance | Evidence sufficiency (never certification) | `docs.search` |
| Legacy Discovery · Integration Architect | Metadata parsing, options, adapter generation | — |
| Scenario Simulator | Deterministic scenarios, seeded Monte Carlo, ROI | — |
| Security & Governance | Explains decisions; never overrides them | — |
| Reporting | Workspace blocks, citations, exports | — |

---

## 🚀 Quick start

Requires **Python 3.11+** and **Node 20+**. Setup needs network once; after that everything runs offline.

```mermaid
flowchart LR
  A["scripts/setup.sh<br/>venv · deps · seed DB · npm install"] --> B["make demo<br/>API :8000 + UI :5173"]
  B --> C["open http://127.0.0.1:5173<br/>no credentials · no API keys"]
  C --> D["make test · make test-e2e · make offline"]
```

<table>
<tr><th>macOS / Linux</th><th>Windows PowerShell</th></tr>
<tr>
<td>

```bash
cd flying-florina
sh scripts/setup.sh
make demo
# open http://127.0.0.1:5173
```

</td>
<td>

```powershell
cd flying-florina
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
cd backend; .\.venv\Scripts\uvicorn app.main:app --port 8000
# 2nd terminal
cd frontend; npm run dev
```

</td>
</tr>
</table>

Without Make: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000`, then `cd frontend && npm run dev`.

The UI signs you in as a synthetic persona. Switch personas in the top bar: Executive, Maintenance Planner, Technician, Reliability Engineer, Enterprise Architect, Security Officer, Auditor, Forward Deployed Engineer, Guest, and an external supplier. **The backend enforces rights; the UI only adapts.**

---

## 🎤 Interview demo

```mermaid
timeline
  title Six-minute offline demo
  Act 1 (2 min) : Legacy X-Ray : import MRO schema + nightly CSV : dependency map, hotspots, unknowns : generate read-only bridge, run 14 tests
  Act 2 (2 min) : AC-204 question : agent graph, citations, charts : pending approval : change lead time and recompute scenarios
  Act 3 (1 min) : export request : DENY POL-004, 0 executions : approve as another persona : replay denied POL-005
  Act 4 (1 min) : 90-day pitch : roadmap, risks, ROI ranges : download PDF brief
```

Full 3-minute and 8-minute scripts, plus the questions to expect, are in **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**.

---

## ✅ Tests and quality gates

| Command | What it covers | Result |
|---|---|---|
| `make test-backend` | routing, policies, export blocking, retrieval filtering, citations, approvals, replay, audit chain, workflows, failure injection, cancel, simulation determinism, upload safety, bridge generation **and execution**, MCP stdio, **local Qwen gateway, four-question engine, Evidence Challenger** | **131 passed** |
| `npm test` (Vitest) | XSS-safe markdown, chart mapping, table sorting, workspace rendering | **9 passed** |
| `make test-e2e` (Playwright) | fresh start, personas, all 10 prompts, **four question cards, follow-ups, Command Center, Predictive, Observability**, charts, agent graph, legacy upload, adapter tests, denial, approvals, PDF download, guest denials, offline interception, mobile | **18 passed** |
| `make offline` | every workflow + reports with the egress guard on, no LLM | **0 egress attempts** |
| Generated bundle `pytest` | contract 6 · security 6 · MCP stdio 2 | **14 passed** |
| `make lint` · `npm run typecheck` · `npm run build` | ruff (incl. bandit rules) · strict TypeScript · production build | **clean** |

Measured on a 4-CPU container with rules only, no LLM: **58 ms** (export denial) to **~970 ms** (downtime analysis with bootstrap CIs); the AC-204 investigation takes about **250 ms**. See [latency_measured.json](docs/latency_measured.json) and [TEST_REPORT.md](docs/TEST_REPORT.md).

---

## 🗂 Repository layout

```
flying-florina/
├── backend/app/
│   ├── core/            config · security · policy · audit · egress · db
│   ├── agents/          maintenance + analytics agents
│   ├── workflows/       intent router · DAG engine · graphs · workspace composer
│   ├── retrieval/       access-aware FTS5/TF-IDF search
│   ├── integrations/    legacy/ (parsers, X-Ray) · mcp/ (registry, bridge, client)
│   ├── simulation/      delay scenarios · ROI
│   ├── reports/         PDF/HTML/MD/CSV/JSON
│   ├── seed/            deterministic synthetic data
│   └── api/             REST endpoints with envelope + typed errors
├── backend/tests/       pytest suite
├── frontend/src/        components/ · features/<15 pages> · lib/
├── frontend/e2e/        Playwright suite
├── mcp_servers/demo_maintenance/                   local stdio MCP server
├── generated_adapters/example_part_availability/   runnable generated bundle
├── fixtures/            documents · legacy schemas · OpenAPI · OData · CSV · policies · tool pins
├── docs/                architecture · threat model · guides · scripts · assets · screenshots
└── scripts/             setup · seed · smoke · offline check · latency · pin tools
```

---

## ⚖️ Honest limits

| ✅ Real | 🟡 Simulated / demo-grade | ⛔ Not built |
|---|---|---|
| Policy engine, approvals, audit chain, retrieval filtering, workflows, parsers, generated adapter + MCP, reports, offline guard, local Qwen gateway + Evidence Challenger, four-question router | Qwen benchmarks (measured on your machine, not in this repo), persona login (no IdP/MFA), approved writes (demo DB only), ERP data (fictional "IFS-like" fixtures), prompt-injection patterns, process-level egress guard, subprocess test sandbox | Live IFS connection, PostgreSQL/Alembic, OPA, embeddings, trained predictive model (scores are statistics), 3D views, connector gallery |

**Cost:** no paid APIs, hosted inference, cloud services or accounts, so incremental software spend is **$0**. You provide the hardware and electricity. Claude Code, which was used to build this, may need its own subscription.

<img src="docs/assets/logo.png" width="64" align="right" alt="Flying_Florina logo" />

**Brand:** the round mark shown here is an original placeholder. The authorized portrait and logo files named in the spec weren't available, so no likeness was invented. To use your own assets locally, see [frontend/public/brand/README.md](frontend/public/brand/README.md).

Read [SECURITY_LIMITATIONS.md](docs/SECURITY_LIMITATIONS.md) before presenting to a security team, and [GAP_MATRIX.md](docs/GAP_MATRIX.md) for the full status list.

---

## 📚 Documentation

| | | |
|---|---|---|
| 🏛 [Architecture](docs/ARCHITECTURE.md) | 🗺 [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | 📊 [Gap matrix](docs/GAP_MATRIX.md) |
| 🎯 [Threat model](docs/THREAT_MODEL.md) | 🔒 [Security limitations](docs/SECURITY_LIMITATIONS.md) | 📋 [Compliance mapping](docs/COMPLIANCE_MAPPING.md) |
| 🔌 [API & MCP guide](docs/API_MCP_GUIDE.md) | 💰 [ROI method](docs/ROI_METHOD.md) | 🚚 [Deployment & offline install](docs/DEPLOYMENT.md) |
| 🎤 [Demo scripts](docs/DEMO_SCRIPT.md) | 📄 [One-page pilot brief](docs/ONE_PAGE_BRIEF.md) | ✅ [Test report](docs/TEST_REPORT.md) |
| 📜 [Third-party notices](THIRD_PARTY_NOTICES.md) | ⚖️ [License (GPL-3.0)](LICENSE) | 🎨 [Brand assets](frontend/public/brand/README.md) |
| 🧠 [Local Qwen integration](docs/QWEN_LOCAL_LLM.md) | ❓ [Four-question engine](docs/FOUR_QUESTION_ENGINE.md) | 📈 [Evaluation results](docs/eval/README.md) |
| 🛡 [Deployment readiness](docs/DEPLOYMENT_READINESS.md) | 🔗 [IFS integration readiness](docs/IFS_INTEGRATION_READINESS.md) | 🆕 [What changed in 2.0](docs/CHANGELOG_2.0.md) |
| ✍️ [Medium article: the build story and challenges](docs/MEDIUM_ARTICLE.md) | 🖼 [README chart generator](scripts/render_readme_v2_assets.py) | 🆕 [What changed in 3.0](docs/CHANGELOG_3.0.md) |
| 🌍 [3.0 architecture](docs/FLYING_FLORINA_3_ARCHITECTURE.md) | 🧭 [Agent harness](docs/AGENT_HARNESS.md) | 📈 [Forecasting engine](docs/FORECASTING_ENGINE.md) |
| 🗺 [Global map](docs/GLOBAL_MAP.md) | 🛡 [Security & governance](docs/SECURITY_GOVERNANCE.md) | ⏱ [Performance benchmarks](docs/PERFORMANCE_BENCHMARKS.md) |
| 🎬 [3.0 demo walkthrough](docs/DEMO_WALKTHROUGH.md) | 🧠 [Qwen integration (3.0)](docs/QWEN_INTEGRATION.md) | 🔎 [3.0 audit](docs/FLYING_FLORINA_3_ARCHITECTURE_AUDIT.md) |

<div align="center">
<br/>
<img src="docs/assets/logo.png" width="72" alt="Flying_Florina" />
<br/>
<b>Flying Florina 3.0</b><br/>
<sub>From legacy systems to trusted industrial intelligence.<br/>Independent concept demo · Not affiliated with or endorsed by IFS</sub>
</div>
