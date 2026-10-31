# One-time setup for Windows PowerShell (needs network once for packages; runtime is offline).
# Your existing local Qwen model is REUSED: nothing here downloads a model.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
python -m venv .venv
.\.venv\Scripts\pip install -q -r requirements-dev.txt
try {
  $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2
  $hasQwen = ($tags.models | Where-Object { $_.name -match "qwen" }).Count -gt 0
} catch { $hasQwen = $false }
if ($hasQwen) { Write-Host "Ollama with a Qwen model detected: using it." }
else {
  $ErrorActionPreference = "Continue"
  .\.venv\Scripts\pip install -q -r requirements-llm.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
  $ErrorActionPreference = "Stop"
}
.\.venv\Scripts\python -m app.seed.generator | Out-Null
Write-Host "Backend ready (synthetic DB seeded)."
.\.venv\Scripts\python ..\scripts\check_qwen.py
Set-Location "$Root\frontend"
npm ci --no-audit --no-fund
Write-Host "Frontend ready. Start: backend: .\.venv\Scripts\uvicorn app.main:app --port 8000 ; frontend: npm run dev"
