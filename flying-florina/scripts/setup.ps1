# One-time setup for Windows PowerShell (needs network once; runtime is offline).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
python -m venv .venv
.\.venv\Scripts\pip install -q -r requirements-dev.txt
.\.venv\Scripts\python -m app.seed.generator | Out-Null
Write-Host "Backend ready (synthetic DB seeded)."
Set-Location "$Root\frontend"
npm ci --no-audit --no-fund
Write-Host "Frontend ready. Start: backend: .\.venv\Scripts\uvicorn app.main:app --reload ; frontend: npm run dev"
