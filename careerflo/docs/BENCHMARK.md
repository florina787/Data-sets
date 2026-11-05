# Qwen benchmark (measured, not estimated)

Machine: 4 vCPU, 16 GB RAM, **no GPU**. Runtime: Ollama 0.40.14 with its default 4-bit quantisation. Harness: `backend/scripts/benchmark_qwen.py`, which uses the same `QwenClient` as the app (thinking disabled). Raw output: [benchmark.json](benchmark.json).

| Model | Load (s) | Server RAM (GB) | TTFT (ms) | Tokens/s | Structured JSON | Tool selection | Resume skills recall / precision | Interview feedback names the gap |
|---|---|---|---|---|---|---|---|---|
| qwen3:0.6b | 48.5 (cold) | 1.24 | 166 | **36.8** | 3/4 | 6/8 | 0.78 / 0.88 | 1/2 |
| qwen3:1.7b | 5.6 | 2.08 | 342 | 15.0 | **4/4** | **8/8** | 0.56 / 0.83 | 1/2 |
| qwen3:4b ¹ | 13.6 | — | 2156 | 4.6 | 4/4 | 8/8 | not re-measured | 1/2 |

¹ The 4B figures come from the earlier full run. The later rerun timed out while loading the model cold from disk.

CPU was at about 99% during every generation, so one generation uses the whole machine.

**Choice: `qwen3:1.7b` (default).** It is the smallest model with perfect structured-output and tool-selection scores on these sets, and it streams at about 15 tok/s on 4 vCPUs. `qwen3:4b` is 3× slower with no measured accuracy gain here. `qwen3:0.6b` is the fallback for low-memory hosts or for narrative-only use.

**Caveats.** The test sets are tiny (4 extraction cases, 8 routing cases, 1 resume, 2 interview answers), so treat the accuracy columns as indicative. The app does not depend on them: routing, scoring, extraction for matching, and all safety checks are deterministic, and every model-written resume summary or cover letter is fact-checked and rejected if unsupported. Load times depend on disk cache; the first load after boot is slow.

**Bug found by this benchmark:** Qwen3 on Ollama put the whole answer in a separate `reasoning` field, so `content` came back empty. This is fixed in `QwenClient.build_body` (`reasoning_effort: "none"` for Ollama, `enable_thinking: false` for llama.cpp) and covered by a test.
