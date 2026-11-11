# Instructions for GitHub Copilot: Flo & Jerry — Food Copilot 2.0

This folder (`foodcare-copilot/`) is a FastAPI + React portfolio prototype with synthetic data only.

## How to run it
0. Make sure the code is current: `git fetch origin && git checkout claude/new-session-pahp8j && git pull`.
   The current app is the navy "Flo & Jerry" UI. A light-green "FoodCare Enterprise Copilot" page means an old checkout.
1. Check prerequisites: `git --version`, `uv --version`, `node --version` (20+). Python comes from uv:
   `.python-version` pins **3.13**, and uv downloads it if needed. Never use Python 3.14+/3.15 here (some pinned
   packages have no wheels for them and would ask for C++ build tools).
   On macOS, if git is missing, tell the user to run `xcode-select --install`. Do not try to install Xcode yourself.
2. **Windows:** run every command in **Git Bash** (`C:\Program Files\Git\bin\bash.exe`), not PowerShell or cmd.
   The VS Code tasks already use Git Bash on Windows. If `.venv` was created with another Python version
   (check with `.venv/Scripts/python --version` on Windows, `.venv/bin/python --version` elsewhere), delete `.venv`
   and run `scripts/setup.sh` (or the task "Flo & Jerry: clean reinstall").
3. If ports 8700 or 8801 are busy, run the task "Flo & Jerry: stop"
   (macOS/Linux: `lsof -t -i :8700 -i :8801 | xargs kill`).
4. Start: `scripts/start.sh` (the first run installs pinned packages and builds the UI; this takes a few minutes).
   Wait for `Uvicorn running on http://127.0.0.1:8700`, then open http://127.0.0.1:8700.
   The VS Code task "Flo & Jerry: start (demo mode)" does the same.
   "Failed to fetch" in the browser means the server is not running: read the first error in the terminal and fix that.
5. Check: `curl -s http://127.0.0.1:8700/api/health` returns `{"status":"ok"}`.
6. Tests: `scripts/test.sh` (lint, backend tests, UI build) and `npm run e2e` (browser tests).
7. Metrics and token usage: `curl -s http://127.0.0.1:8700/metrics` (Prometheus format) and the
   "Local-model token usage" panel on System Observability (`GET /api/llm/usage`, needs sign-in).
8. Global supply-chain maps: Executive Command → "Global supply chain intelligence" (3D globe / 2D map).
   All network data there is a labelled SYNTHETIC scenario from `fixtures/geo/scenario.json`.

## Optional: the user's local Qwen model
- Use ONLY a model server that is already running (Ollama on port 11434 or LM Studio on 1234).
  Check with `curl -s http://127.0.0.1:11434/v1/models` (lists models; loads no weights).
- Put the settings in `foodcare-copilot/.env` (git-ignored; copy from `.env.example`):
  `FOODCARE_LLM_BASE_URL=http://127.0.0.1:11434/v1` and `FOODCARE_LLM_MODEL=<exact name from ollama list>`.
- Then restart with `scripts/start.sh` and tick LIVE in Ask Copilot. `GET /api/llm/status` shows reachability.

## Rules (do not break these)
- Do NOT download, pull or install any language model or vision model weights (no `ollama pull`, no Hugging Face downloads).
- Do NOT install a second model runtime or start another model server. Reuse the one that is running.
- Do NOT add cloud AI APIs (OpenAI, Anthropic, Gemini).
- Do NOT commit `.env`, push to git, or change the branch without the user's explicit request.
- Do NOT describe the potato inspection as a trained AI model: it is classical image processing with colour heuristics.
- Keep CPU and RAM low: one model request and one image inspection at a time are the defaults.
- Never estimate token counts: they come only from the model server's `usage` field.

## Where things are
- Backend: `backend/app/` (`main.py` API, `copilot/` question answering, `vision/` potato pipeline,
  `memory/` SQLite memory, `llm/local.py` local model client, `resources.py` CPU/RAM,
  `observability.py` /metrics and token usage).
- Deployment: `Dockerfile`, `deploy/k8s/`, `deploy/flux/`; research note in `docs/MCCAIN_INTEGRATION.md`.
- Frontend: `apps/control-room/src/` (screens in `screens/`, theme in `tailwind.config.js` and `index.css`).
- Docs: `README.md` (layman guide) and `docs/`.

**Terminal rule (Windows):** the workspace sets Git Bash as the default terminal (`.vscode/settings.json`).
Run ONE simple command per terminal call, directly in that Git Bash terminal. NEVER wrap bash inside PowerShell
(no `& 'C:\Program Files\Git\bin\bash.exe' -lc '...'`): PowerShell strips the inner quotes and bash fails with
"unexpected end of file". Avoid multi-line `if ... fi` one-liners; use plain commands such as `ls`, `cat FILE`, `cd DIR`.
If the terminal is still PowerShell, stop and ask the user to reload VS Code (Developer: Reload Window).
