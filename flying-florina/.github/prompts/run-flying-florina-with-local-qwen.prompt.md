---
mode: agent
description: Set up and run Flying Florina 3.0 locally with my EXISTING local Qwen model (no downloads, no cloud APIs)
---

I want the Flying Florina 3.0 app (folder `flying-florina/`: FastAPI backend in `backend/`, React frontend in `frontend/`) running on
this machine, using the Qwen model that is ALREADY on this computer. Work step by step in the VS Code terminal, show me the output of
each step, and stop to explain if something fails.

Hard rules:
- Do NOT download any model. Never run `ollama pull`, `huggingface-cli download` or anything similar. Reuse my existing Qwen.
- Do NOT add OpenAI, Anthropic, Gemini or any other cloud or paid API, and do not change the app's code to make something "work".
- If my Qwen model cannot be found or run, the app still works without it: tell me exactly what was searched and why it failed.
- Use PowerShell syntax on Windows and bash on macOS/Linux. `make` may not exist on Windows; use the two-terminal commands instead.

Steps:
1. Check prerequisites: `python --version` (3.11+), `node --version` (20+), `git --version`. If one is missing, tell me how to install it and stop.
2. Make sure I'm on the right branch: `git checkout claude/new-session-yijwxb` and `git pull`.
3. Find my existing Qwen model, in this order:
   - `ollama list` (if Ollama is installed): a model whose name contains `qwen`;
   - `*.gguf` files with `qwen` in the name in: `conversation-intelligence-copilot/data/models/`, `flying-florina/models/`, `~/models`,
     `~/.cache/huggingface/hub`, `~/.cache/lm-studio/models`, `~/.lmstudio/models` (on Windows also `%USERPROFILE%\models` and `%USERPROFILE%\Downloads`).
   Report the model name, quantization (e.g. Q4_K_M), path or server URL and size.
4. If it is a `.gguf` file outside those folders, create `flying-florina/.env` with `FF_QWEN_MODEL_PATH=<absolute path to the .gguf>`
   (copy the other lines from `flying-florina/.env.example`).
5. Run the one-time setup from the `flying-florina` folder (needs internet once; it installs packages, creates the synthetic data,
   fits the forecasting models and checks Qwen):
   - macOS/Linux: `sh scripts/setup.sh`
   - Windows: `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`
   If `llama-cpp-python` fails to build, don't retry the same command. Either install the prebuilt CPU wheel
   (`pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu` inside `backend/.venv`)
   or use Ollama with my existing model and set `LLM_URL=http://127.0.0.1:11434` in `.env`.
6. Verify Qwen with one real answer: in `flying-florina/backend` run the venv Python on `../scripts/check_qwen.py`
   (`.venv/bin/python` on macOS/Linux, `.\.venv\Scripts\python` on Windows). It must end with `QWEN VERIFIED`; show me the latency,
   time to first token and tokens per second.
7. Start the app in two terminals (or run the VS Code task "Flying Florina: run app" with Ctrl+Shift+B):
   - backend, in `flying-florina/backend`: venv Python `-m uvicorn app.main:app --host 127.0.0.1 --port 8000`
   - frontend, in `flying-florina/frontend`: `npm run dev`
   Wait for the backend log line "Forecasting models ready" (or "loaded from cache"), then tell me to open http://127.0.0.1:5173.
8. Smoke-test it from the terminal: `curl http://127.0.0.1:8000/health` and `curl http://127.0.0.1:8000/ready` must both return status ok/ready.
9. Tell me what to check in the browser: the green "Local Qwen" pill at the top right; the Global Intelligence globe; and in
   Flying Florina Chat, asking "Show hydraulic component shortages in Europe." and then "What about the next 60 days?" (the second
   answer must keep hydraulics and Europe).
10. Optional, if I say yes: run the backend tests (`python -m pytest -q` with the venv Python in `backend/`) and
    `scripts/benchmark_3.py`, and show me the measured numbers.
