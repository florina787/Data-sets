#!/usr/bin/env bash
# Builds the installer for the current OS: frozen backend, then electron-builder.
# PyInstaller cannot cross-compile, so run this on the target OS (CI does all three).
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/pip install pyinstaller==6.22.3
.venv/bin/pyinstaller packaging/backend.spec --noconfirm --distpath packaging/backend-dist --workpath packaging/build
.venv/bin/python packaging/smoke_backend.py packaging/backend-dist/veena-backend/veena-backend
cd apps/desktop
npm run build
case "$(uname -s)" in
  Darwin) npx electron-builder --mac --publish never ;;
  Linux) npx electron-builder --linux --publish never ;;
esac
ls -lh release
