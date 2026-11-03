# Instructions for GitHub Copilot: Flo & Jerry — Food Copilot 2.0

This folder (`foodcare-copilot/`) is a FastAPI + React portfolio prototype with synthetic data only.

## How to run it
1. Check prerequisites: `git --version`, `python3 --version` (3.11+), `uv --version`, `node --version` (20+).
   On macOS, if git is missing, tell the user to run `xcode-select --install`. Do not try to install Xcode yourself.
2. If ports 8700 or 8801 are busy, stop the old copy: `lsof -t -i :8700 -i :8801 | xargs kill`.
3. Start: `scripts/start.sh` (the first run installs pinned packages and builds the UI; this takes a few minutes).
   Wait for `Uvicorn running on http://127.0.0.1:8700`, then open http://127.0.0.1:8700.
   The VS Code task "Flo & Jerry: start (demo mode)" does the same.
4. Tests: `scripts/test.sh` (lint, backend tests, UI build) and `npm run e2e` (browser tests).

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

## Where things are
- Backend: `backend/app/` (`main.py` API, `copilot/` question answering, `vision/` potato pipeline,
  `memory/` SQLite memory, `llm/local.py` local model client, `resources.py` CPU/RAM).
- Frontend: `apps/control-room/src/` (screens in `screens/`, theme in `tailwind.config.js` and `index.css`).
- Docs: `README.md` (layman guide) and `docs/`.
