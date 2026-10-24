# Developer setup for Windows (PowerShell): Python backend + desktop app.
# Free tools only. Needs Python 3.11+, Node 22+, and internet for the first download.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# CPU build of torch (about 200 MB instead of several GB of CUDA libraries).
.\.venv\Scripts\pip.exe install --extra-index-url https://download.pytorch.org/whl/cpu -e ".[dev]"

Push-Location apps\desktop
npm ci
node scripts\make-icons.mjs
Pop-Location

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama is not installed. Get it free from https://ollama.com/download"
}
if (-not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) {
  Write-Host "Optional: install Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki) for better screen text."
}
Write-Host ""
Write-Host "Done. Next:"
Write-Host "  ollama pull qwen2.5:3b; ollama pull qwen2.5vl:3b   # or let the Setup wizard do it"
Write-Host "  cd apps\desktop; npm run dev"
