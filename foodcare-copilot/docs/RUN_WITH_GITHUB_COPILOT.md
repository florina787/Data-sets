# Run Flo & Jerry with GitHub Copilot in VS Code

GitHub Copilot cannot be controlled from outside VS Code, so this page gives you everything to hand it the job.
Copilot automatically reads `.github/copilot-instructions.md`, so it already knows the commands and the rules
(no model downloads, no second model server, no pushing).

## 1. Open the project
1. In VS Code: **File → Open Folder…** and choose the `foodcare-copilot` folder
   (inside your `Data-sets` clone, on branch `claude/new-session-pahp8j`).
2. Open Copilot Chat (the chat icon, or `Ctrl+Alt+I` / `⌃⌘I` on Mac) and switch the mode picker to **Agent**.
   *Why Agent:* only Agent mode may run terminal commands; Ask mode can only answer.

## 2. Paste this prompt

```text
Run the Flo & Jerry app in this workspace by following .github/copilot-instructions.md.
1. Check git, python3 (3.11+), uv and node (20+). If git is missing on macOS, stop and tell me to run xcode-select --install.
2. Stop anything on ports 8700 and 8801.
3. Run the VS Code task "Flo & Jerry: start (demo mode)" (or scripts/start.sh) and wait for "Uvicorn running on".
4. Confirm http://127.0.0.1:8700/api/health returns ok, then tell me to open http://127.0.0.1:8700.
Optional local model: check whether Ollama answers at http://127.0.0.1:11434/v1/models. If it does, show me the
model names and ask which one to use; then copy .env.example to .env, set FOODCARE_LLM_BASE_URL and FOODCARE_LLM_MODEL,
and restart. Do not download or pull any model, do not install Ollama, do not start another model server, do not push.
```

Copilot will ask before running each command. Read each one and click **Continue** only if it matches the steps above.

## 3. Or run it yourself without Copilot
**Terminal → Run Task…** then pick:

| Task | What it does |
|---|---|
| Flo & Jerry: check prerequisites | Prints git, Python, uv, Node and npm versions |
| Flo & Jerry: start (demo mode) | Starts the app at http://127.0.0.1:8700 |
| Flo & Jerry: start with local Qwen | Asks for your model server URL and model name, then starts in LIVE-capable mode |
| Flo & Jerry: stop | Stops anything on ports 8700 and 8801 |
| Flo & Jerry: run tests | Lint, backend tests, UI build |
| Flo & Jerry: reset demo | Clean demo data (saved conversations and inspections are kept) |

## Why it works this way
- **Why not let Copilot "use Qwen" for the app directly?** Copilot has no API that other programs can call.
  Both Copilot and Flo & Jerry talk to the same local server (Ollama or LM Studio), so they share one loaded model.
- **Why forbid model downloads?** Models are gigabytes and you already have one; a second copy would double RAM use.
- **Why approve each command?** Agent mode runs real commands on your computer; reviewing them keeps you in control.
