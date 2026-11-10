---
mode: agent
description: Enable the optional local LLM (Qwen2.5-1.5B via llama-cpp-python) for the Conversation Intelligence Copilot
---

I'm working in the "conversation-intelligence-copilot" project (FastAPI backend in backend/, React frontend in frontend/, Python managed with uv). The app currently runs WITHOUT its optional local language model. The UI says "No LLM is available". I want to enable the local LLM (Qwen2.5-1.5B-Instruct, GGUF, run with llama-cpp-python on CPU). Please do this step by step, running commands in the VS Code terminal and showing me the output.

Goal: the file data/models/qwen2.5-1.5b-instruct-q4_k_m.gguf exists, llama-cpp-python is installed in backend/.venv, and after a restart the app's top bar shows "Local LLM · qwen2.5-1.5b-instruct-q4_k_m".

Steps:
1. Detect my OS and confirm the terminal is in the conversation-intelligence-copilot folder (the one containing Makefile, backend/ and frontend/). Check that uv is installed (`uv --version`).
2. Check .env in the project root. If it contains LLM_PROVIDER=none or LLM_ENABLED=false, tell me and ask before changing it. LLM_PROVIDER should be auto (or local).
3. Install the local-model dependencies:
   - If `make` is available (macOS/Linux): run `make install-local-llm`.
   - Otherwise (usually Windows): run `cd backend && uv sync --extra transformers --extra local-llm`.
4. If installing llama-cpp-python fails because it needs to compile C++ code, do not keep retrying the same command. Instead, install the prebuilt CPU wheel:
   `cd backend && uv pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`
   If that also fails, tell me which build tools my OS needs (Windows: Visual Studio Build Tools with the C++ workload, plus CMake; macOS: `xcode-select --install`; Linux: build-essential and cmake) and stop.
5. Verify the install: `cd backend && uv run python -c "import llama_cpp; print(llama_cpp.__version__)"`
6. Download the model (about 1.1 GB):
   - With make: `make llm-download`
   - Without make: `cd backend && uv run python -c "from app.config import get_settings; from app.llm.local_client import download_model; print(download_model(get_settings()))"`
   Then confirm the file data/models/qwen2.5-1.5b-instruct-q4_k_m.gguf exists and report its size.
7. Tell me to restart the app: stop the running debug session (Shift+F5), then in Run and Debug choose "Full stack (API + UI)" and press F5. The backend only checks for the model at start-up.
8. After I restart, help me verify: the top bar should show "Local LLM · qwen2.5-1.5b-instruct-q4_k_m", and http://localhost:8000/api/model/status should report the local model as available. The first model call can take about 10 seconds while the model loads.

Rules:
- Do not edit any source code, tests or config files other than .env (and only with my permission).
- Do not commit, push or create branches.
- Do not add or ask for any API keys. This project uses only the local model.
- Do not delete data/, data/processed/ or data/indexes/.
- If a step fails, show me the exact error and explain it before trying anything else.
