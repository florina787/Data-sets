---
mode: agent
description: Set up and run Flying_Florina 2.0 locally with my EXISTING local Qwen model (no downloads, no cloud APIs)
---

I'm working in the `flying-florina/` project of this repository (FastAPI backend in `flying-florina/backend/`, React frontend in
`flying-florina/frontend/`). I want it running on this machine using the Qwen model that is ALREADY downloaded here. Please do this
step by step in the VS Code terminal and show me the output of each step.

Hard rules:
- Do NOT download any model, do NOT run `huggingface-cli download`, `ollama pull`, or anything similar. Reuse my existing Qwen.
- Do NOT add OpenAI, Anthropic, Gemini or any other cloud/paid API.
- If my Qwen model cannot be found or run, stop and tell me exactly what was searched and why it failed.

Steps:
1. Find my existing Qwen model. Check, in this order:
   - `ollama list` (if Ollama is installed) for a model whose name contains `qwen`;
   - `conversation-intelligence-copilot/data/models/*.gguf` next to `flying-florina/` (the Copilot stored `qwen2.5-1.5b-instruct-q4_k_m.gguf` there);
   - `~/models`, `~/.cache/huggingface/hub`, `~/.cache/lm-studio/models`, `~/.lmstudio/models` for `*qwen*.gguf`.
   Report the model name, quantization (e.g. Q4_K_M), file path or server URL, and size.
2. If the model is a `.gguf` file outside those folders, create `flying-florina/.env` with
   `FF_QWEN_MODEL_PATH=<absolute path to the .gguf>` (copy the other lines from `.env.example`).
3. Run the one-time setup:
   - macOS / Linux: `cd flying-florina && sh scripts/setup.sh`
   - Windows PowerShell: `cd flying-florina; powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`
   It installs Python/npm packages and the llama.cpp runtime library (`llama-cpp-python`, prebuilt CPU wheel; Metal on macOS),
   seeds the synthetic database, and runs `scripts/check_qwen.py`. If `llama-cpp-python` fails to build, do not retry the same command:
   install the prebuilt wheel with
   `backend/.venv/bin/pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`
   (or serve the model with Ollama instead and set `LLM_URL=http://127.0.0.1:11434`).
4. Verify Qwen with a real inference: `cd flying-florina && backend/.venv/bin/python scripts/check_qwen.py`.
   It must end with `QWEN VERIFIED` and print latency, time to first token and tokens per second. Show me that output.
5. Start the app: `cd flying-florina && make demo` (or, in two terminals: `cd backend && .venv/bin/uvicorn app.main:app --port 8000`
   and `cd frontend && npm run dev`). Open http://127.0.0.1:5173.
6. Confirm in the UI: the top bar shows a green **Local Qwen · <model> · <quantization>** pill; the four question cards on the
   homepage each return an answer with a **"Explained by Local Qwen"** card and an Evidence Challenger verdict.
7. Open **Evaluation & Observability**, click **Benchmark (uncached)**, and report the measured p50/p95 latency, time to first token
   and tokens/s on this machine.
8. Run the measured evaluation with Qwen: `cd flying-florina && backend/.venv/bin/python scripts/eval_four_questions.py --split test_v2`
   and show me the routing accuracy, macro-F1 and unsupported-claim rate it prints.
