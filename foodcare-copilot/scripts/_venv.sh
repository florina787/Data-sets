# Sourced by the other scripts: the virtual environment's tools on any OS.
# Linux/macOS put them in .venv/bin; Windows (Git Bash) puts them in .venv/Scripts.
_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -d "$_root/.venv/Scripts" ]; then VENV_BIN="$_root/.venv/Scripts"; else VENV_BIN="$_root/.venv/bin"; fi
PY="$VENV_BIN/python"
export VENV_BIN PY
