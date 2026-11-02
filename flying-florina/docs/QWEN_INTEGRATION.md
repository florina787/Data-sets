# Qwen integration (3.0)

3.0 keeps the 2.0 local-Qwen gateway unchanged and preferred. Full gateway documentation: [QWEN_LOCAL_LLM.md](QWEN_LOCAL_LLM.md).

## What was inspected

| Item | Finding on the build machine | On your machine |
|---|---|---|
| Model | none present (cloud container) | auto-discovered: `FF_QWEN_MODEL_PATH`, `FF_QWEN_BASE_URL`, Ollama `qwen*`, llama.cpp/LM Studio server, `*qwen*.gguf` (incl. `../conversation-intelligence-copilot/data/models/qwen2.5-1.5b-instruct-q4_k_m.gguf`) |
| Size / quantization | — | reported by discovery (e.g. Q4_K_M from the file name; parameter count from Ollama) |
| Context window | configured 4096 (`FF_QWEN_N_CTX`) | same |
| Modality | — | Qwen2.5-Instruct is **text-only**; the Airspace Safety Lab reports this and does not pretend to see images |
| Runtime | llama-cpp-python not installed here | in-process llama.cpp, Ollama, or OpenAI-compatible local server |
| CPU / GPU | 4 CPUs, no GPU | GPU offload when the llama.cpp build supports it (`FF_QWEN_GPU_LAYERS=-1`) |

## What Qwen does in 3.0

* Explains every harness answer (forecasts, shortages, supplier impact, twins, resilience) **after** the deterministic composer has
  produced it; the Evidence Challenger then removes any number or identifier not in the verified facts.
* Classifies ambiguous questions into a closed label set that now includes the 3.0 intents (router stage 6); slots are still
  extracted deterministically.
* Never produces a forecast, interval, probability, cost or approval.

## Performance and resource protection (unchanged gateway + 3.0 additions)

* One warm model instance, concurrency 1, bounded context (prompt trimmed to fit with the output budget), bounded output
  (320 tokens), wall-clock timeout, exact-prompt cache, telemetry in `llm_calls`.
* 3.0 memory never sends the whole history: `memory.context_for_model` builds a session summary + the last 6 turns + up to 2
  retrieved older turns, capped at 2,400 characters.
* One explanation per answer; the harness budget counts tool calls, and the DAG cannot loop.
* Forecasting models are fitted once and cached on disk, so a restart does not re-run them.

## Graceful degradation

`LLM_ENABLED=on` (default) marks Qwen as required: the header pill turns red and every answer carries a "Qwen not reachable" status
block while the deterministic answer, charts and evidence remain fully available. `auto` uses Qwen when found; `off` never calls a
model. There is no cloud fallback in any mode.

## Measured

No Qwen latency is quoted: none was measured here. Run `scripts/check_qwen.py` and the Benchmark button (Evaluation & Observability) or
`scripts/benchmark_3.py` on your machine; the Control Tower then shows real p50/p95 latency, time to first token, tokens/s and cache hits.
