# Local Qwen integration

Flying_Florina uses **your existing, locally downloaded Qwen model** as its only language model. It never downloads a model and has
no cloud, paid or external fallback.

```
Flying_Florina UI -> Agent Orchestrator -> Local LLM Gateway (app/llm/gateway.py) -> your Qwen model
                                             |  POL-008 loopback-only, cache, concurrency 1, context & token budget,
                                             |  timeout, JSON-schema validation, telemetry (llm_calls table)
                                             v
                         Evidence Challenger -> Governance validation -> response
```

## 1. Discovery (app/llm/discovery.py)

On startup (and from **Evaluation & Observability → Re-detect Qwen**) the backend looks, in order, for:

| # | Where | Runtime used |
|---|---|---|
| 1 | `FF_QWEN_MODEL_PATH` (a `.gguf` file) | in-process llama.cpp (`llama-cpp-python`) |
| 2 | `FF_QWEN_BASE_URL` (loopback only) | Ollama or OpenAI-compatible server |
| 3 | Ollama at `LLM_URL` (default `http://127.0.0.1:11434`) with a model named `*qwen*` | Ollama HTTP API |
| 4 | OpenAI-compatible server on `127.0.0.1:8080` or `:1234` (llama.cpp server, LM Studio) advertising a qwen model | `/v1/chat/completions` |
| 5 | `*qwen*.gguf` in `../conversation-intelligence-copilot/data/models/`, `flying-florina/models/`, `~/models`, `~/.cache/huggingface/hub`, `~/.cache/lm-studio/models`, `~/.lmstudio/models`, `~/llama.cpp/models`, plus `FF_QWEN_SEARCH_DIRS` | in-process llama.cpp |

The Conversation Intelligence Copilot stored **Qwen2.5-1.5B-Instruct, Q4_K_M** (`qwen2.5-1.5b-instruct-q4_k_m.gguf`) in its
`data/models/` folder, which is searched first among files. Discovery reports model name, quantization, path or URL, size,
parameter count (Ollama), whether `llama-cpp-python` is installed, and whether GPU offload is supported.

`LLM_ENABLED=on` (default) makes Qwen **required**: if it cannot be reached, the header pill turns red and Evaluation &
Observability shows exactly what was searched and how to fix it. `auto` uses Qwen when found; `off` never calls a model.

## 2. Verify on your machine

```bash
cd flying-florina
sh scripts/setup.sh                                  # installs llama-cpp-python (runtime only) and runs the check
backend/.venv/bin/python scripts/check_qwen.py       # discovery + one real inference: latency, TTFT, tokens/s
```

`scripts/check_qwen.py` exits 0 and prints `QWEN VERIFIED` only after a real generation succeeded. A GitHub Copilot agent prompt that
does all of this is in `.github/prompts/run-flying-florina-with-local-qwen.prompt.md`.

## 3. Where Qwen is used, and where it is not

| Qwen does (language reasoning) | Deterministic code does (never the model) |
|---|---|
| Explains every workflow's verified findings (diagnostics, recovery, modernization, executive, parts, governance, compliance, downtime analytics) | Telemetry statistics, anomaly z-scores, inventory reconciliation, scheduling, simulations, ROI |
| Classifies ambiguous questions into a closed label set (router stage 6) | Routing rules, semantic similarity, policy and security decisions |
| Answers general aviation questions (no fleet data) | Every number, citation, approval and audit record |
| Explains predictive-maintenance scores | Evidence Challenger checks on everything Qwen writes |

Qwen's output is treated as untrusted text: it is schema-validated, then the **Evidence Challenger** removes or rejects any number or
identifier (aircraft, part, document, work order, approval, policy, supplier) that is not in the verified facts, and any airworthiness,
return-to-service, certification or guaranteed-savings claim; causal wording is softened to "associated with". Model output is never
parsed into tool calls, and approvals still require a different authorized human.

## 4. Performance controls

| Setting | Default | Effect |
|---|---|---|
| `FF_QWEN_THREADS` | CPU cores − 1 | llama.cpp CPU threads |
| `FF_QWEN_GPU_LAYERS` | -1 | offload every layer when the build supports GPU/Metal; 0 = CPU only |
| `FF_QWEN_N_CTX` | 4096 | context window; prompts are trimmed to fit with the output budget |
| `FF_QWEN_MAX_TOKENS` | 320 | output cap per call (explanations target ~150–250 tokens) |
| `FF_QWEN_TIMEOUT_S` | 45 | wall-clock limit, checked between streamed tokens |
| `FF_QWEN_CONCURRENCY` | 1 | one generation at a time (llama.cpp contexts are not thread-safe) |
| `FF_QWEN_PRELOAD` | true | load and warm the model in the background at startup |

Latency lessons from the Copilot applied here: compact fact packs instead of raw data (≤ 7,000 characters), one explanation call per
answer, a bounded output, a warm single model instance, an exact-prompt cache (repeat questions answer instantly), deterministic work
done before the model is called, and the evidence workspace rendered **before** the explanation arrives.

## 5. Measured performance

| Measurement | Value | Where |
|---|---|---|
| Deterministic workflows (no model), warm median | 57–850 ms; the four questions 163–323 ms | `docs/latency_measured.json` (build machine) |
| Qwen latency p50/p95, time to first token, tokens/s | **not measured on the build machine** (no Qwen there) | Run **Benchmark** in Evaluation & Observability, or `scripts/check_qwen.py`, on your machine |

No Qwen benchmark is quoted in this repository because none was measured; the dashboard shows your real numbers once Qwen is connected.
For reference, the Copilot's own notes measured 130–190-token answers from this model size; expect seconds, not milliseconds, per
explanation on CPU. Cached and deterministic interactions return in well under one second.

## 6. Monitoring

**Evaluation & Observability** shows: model, quantization, runtime, path, parameters, GPU offload, model load time, CPU load, process
and system memory, GPU utilisation (when `nvidia-smi` exists), calls (live/cached), latency p50/p95, time to first token, tokens/s,
cache hit rate, errors, prompt/completion tokens, per-agent usage and recent calls. All values are read from the local `llm_calls`
table and the OS; nothing is sent to an external telemetry service.
